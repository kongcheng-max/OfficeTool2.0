"""知识库管理 API"""

import asyncio

from fastapi import APIRouter, Depends
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from core.database import get_db
from core.exceptions import NotFoundError
from core.response import APIResponse
from models.models import Document, KnowledgeBase, User
from schemas.schemas import KBCreateRequest, KBResponse, KBUpdateRequest

router = APIRouter(prefix="/api/v1/knowledge-bases", tags=["知识库"])


async def _enrich_kb(kb: KnowledgeBase, db: AsyncSession) -> dict:
    """为知识库补充文档计数"""
    result = await db.execute(
        select(func.count(Document.id)).where(Document.kb_id == kb.id)
    )
    doc_count = result.scalar() or 0
    data = KBResponse(
        id=kb.id,
        name=kb.name,
        description=kb.description,
        owner_id=kb.owner_id,
        chunk_count=kb.chunk_count,
        doc_count=doc_count,
        created_at=kb.created_at,
        updated_at=kb.updated_at,
    )
    return data


@router.post("", response_model=APIResponse[KBResponse])
async def create_kb(
    req: KBCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建知识库"""
    kb = KnowledgeBase(
        name=req.name,
        description=req.description,
        owner_id=current_user.id,
    )
    db.add(kb)
    await db.flush()
    await db.refresh(kb)

    data = await _enrich_kb(kb, db)
    return APIResponse.success(data, message="知识库创建成功")


@router.get("", response_model=APIResponse[list[KBResponse]])
async def list_kbs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的知识库列表"""
    result = await db.execute(
        select(KnowledgeBase)
        .where(KnowledgeBase.owner_id == current_user.id)
        .order_by(KnowledgeBase.updated_at.desc())
    )
    kbs = result.scalars().all()

    items = []
    for kb in kbs:
        items.append(await _enrich_kb(kb, db))

    return APIResponse.success(items)


@router.get("/{kb_id}", response_model=APIResponse[KBResponse])
async def get_kb(
    kb_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取知识库详情"""
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.owner_id == current_user.id,
        )
    )
    kb = result.scalar_one_or_none()
    if not kb:
        raise NotFoundError("知识库")

    data = await _enrich_kb(kb, db)
    return APIResponse.success(data)


async def _cleanup_kb_resources(kb_id: str, db: AsyncSession) -> dict:
    """清理知识库关联的所有外部资源（Milvus / ES / 文件 / Neo4j）

    在 DB 删除之前调用，逐个文档清理，避免存储泄漏。
    返回清理统计信息。
    """
    from sqlalchemy import text

    from engine.rag.vector_store import vector_store
    from services.storage import storage_service

    # 查询 KB 下所有文档（含已删除/失败的，确保彻底清理）
    result = await db.execute(
        select(Document).where(Document.kb_id == kb_id)
    )
    docs = result.scalars().all()

    stats = {"docs": len(docs), "milvus_ok": 0, "milvus_fail": 0,
             "es_ok": 0, "es_fail": 0, "files_ok": 0, "files_fail": 0,
             "neo4j_ok": False}

    # ── 1. 逐个文档清理 Milvus 向量 ──
    for doc in docs:
        try:
            vector_store.delete_by_doc_id(doc.id)
            stats["milvus_ok"] += 1
        except Exception as e:
            stats["milvus_fail"] += 1
            logger.warning(f"KB 删除 — Milvus 清理失败 doc_id={doc.id}: {e}")

    # ── 2. 逐个文档清理 ES BM25 索引 ──
    try:
        from engine.rag.es_store import es_store
        for doc in docs:
            try:
                await es_store.delete_by_doc_id(doc.id)
                stats["es_ok"] += 1
            except Exception as e:
                stats["es_fail"] += 1
                logger.warning(f"KB 删除 — ES 清理失败 doc_id={doc.id}: {e}")
    except ImportError:
        logger.info("KB 删除 — ES 模块未加载，跳过 ES 清理")

    # ── 3. 逐个文档清理文件存储 ──
    for doc in docs:
        # 源文件
        if doc.file_path:
            try:
                await storage_service.delete(doc.file_path)
                stats["files_ok"] += 1
            except Exception as e:
                stats["files_fail"] += 1
                logger.warning(f"KB 删除 — 文件删除失败 doc_id={doc.id}: {e}")
        # chunks JSON
        try:
            await storage_service.delete(f"chunks/{doc.id}.json")
        except Exception:
            pass

    # ── 4. Neo4j 图谱清理 ──
    try:
        from engine.kg.neo4j_store import neo4j_store
        for doc in docs:
            try:
                await neo4j_store.delete_by_doc_id(doc.id)
            except Exception:
                pass
        stats["neo4j_ok"] = True
    except ImportError:
        logger.info("KB 删除 — Neo4j 模块未加载，跳过 KG 清理")

    logger.info(
        f"KB 删除资源清理完成 kb_id={kb_id}: "
        f"docs={stats['docs']}, milvus={stats['milvus_ok']}/{stats['milvus_fail']}, "
        f"es={stats['es_ok']}/{stats['es_fail']}, files={stats['files_ok']}/{stats['files_fail']}, "
        f"neo4j={stats['neo4j_ok']}"
    )

    return stats


@router.delete("/{kb_id}", response_model=APIResponse)
async def delete_kb(
    kb_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除知识库 — 同步清理 Milvus / ES / 文件 / Neo4j 后级联删除 DB 记录"""
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.owner_id == current_user.id,
        )
    )
    kb = result.scalar_one_or_none()
    if not kb:
        raise NotFoundError("知识库")

    # 先清理外部资源，再删除 DB 记录
    await _cleanup_kb_resources(kb_id, db)

    await db.delete(kb)
    await db.flush()

    return APIResponse.success(message="知识库已删除，关联资源已清理")
