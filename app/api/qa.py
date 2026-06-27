"""问答 API — 单次问答 + 流式问答"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from core.database import get_db
from core.exceptions import NotFoundError
from core.response import APIResponse
from models.models import KnowledgeBase, User
from schemas.schemas import QARequest, QAResponse
from services.qa_service import qa, qa_stream

router = APIRouter(tags=["问答"])


@router.post("/api/v1/kb/{kb_id}/qa", response_model=APIResponse[QAResponse])
async def ask_question(
    kb_id: str,
    req: QARequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """单次问答"""
    # 验证知识库存在且当前用户有访问权限
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.owner_id == current_user.id,
        )
    )
    kb = result.scalar_one_or_none()
    if not kb:
        raise NotFoundError("知识库")

    result = await qa(
        question=req.question,
        kb_id=kb_id,
    )

    return APIResponse.success(
        QAResponse(
            answer=result["answer"],
            conversation_id=result["conversation_id"],
            sources=result["sources"],
            confidence=result["confidence"],
        )
    )


@router.post("/api/v1/kb/{kb_id}/qa/stream")
async def ask_question_stream(
    kb_id: str,
    req: QARequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """流式问答（SSE）

    返回 text/event-stream，前端逐字展示。
    """
    # 验证知识库存在且当前用户有访问权限
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.owner_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise NotFoundError("知识库")

    async def generate():
        async for chunk_json in qa_stream(question=req.question, kb_id=kb_id):
            # qa_stream 现在产出 JSON 字符串，直接包装为 SSE data 行
            yield f"data: {chunk_json}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
