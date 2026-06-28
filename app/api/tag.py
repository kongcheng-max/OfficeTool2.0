"""标签管理 API — CRUD + 文档关联 + KB 统计"""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from core.database import get_db
from core.exceptions import BadRequestError, NotFoundError
from core.response import APIResponse
from models.models import Document, KnowledgeBase, Tag, User, document_tags
from schemas.schemas import TagAssignRequest, TagCreateRequest, TagResponse, TagStatResponse

router = APIRouter(prefix="/api/v1/kb/{kb_id}/tags", tags=["标签"])


async def _verify_kb(kb_id: str, user_id: str, db: AsyncSession) -> KnowledgeBase:
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.owner_id == user_id,
        )
    )
    kb = result.scalar_one_or_none()
    if not kb:
        raise NotFoundError("知识库")
    return kb


@router.post("", response_model=APIResponse[TagResponse])
async def create_tag(
    kb_id: str,
    req: TagCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建标签"""
    await _verify_kb(kb_id, current_user.id, db)

    result = await db.execute(
        select(Tag).where(Tag.kb_id == kb_id, Tag.name == req.name)
    )
    if result.scalar_one_or_none():
        raise BadRequestError("标签名已存在")

    tag = Tag(name=req.name, color=req.color, kb_id=kb_id)
    db.add(tag)
    await db.flush()
    await db.refresh(tag)
    return APIResponse.success(TagResponse.model_validate(tag), message="标签创建成功")


@router.get("", response_model=APIResponse[list[TagResponse]])
async def list_tags(
    kb_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """知识库标签列表"""
    await _verify_kb(kb_id, current_user.id, db)
    result = await db.execute(
        select(Tag).where(Tag.kb_id == kb_id).order_by(Tag.created_at.desc())
    )
    tags = result.scalars().all()
    return APIResponse.success([TagResponse.model_validate(t) for t in tags])


@router.get("/stats", response_model=APIResponse[list[TagStatResponse]])
async def tag_stats(
    kb_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """知识库标签使用统计 — 每个标签关联的文档数量"""
    await _verify_kb(kb_id, current_user.id, db)

    result = await db.execute(
        text("""
            SELECT t.id AS id, t.name AS name, t.color,
                   COUNT(dt.document_id) AS document_count
            FROM tags t
            LEFT JOIN document_tags dt ON dt.tag_id = t.id
            WHERE t.kb_id = :kb_id
            GROUP BY t.id, t.name, t.color
            ORDER BY document_count DESC
        """),
        {"kb_id": kb_id},
    )
    rows = result.fetchall()
    stats = [
        TagStatResponse(
            id=r.id,
            name=r.name,
            color=r.color,
            document_count=r.document_count,
        )
        for r in rows
    ]
    return APIResponse.success(stats)


@router.delete("/{tag_id}", response_model=APIResponse)
async def delete_tag(
    kb_id: str,
    tag_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除标签（同时解除所有文档关联）"""
    await _verify_kb(kb_id, current_user.id, db)

    result = await db.execute(
        select(Tag).where(Tag.id == tag_id, Tag.kb_id == kb_id)
    )
    tag = result.scalar_one_or_none()
    if not tag:
        raise NotFoundError("标签")

    # 先解除关联
    await db.execute(
        text("DELETE FROM document_tags WHERE tag_id = :tid"), {"tid": tag_id}
    )
    await db.delete(tag)
    return APIResponse.success(message="标签已删除")


@router.post("/assign", response_model=APIResponse)
async def assign_tags(
    kb_id: str,
    req: TagAssignRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """为文档批量分配标签"""
    await _verify_kb(kb_id, current_user.id, db)

    tags_result = await db.execute(
        select(Tag).where(Tag.id.in_(req.tag_ids), Tag.kb_id == kb_id)
    )
    tags = tags_result.scalars().all()

    from sqlalchemy.orm import selectinload
    docs_result = await db.execute(
        select(Document).where(
            Document.id.in_(req.document_ids),
            Document.kb_id == kb_id,
        ).options(selectinload(Document.tags))
    )
    docs = docs_result.scalars().all()

    for doc in docs:
        for tag in tags:
            # doc.tags is now eagerly loaded via selectinload
            if tag not in doc.tags:
                doc.tags.append(tag)

    await db.flush()
    return APIResponse.success(
        message=f"已为 {len(docs)} 个文档分配 {len(tags)} 个标签"
    )


@router.post("/unassign", response_model=APIResponse)
async def unassign_tags(
    kb_id: str,
    req: TagAssignRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """为文档批量移除标签"""
    await _verify_kb(kb_id, current_user.id, db)

    # 直接通过关联表删除
    for doc_id in req.document_ids:
        for tag_id in req.tag_ids:
            await db.execute(
                text(
                    "DELETE FROM document_tags WHERE document_id = :did AND tag_id = :tid"
                ),
                {"did": doc_id, "tid": tag_id},
            )

    return APIResponse.success(message=f"已移除 {len(req.tag_ids)} 个标签的关联")
