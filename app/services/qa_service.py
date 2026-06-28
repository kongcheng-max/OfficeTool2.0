"""问答编排服务 — 混合检索 → 构建 Prompt → LLM 生成 → 多轮对话"""

import json
import uuid
from typing import Any, AsyncIterator, Dict, List, Optional

from loguru import logger

from core.config import settings
from engine.llm.base import Message
from engine.llm.factory import LLMFactory
from engine.rag.embedder import create_embedder
from engine.rag.retriever import (
    BM25Retriever,
    HybridRetriever,
    KGRetriever,
    Retriever,
)
from engine.rag.vector_store import vector_store

# ========================================================================
# 全局检索器（三路混合检索：向量 + BM25 + KG）
# ========================================================================

_hybrid_retriever = HybridRetriever(
    vector_retriever=Retriever(
        embedder=create_embedder(use_dummy_fallback=True),
        store=vector_store,
    ),
    bm25_retriever=BM25Retriever(),
    kg_retriever=KGRetriever(),
)

# ========================================================================
# Redis 多轮对话存储
# ========================================================================

_conversation_redis = None  # None=未初始化, False=不可用

async def _get_redis():
    """延迟初始化 Redis 连接（首次调用时连接，失败则标记为不可用）"""
    global _conversation_redis
    import redis.asyncio as aioredis

    # None = 尚未尝试连接
    if _conversation_redis is None:
        try:
            _conversation_redis = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=3,
            )
            await _conversation_redis.ping()
            logger.info("Redis 多轮对话存储已连接")
        except Exception as e:
            logger.warning(f"Redis 不可用，多轮对话将仅返回单次结果: {e}")
            _conversation_redis = False  # False = 已确认不可用
    # False = 不可用
    if _conversation_redis is False:
        return None
    return _conversation_redis


CONVERSATION_TTL = 3600       # 对话历史 1 小时过期
MAX_HISTORY_MESSAGES = 20     # 最多保留 20 条消息（10 轮）


async def _get_conversation_history(conv_id: str) -> List[Message]:
    """从 Redis 读取多轮对话历史"""
    r = await _get_redis()
    if not r:
        return []
    try:
        data = await r.get(f"conv:{conv_id}")
        if data:
            records = json.loads(data)
            return [Message(role=m["role"], content=m["content"]) for m in records]
    except Exception as e:
        logger.warning(f"读取对话历史失败: {e}")
    return []


async def _save_conversation(conv_id: str, messages: List[Message]):
    """保存多轮对话历史到 Redis"""
    r = await _get_redis()
    if not r:
        return
    try:
        trimmed = messages[-MAX_HISTORY_MESSAGES:]  # 裁剪
        records = [{"role": m.role, "content": m.content} for m in trimmed]
        await r.setex(
            f"conv:{conv_id}",
            CONVERSATION_TTL,
            json.dumps(records, ensure_ascii=False),
        )
    except Exception as e:
        logger.warning(f"保存对话历史失败: {e}")


async def _delete_conversation(conv_id: str):
    """删除对话历史（用户主动清除时调用）"""
    r = await _get_redis()
    if not r:
        return
    try:
        await r.delete(f"conv:{conv_id}")
    except Exception:
        pass

# ========================================================================
# Prompt 模板
# ========================================================================

SYSTEM_PROMPT_QA = """你是一个专业的文档问答助手。请根据以下参考资料回答用户的问题。

要求：
1. 只根据参考资料中的内容回答，不要编造信息
2. 如果参考资料不足以回答问题，请明确说明
3. 回答应清晰、准确、有条理
4. 如果涉及表格数据，请尽量保持结构化展示
5. 在回答末尾列出引用的来源编号

{context}

用户问题：{question}

请回答："""

SYSTEM_PROMPT_CHAT = """你是一个专业的文档问答助手。请根据以下参考资料和对话历史回答用户的问题。

要求：
1. 只根据参考资料中的内容回答，不要编造信息
2. 如果参考资料不足以回答问题，请明确说明
3. 回答应清晰、准确、有条理，注意与对话历史的连贯性
4. 如果涉及表格数据，请尽量保持结构化展示
5. 在回答末尾列出引用的来源编号

{context}

用户问题：{question}

请回答："""

# ========================================================================
# Helper: 构建 Prompt + 答案溯源
# ========================================================================

def _build_prompt_context(chunks: List[Dict]) -> str:
    """将检索结果拼接为上下文"""
    parts = []
    for i, hit in enumerate(chunks, 1):
        meta = hit.get("metadata", {})
        source = meta.get("source", "未知文档")
        page = meta.get("page")
        section = meta.get("section")
        sources = hit.get("sources", [])
        src_tag = f" [{'/'.join(sources)}]" if sources else ""

        loc = f"来源: {source}"
        if page:
            loc += f", 第{page}页"
        if section:
            loc += f", {section}"
        loc += src_tag

        parts.append(f"[文档{i}] {loc}\n{hit['chunk_text']}")

    return "\n\n---\n\n".join(parts)


def _build_prompt_messages(
    question: str,
    chunks: List[Dict],
    history: Optional[List[Message]] = None,
) -> List[Message]:
    """构建 Prompt 消息列表"""
    context = _build_prompt_context(chunks)
    template = SYSTEM_PROMPT_CHAT if history else SYSTEM_PROMPT_QA
    system_content = template.format(context=context, question=question)
    messages = [Message(role="system", content=system_content)]
    if history:
        messages = history + messages
    return messages


def _build_sources(hits: List[Dict], max_sources: int = 5) -> List[Dict]:
    """构建答案溯源列表

    每个来源包含:
      - document_id: 文档 ID
      - document_name: 原始文件名
      - chunk_text: 原文片段（完整，供前端展示）
      - page: 页码（如有）
      - section: 章节（如有）
      - score: RRF 融合分或原始检索分
      - sources: 命中通路 ["vector","bm25","kg"]
      - chunk_index: 块序号
    """
    sources = []
    for hit in hits[:max_sources]:
        meta = hit.get("metadata", {})
        sources.append({
            "document_id": hit.get("doc_id", ""),
            "document_name": meta.get("source", ""),
            "chunk_text": hit.get("chunk_text", ""),
            "page": meta.get("page"),
            "section": meta.get("section"),
            "score": round(hit.get("rrf_score", hit.get("score", 0.0)), 4),
            "sources": hit.get("sources", []),
            "chunk_index": meta.get("chunk_index"),
        })
    return sources


def _compute_confidence(hits: List[Dict]) -> float:
    """计算答案置信度

    基于 Top-3 RRF 分加权平均。
    """
    if not hits:
        return 0.0
    top_scores = [h.get("rrf_score", h.get("score", 0.0)) for h in hits[:3]]
    avg = sum(top_scores) / len(top_scores)
    return round(avg, 4)


async def _retrieve(
    question: str,
    kb_id: str,
    top_k: int = 10,
    use_kg: bool = True,
) -> List[Dict]:
    """统一检索入口，外部异常全兜底"""
    try:
        result = await _hybrid_retriever.retrieve(
            question, kb_id=kb_id, top_k=top_k, use_kg=use_kg,
        )
        hits = result["hits"]
        total_sources = result.get("total_sources", {})
        logger.info(
            f"混合检索完成: query='{question[:50]}...' hits={len(hits)}"
            f" sources={total_sources}"
        )
        return hits
    except Exception as e:
        logger.warning(f"混合检索失败，降级为空列表: {e}")
        return []

# ========================================================================
# 公开 API: qa / qa_stream / chat / clear_conversation
# ========================================================================

async def qa(
    question: str,
    kb_id: str,
    top_k: int = 10,
    use_kg: bool = True,
) -> dict:
    """单次问答（非流式）

    Returns:
        {answer, conversation_id, sources, confidence}
    """
    # 1. 混合检索
    hits = await _retrieve(question, kb_id, top_k=top_k, use_kg=use_kg)

    # 2. 构建 Prompt
    messages = _build_prompt_messages(question, hits)

    # 3. LLM 生成
    try:
        answer = await LLMFactory.generate_with_fallback(
            messages=[{"role": m.role, "content": m.content} for m in messages],
        )
    except Exception as e:
        logger.error(f"LLM 不可用: {e}")
        answer = _fallback_answer(question, hits)

    return {
        "answer": answer,
        "conversation_id": uuid.uuid4().hex[:12],
        "sources": _build_sources(hits),
        "confidence": _compute_confidence(hits),
    }


async def qa_stream(
    question: str,
    kb_id: str,
    top_k: int = 10,
    use_kg: bool = True,
) -> AsyncIterator[str]:
    """流式问答（SSE）

    Yields:
        {"type":"chunk","text":"..."}  逐 token
        {"type":"done","sources":[...],"confidence":...,"conversation_id":"..."}
    """
    import json as _json

    # 1. 混合检索
    hits = await _retrieve(question, kb_id, top_k=top_k, use_kg=use_kg)

    sources = _build_sources(hits)
    confidence = _compute_confidence(hits)
    conversation_id = uuid.uuid4().hex[:12]

    # 2. 构建 Prompt
    messages = _build_prompt_messages(question, hits)

    # 3. LLM 流式 → JSON 包装
    try:
        llm = LLMFactory.create()
        async for token in llm.chat_stream(messages=messages):
            yield _json.dumps({"type": "chunk", "text": token}, ensure_ascii=False)
    except Exception as e:
        logger.error(f"LLM 流式失败: {e}")
        yield _json.dumps(
            {"type": "chunk", "text": _fallback_answer(question, hits)},
            ensure_ascii=False,
        )

    # 4. 发送 done 事件
    yield _json.dumps({
        "type": "done",
        "sources": sources,
        "confidence": confidence,
        "conversation_id": conversation_id,
    }, ensure_ascii=False)


async def chat(
    question: str,
    kb_id: str,
    conversation_id: Optional[str] = None,
    top_k: int = 10,
    use_kg: bool = True,
) -> dict:
    """多轮对话（非流式）

    Args:
        question: 用户问题
        kb_id: 知识库 ID
        conversation_id: 对话 ID（None = 新建对话）
        top_k: 检索数量
        use_kg: 是否启用图谱检索

    Returns:
        {answer, conversation_id, sources, confidence, context_rounds}
    """
    # 1. 读取历史
    history: List[Message] = []
    if conversation_id:
        history = await _get_conversation_history(conversation_id)

    # 2. 混合检索
    hits = await _retrieve(question, kb_id, top_k=top_k, use_kg=use_kg)

    # 3. 构建 Prompt（含历史）
    messages = _build_prompt_messages(question, hits, history)

    # 4. LLM 生成
    try:
        answer = await LLMFactory.generate_with_fallback(
            messages=[{"role": m.role, "content": m.content} for m in messages],
        )
    except Exception as e:
        logger.error(f"LLM 不可用: {e}")
        answer = _fallback_answer(question, hits)

    # 5. 保存对话历史
    conv_id = conversation_id or uuid.uuid4().hex[:12]
    updated = history + [
        Message(role="user", content=question),
        Message(role="assistant", content=answer),
    ]
    await _save_conversation(conv_id, updated)

    return {
        "answer": answer,
        "conversation_id": conv_id,
        "sources": _build_sources(hits),
        "confidence": _compute_confidence(hits),
        "context_rounds": len(history) // 2,
    }


async def chat_stream(
    question: str,
    kb_id: str,
    conversation_id: Optional[str] = None,
    top_k: int = 10,
    use_kg: bool = True,
) -> AsyncIterator[str]:
    """多轮流式对话（SSE）

    Args:
        question: 用户问题
        kb_id: 知识库 ID
        conversation_id: 对话 ID（None = 新建对话）
        top_k: 检索数量
        use_kg: 是否启用图谱检索

    Yields:
        {"type":"chunk","text":"..."}  逐 token
        {"type":"done","sources":[...],"confidence":...,"conversation_id":"..."}
    """
    import json as _json

    # 1. 读取历史
    history: List[Message] = []
    if conversation_id:
        history = await _get_conversation_history(conversation_id)

    # 2. 混合检索
    hits = await _retrieve(question, kb_id, top_k=top_k, use_kg=use_kg)

    sources = _build_sources(hits)
    confidence = _compute_confidence(hits)

    # 3. 构建 Prompt（含历史）
    messages = _build_prompt_messages(question, hits, history)

    # 4. LLM 流式 → JSON 包装
    full_answer = ""
    try:
        llm = LLMFactory.create()
        async for token in llm.chat_stream(messages=messages):
            full_answer += token
            yield _json.dumps({"type": "chunk", "text": token}, ensure_ascii=False)
    except Exception as e:
        logger.error(f"LLM 流式失败: {e}")
        fallback = _fallback_answer(question, hits)
        full_answer = fallback
        yield _json.dumps(
            {"type": "chunk", "text": fallback},
            ensure_ascii=False,
        )

    # 5. 保存对话历史
    conv_id = conversation_id or uuid.uuid4().hex[:12]
    updated = history + [
        Message(role="user", content=question),
        Message(role="assistant", content=full_answer),
    ]
    await _save_conversation(conv_id, updated)

    # 6. 发送 done 事件（含 conversation_id）
    yield _json.dumps({
        "type": "done",
        "sources": sources,
        "confidence": confidence,
        "conversation_id": conv_id,
    }, ensure_ascii=False)


async def clear_conversation(conv_id: str) -> bool:
    """清除指定对话历史"""
    await _delete_conversation(conv_id)
    return True


def _fallback_answer(question: str, hits: List[Dict]) -> str:
    """LLM 不可用时的兜底"""
    if not hits:
        return "抱歉，未能在知识库中找到与您问题相关的信息。请尝试更换关键词或上传更多文档。"

    parts = [f"以下是与「{question}」最相关的内容（LLM 暂不可用，展示检索原始结果）：\n"]
    for i, hit in enumerate(hits[:5], 1):
        meta = hit.get("metadata", {})
        source = meta.get("source", "未知")
        page = meta.get("page", "")
        score = hit.get("rrf_score", hit.get("score", 0.0))
        src_str = f"**来源 {i}** — {source}"
        if page:
            src_str += f" 第{page}页"
        src_str += f" (分数: {round(score, 4)})"
        parts.append(f"{src_str}\n> {hit['chunk_text'][:500]}\n")

    parts.append(f"\n*共检索到 {len(hits)} 个结果*")
    return "\n".join(parts)
