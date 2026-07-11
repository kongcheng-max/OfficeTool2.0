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
# 全局检索器（三路混合检索：向量 + BM25 + KG）— 懒加载，首次调用时初始化
# ========================================================================

_hybrid_retriever: Optional[HybridRetriever] = None


def _get_hybrid_retriever() -> HybridRetriever:
    """懒加载混合检索器（延迟 Embedder 模型加载到首次使用）"""
    global _hybrid_retriever
    if _hybrid_retriever is None:
        _hybrid_retriever = HybridRetriever(
            vector_retriever=Retriever(
                embedder=create_embedder(use_dummy_fallback=True),
                store=vector_store,
            ),
            bm25_retriever=BM25Retriever(),
            kg_retriever=KGRetriever(),
        )
    return _hybrid_retriever

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

NO_RESULTS_ANSWER = (
    "知识库中未找到与您问题相关的文档内容。"
    "可能的原因：\n"
    "1. 相关文档尚未上传或正在解析中\n"
    "2. 文档已上传但 Embedding 索引尚未完成（请稍后重试）\n"
    "3. 尝试更换关键词或上传包含相关内容的文档"
)

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

{context}"""

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
    """构建 Prompt 消息列表

    BUG-068: 多轮对话时把当前提问作为独立的 user 消息放在末尾，
    确保模型正确响应最新提问（而非历史中的旧话题）。
    """
    context = _build_prompt_context(chunks)

    if history:
        # system（开头）：上下文 + 指令 + 参考资料（提问已在末尾 user 中）
        system_content = SYSTEM_PROMPT_CHAT.format(context=context)
        # 历史对话 + 当前提问（末尾 user）
        messages = [Message(role="system", content=system_content)]
        messages += history
        messages.append(Message(role="user", content=question))
    else:
        # 无历史：system 中包含 question，保持简洁
        system_content = SYSTEM_PROMPT_QA.format(context=context, question=question)
        messages = [Message(role="system", content=system_content)]
        messages.append(Message(role="user", content=question))

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
    """统一检索入口 — 含查询改写扩展 (W9.6)"""
    try:
        # W9.6: 查询改写 — 生成变体扩展召回
        from engine.rag.query_rewriter import query_rewriter
        variants = await query_rewriter.rewrite(question, max_variants=2)

        # 首次检索（原始查询）
        result = await _get_hybrid_retriever().retrieve(
            question, kb_id=kb_id, top_k=top_k, use_kg=use_kg,
        )
        all_hits = {self._hit_key(h): h for h in result["hits"]}
        total_sources = dict(result.get("total_sources", {}))

        # 变体扩展检索（仅 BM25，快速且互补）
        if len(variants) > 1:
            for v in variants[1:]:
                try:
                    from engine.rag.retriever import BM25Retriever
                    bm25 = BM25Retriever()
                    extra = await bm25.retrieve(v, kb_id=kb_id, top_k=5)
                    for h in extra:
                        k = self._hit_key(h)
                        if k not in all_hits:
                            all_hits[k] = h
                except Exception:
                    pass  # BM25 不可用时跳过

        hits = list(all_hits.values())

        # W9.5 / BUG-069: Cross-encoder 精排（RRF 融合后二次排序）
        if len(hits) > 1:
            try:
                from engine.rag.reranker import cross_encoder_rerank
                # 为 variant hits 补默认 rrf_score
                for h in hits:
                    if "rrf_score" not in h:
                        h["rrf_score"] = h.get("score", 0.0)
                hits = await cross_encoder_rerank(question, hits, top_k=top_k)
                logger.info(
                    f"Cross-encoder 精排完成: query='{question[:50]}...' "
                    f"final_hits={len(hits)}"
                )
            except Exception as e:
                logger.warning(f"Cross-encoder 精排跳过: {e}")

        logger.info(
            f"混合检索完成: query='{question[:50]}...' variants={len(variants)} "
            f"hits={len(hits)} sources={total_sources}"
        )
        return hits
    except Exception as e:
        logger.warning(f"混合检索失败，降级为空列表: {e}")
        return []

@staticmethod
def _hit_key(hit: Dict) -> str:
    """检索结果去重 key"""
    return f"{hit.get('doc_id', '')}|{hit.get('chunk_text', '')[:80]}"

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
    # W10.1: 检查 LLM 答案缓存（相同问题 1h 内直接返回）
    from services.qa_cache import qa_cache as _qa_cache
    cached = await _qa_cache.get(kb_id, question)
    if cached:
        return cached

    # 1. 混合检索
    hits = await _retrieve(question, kb_id, top_k=top_k, use_kg=use_kg)

    # BUG-064 P2: 检索零结果时直接返回，不浪费 LLM 调用
    if not hits:
        return {
            "answer": NO_RESULTS_ANSWER,
            "conversation_id": uuid.uuid4().hex[:12],
            "sources": [],
            "confidence": 0.0,
        }

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

    result = {
        "answer": answer,
        "conversation_id": uuid.uuid4().hex[:12],
        "sources": _build_sources(hits),
        "confidence": _compute_confidence(hits),
    }

    # W10.1: 写入缓存（仅正常回答，零结果不缓存）
    if hits:
        await _qa_cache.set(kb_id, question, result)

    return result


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

    # BUG-064 P2: 检索零结果时直接返回提示，不走 LLM
    if not hits:
        yield _json.dumps(
            {"type": "chunk", "text": NO_RESULTS_ANSWER},
            ensure_ascii=False,
        )
        yield _json.dumps({
            "type": "done",
            "sources": [],
            "confidence": 0.0,
            "conversation_id": conversation_id,
        }, ensure_ascii=False)
        return

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

    # BUG-064 P2: 检索零结果时直接返回
    if not hits:
        return {
            "answer": NO_RESULTS_ANSWER,
            "conversation_id": conversation_id or uuid.uuid4().hex[:12],
            "sources": [],
            "confidence": 0.0,
            "context_rounds": len(history) // 2,
        }

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
    conv_id = conversation_id or uuid.uuid4().hex[:12]

    # BUG-064 P2: 检索零结果时直接返回提示，不走 LLM
    if not hits:
        yield _json.dumps(
            {"type": "chunk", "text": NO_RESULTS_ANSWER},
            ensure_ascii=False,
        )
        yield _json.dumps({
            "type": "done",
            "sources": [],
            "confidence": 0.0,
            "conversation_id": conv_id,
        }, ensure_ascii=False)
        return

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
