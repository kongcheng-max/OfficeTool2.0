"""问答 API — 单次问答 + 流式 + 多轮对话 + 清除"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from core.database import get_db
from core.exceptions import NotFoundError
from core.response import APIResponse
from models.models import KnowledgeBase, User
from schemas.schemas import ChatRequest, ChatResponse, QARequest, QAResponse
from services.qa_service import chat, chat_stream, clear_conversation, qa, qa_stream

router = APIRouter(tags=["问答"])


# ====================================================================
# 单次问答 + 流式问答
# ====================================================================

@router.post("/api/v1/kb/{kb_id}/qa", response_model=APIResponse[QAResponse])
async def ask_question(
    kb_id: str,
    req: QARequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """单次问答 — 混合检索（向量+BM25+KG）→ RRF 融合 → LLM 生成"""
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.owner_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise NotFoundError("知识库")

    result = await qa(question=req.question, kb_id=kb_id)

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
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """流式问答（SSE）— text/event-stream 逐字输出"""
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
            # BUG-046: 客户端断开后停止 LLM 流，避免浪费 API 配额
            if await request.is_disconnected():
                logger.info(f"SSE 客户端断开，停止流式输出")
                break
            yield f"data: {chunk_json}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ====================================================================
# 多轮对话
# ====================================================================

@router.post("/api/v1/kb/{kb_id}/chat", response_model=APIResponse[ChatResponse])
async def chat_conversation(
    kb_id: str,
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """多轮对话 — 支持上下文追问

    首次对话不传 conversation_id，后续传入返回的 conversation_id 实现多轮记忆。
    最多保留 10 轮（20 条消息），1 小时无活动自动过期。
    """
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.owner_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise NotFoundError("知识库")

    result = await chat(
        question=req.question,
        kb_id=kb_id,
        conversation_id=req.conversation_id,
    )

    return APIResponse.success(
        ChatResponse(
            answer=result["answer"],
            conversation_id=result["conversation_id"],
            sources=result["sources"],
            confidence=result["confidence"],
            context_rounds=result.get("context_rounds", 0),
        )
    )


@router.post("/api/v1/kb/{kb_id}/chat/stream")
async def chat_conversation_stream(
    kb_id: str,
    req: ChatRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """多轮流式对话（SSE）"""
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.owner_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise NotFoundError("知识库")

    async def generate():
        async for chunk_json in chat_stream(
            question=req.question,
            kb_id=kb_id,
            conversation_id=req.conversation_id,
        ):
            # BUG-046: 客户端断开后停止 LLM 流
            if await request.is_disconnected():
                logger.info(f"SSE 客户端断开，停止多轮对话流式输出")
                break
            yield f"data: {chunk_json}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/api/v1/kb/{kb_id}/chat/{conv_id}", response_model=APIResponse)
async def clear_chat(
    kb_id: str,
    conv_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """清除指定多轮对话历史"""
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.owner_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise NotFoundError("知识库")

    await clear_conversation(conv_id)
    return APIResponse.success(message="对话历史已清除")


# BUG-049: 对话列表查询 API（从 Redis 恢复已知的对话 ID）
@router.get("/api/v1/kb/{kb_id}/conversations", response_model=APIResponse[list])
async def list_conversations(
    kb_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的对话列表（从 Redis）"""
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.owner_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise NotFoundError("知识库")

    # 从 Redis 扫描所有 conv:* 前缀的 key
    import json as _json
    from services.qa_service import _get_redis, _get_conversation_history

    r = await _get_redis()
    items = []
    if r:
        try:
            cursor = 0
            while True:
                cursor, keys = await r.scan(cursor, match="conv:*", count=100)
                for key in keys:
                    try:
                        data = await r.get(key)
                        if data:
                            conv = _json.loads(data)
                            conv_id = key.decode("utf-8").replace("conv:", "")
                            first_msg = conv[0]["content"][:60] if conv else "(空)"
                            items.append({
                                "id": conv_id[:20],
                                "title": first_msg,
                                "message_count": len(conv),
                            })
                    except Exception:
                        pass
                if cursor == 0:
                    break
        except Exception:
            pass

    return APIResponse.success(items)
