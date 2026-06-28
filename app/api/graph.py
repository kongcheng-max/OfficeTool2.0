"""图谱 API"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from core.database import get_db
from core.exceptions import NotFoundError
from core.response import APIResponse
from models.models import KnowledgeBase, User
from services.graph_service import find_path, get_entity, get_entity_network, list_entities

router = APIRouter(prefix="/api/v1/kb/{kb_id}/graph", tags=["知识图谱"])


@router.get("/entities", response_model=APIResponse[list])
async def search_entities(
    kb_id: str,
    q: str = Query("", description="搜索关键词"),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """实体列表（支持关键词搜索）"""
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.owner_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise NotFoundError("知识库")

    entities = await list_entities(q=q, kb_id=kb_id, limit=limit)
    return APIResponse.success(entities)


@router.get("/entity/{entity_name:path}/network", response_model=APIResponse[dict])
async def get_network(
    kb_id: str,
    entity_name: str,
    depth: int = Query(2, ge=1, le=4),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """实体关系网络（子图）

    注意：此路由必须在 /entity/{entity_name:path} 之前注册，
    否则 :path 转换器会贪心匹配 /network 后缀。
    """
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.owner_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise NotFoundError("知识库")

    network = await get_entity_network(entity_name, depth=depth)
    return APIResponse.success(network)


@router.get("/entity/{entity_name:path}", response_model=APIResponse[dict])
async def get_entity_detail(
    kb_id: str,
    entity_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """实体详情 + 关联实体"""
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.owner_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise NotFoundError("知识库")

    detail = await get_entity(entity_name)
    if not detail:
        raise NotFoundError("实体")
    return APIResponse.success(detail)
