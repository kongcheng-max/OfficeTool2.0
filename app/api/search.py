"""搜索 API — 语义搜索 + 混合搜索（含完整溯源）"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from core.database import get_db
from core.exceptions import NotFoundError
from core.response import APIResponse
from models.models import KnowledgeBase, User
from services.qa_service import _hybrid_retriever

router = APIRouter(prefix="/api/v1/kb/{kb_id}/search", tags=["搜索"])


def _hit_to_result(hit: dict) -> dict:
    """将检索命中转为标准溯源格式"""
    meta = hit.get("metadata", {})
    return {
        "document_id": hit.get("doc_id", ""),
        "document_name": meta.get("source", ""),
        "chunk_text": hit.get("chunk_text", ""),
        "page": meta.get("page"),
        "section": meta.get("section"),
        "score": round(hit.get("rrf_score", hit.get("score", 0.0)), 4),
        "sources": hit.get("sources", []),
        "chunk_index": meta.get("chunk_index"),
    }


@router.get("", response_model=APIResponse[list])
async def search(
    kb_id: str,
    q: str = Query(..., description="搜索关键词"),
    top_k: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """向量语义搜索（仅 Milvus 向量通路）"""
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.owner_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise NotFoundError("知识库")

    hits = await _hybrid_retriever.vector.retrieve(q, kb_id=kb_id, top_k=top_k)
    results = [_hit_to_result(h) for h in hits]
    return APIResponse.success(results)


@router.get("/hybrid", response_model=APIResponse[list])
async def hybrid_search(
    kb_id: str,
    q: str = Query(..., description="搜索关键词"),
    top_k: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """混合搜索 — 向量 + BM25 + 知识图谱 三路 → RRF 融合

    每条结果包含完整溯源：文档名、页码、章节、分数、命中通路。
    """
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.owner_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise NotFoundError("知识库")

    result = await _hybrid_retriever.retrieve(q, kb_id=kb_id, top_k=top_k, use_kg=True)
    hits = result["hits"]
    total_sources = result.get("total_sources", {})

    results = [_hit_to_result(h) for h in hits]

    return APIResponse.success({
        "items": results,
        "total": len(results),
        "total_sources": total_sources,
        "query": q,
    })
