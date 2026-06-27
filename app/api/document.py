"""文档管理 API — 上传 / 列表 / 删除"""

from fastapi import APIRouter, Depends, Query, UploadFile, File
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from core.database import get_db
from core.exceptions import BadRequestError, NotFoundError
from core.response import APIResponse, PaginatedData
from engine.rag.vector_store import vector_store
from models.models import Document, KnowledgeBase, User
from schemas.schemas import DocumentResponse, DocumentUploadResponse
from services.document_service import create_document
from services.storage import storage_service

router = APIRouter(prefix="/api/v1/kb/{kb_id}/documents", tags=["文档"])


@router.post("", response_model=APIResponse[DocumentUploadResponse])
async def upload_document(
    kb_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """上传文档到指定知识库（multipart/form-data）"""
    # 验证知识库归属
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.owner_id == current_user.id,
        )
    )
    kb = result.scalar_one_or_none()
    if not kb:
        raise NotFoundError("知识库")

    # 读取文件内容
    if not file.filename:
        raise BadRequestError("文件名不能为空")

    file_data = await file.read()
    if not file_data:
        raise BadRequestError("文件内容为空")

    # 创建文档
    doc = await create_document(
        db=db,
        kb_id=kb_id,
        filename=file.filename,
        file_data=file_data,
        mime_type=file.content_type or "",
    )

    return APIResponse.success(
        DocumentUploadResponse(
            document_id=doc.id,
            status=doc.status,
            message="文档已上传，正在解析中",
        )
    )


@router.get("", response_model=APIResponse[PaginatedData[DocumentResponse]])
async def list_documents(
    kb_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """知识库内文档列表（分页）"""
    # 验证知识库归属
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.owner_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise NotFoundError("知识库")

    # 总数
    count_result = await db.execute(
        select(func.count(Document.id)).where(Document.kb_id == kb_id)
    )
    total = count_result.scalar() or 0

    # 分页查询
    offset = (page - 1) * page_size
    result = await db.execute(
        select(Document)
        .where(Document.kb_id == kb_id)
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    docs = result.scalars().all()

    total_pages = max(1, (total + page_size - 1) // page_size)

    return APIResponse.success(
        PaginatedData(
            items=[DocumentResponse.model_validate(d) for d in docs],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    )


@router.delete("/{doc_id}", response_model=APIResponse)
async def delete_document(
    kb_id: str,
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除文档 — 同步清理 DB 记录 + Milvus 向量 + MinIO 文件"""
    from sqlalchemy import select as sa_select

    result = await db.execute(
        sa_select(Document).where(
            Document.id == doc_id,
            Document.kb_id == kb_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise NotFoundError("文档")

    # 验证知识库归属
    kb_result = await db.execute(
        sa_select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
    )
    kb = kb_result.scalar_one_or_none()
    if not kb or kb.owner_id != current_user.id:
        raise NotFoundError("知识库")

    # 1. 删除 Milvus 向量
    try:
        vector_store.delete_by_doc_id(doc_id)
        logger.info(f"Milvus 向量已删除: doc_id={doc_id}")
    except Exception as e:
        logger.warning(f"Milvus 向量删除失败（可能 Milvus 未启动）: {e}")

    # 2. 删除 MinIO / 本地文件
    try:
        await storage_service.delete(doc.file_path)
        logger.info(f"文件已删除: {doc.file_path}")
    except Exception as e:
        logger.warning(f"文件删除失败: {e}")

    # 3. 删除解析结果 (chunks JSON)
    try:
        await storage_service.delete(f"chunks/{doc_id}.json")
    except Exception:
        pass  # 可能不存在

    # 4. 删除数据库记录
    await db.delete(doc)
    await db.flush()

    # 5. 更新知识库 chunk 计数
    from sqlalchemy import text
    await db.execute(
        text(
            """UPDATE knowledge_bases
               SET chunk_count = (
                   SELECT COALESCE(SUM(chunk_count), 0)
                   FROM documents
                   WHERE kb_id = :kb_id AND status = 'ready'
               )
               WHERE id = :kb_id"""
        ),
        {"kb_id": kb_id},
    )

    return APIResponse.success(message="文档已删除")
