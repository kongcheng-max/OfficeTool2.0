"""知识库管理 API"""

from fastapi import APIRouter, Depends
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


@router.delete("/{kb_id}", response_model=APIResponse)
async def delete_kb(
    kb_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除知识库"""
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.owner_id == current_user.id,
        )
    )
    kb = result.scalar_one_or_none()
    if not kb:
        raise NotFoundError("知识库")

    await db.delete(kb)
    return APIResponse.success(message="知识库已删除")
