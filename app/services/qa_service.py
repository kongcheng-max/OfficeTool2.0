"""问答编排服务 — 检索 → 构建 Prompt → LLM 生成"""

import json
import uuid
from typing import AsyncIterator, Dict, List, Optional

from loguru import logger

from core.config import settings
from engine.llm.base import Message
from engine.llm.factory import LLMFactory
from engine.rag.embedder import create_embedder
from engine.rag.retriever import Retriever
from engine.rag.vector_store import vector_store

# 全局检索器实例（使用工厂函数，优先真实 Embedding）
_retriever = Retriever(
    embedder=create_embedder(use_dummy_fallback=True),
    store=vector_store,
)


PROMPT_TEMPLATE = """你是一个专业的文档问答助手。请根据以下参考资料回答用户的问题。

要求：
1. 只根据参考资料中的内容回答，不要编造信息
2. 如果参考资料不足以回答问题，请明确说明
3. 回答应清晰、准确、有条理
4. 如果涉及表格数据，请尽量保持结构化展示

{context}

用户问题：{question}

请回答："""


def _build_prompt(question: str, chunks: List[Dict]) -> List[Message]:
    """构建 Prompt 消息列表"""
    # 拼接上下文
    context_parts = []
    for i, hit in enumerate(chunks, 1):
        source = hit.get("metadata", {}).get("source", "未知")
        page = hit.get("metadata", {}).get("page", "")
        section = hit.get("metadata", {}).get("section", "")
        loc = f"来源: {source}"
        if page:
            loc += f", 第{page}页"
        if section:
            loc += f", {section}"
        context_parts.append(f"[文档{i}] {loc}\n{hit['chunk_text']}")

    context = "\n\n" + "\n\n---\n\n".join(context_parts) + "\n"

    return [
        Message(role="system", content=PROMPT_TEMPLATE.format(context=context, question=question)),
    ]


async def qa(
    question: str,
    kb_id: str,
    top_k: int = 10,
) -> dict:
    """单次问答（非流式）

    Args:
        question: 用户问题
        kb_id: 知识库 ID
        top_k: 检索数量

    Returns:
        {answer, sources[{document_id, document_name, chunk_text, page, score}], confidence}
    """
    # 1. 检索
    try:
        hits = await _retriever.retrieve(question, kb_id=kb_id, top_k=top_k)
    except Exception as e:
        logger.warning(f"向量检索失败（可能 Milvus 未启动）: {e}")
        hits = []

    # 2. 构建 Prompt
    messages = _build_prompt(question, hits)

    # 3. LLM 生成
    try:
        answer = await LLMFactory.generate_with_fallback(
            messages=[{"role": m.role, "content": m.content} for m in messages],
        )
    except Exception as e:
        logger.error(f"所有 LLM 不可用: {e}")
        # 兜底：返回检索结果
        answer = _fallback_answer(question, hits)

    # 4. 构建来源
    sources = []
    for hit in hits[:5]:
        sources.append({
            "document_id": hit.get("doc_id", ""),
            "document_name": hit.get("metadata", {}).get("source", ""),
            "chunk_text": hit.get("chunk_text", "")[:200],
            "page": hit.get("metadata", {}).get("page"),
            "score": round(hit.get("score", 0.0), 4),
        })

    confidence = 0.0
    if hits:
        confidence = round(hits[0].get("score", 0.0), 4)

    return {
        "answer": answer,
        "conversation_id": uuid.uuid4().hex[:12],
        "sources": sources,
        "confidence": confidence,
    }


async def qa_stream(
    question: str,
    kb_id: str,
    top_k: int = 10,
) -> AsyncIterator[str]:
    """流式问答（SSE）

    Yields:
        JSON 字符串：{"type":"chunk","text":"..."} 逐 token
        最后一条：{"type":"done","sources":[...],"confidence":...,"conversation_id":"..."}
    """
    import json as _json

    # 1. 检索
    try:
        hits = await _retriever.retrieve(question, kb_id=kb_id, top_k=top_k)
    except Exception:
        hits = []

    # 2. 构建来源信息（供 done 事件使用）
    sources = []
    for hit in hits[:5]:
        sources.append({
            "document_id": hit.get("doc_id", ""),
            "document_name": hit.get("metadata", {}).get("source", ""),
            "chunk_text": hit.get("chunk_text", "")[:200],
            "page": hit.get("metadata", {}).get("page"),
            "score": round(hit.get("score", 0.0), 4),
        })

    confidence = round(hits[0].get("score", 0.0), 4) if hits else 0.0
    conversation_id = uuid.uuid4().hex[:12]

    # 3. 构建 Prompt
    messages = _build_prompt(question, hits)

    # 4. LLM 流式生成 → 每个 token 包装为 JSON chunk
    try:
        llm = LLMFactory.create()
        async for token in llm.chat_stream(
            messages=messages,
        ):
            yield _json.dumps({"type": "chunk", "text": token}, ensure_ascii=False)
    except Exception as e:
        logger.error(f"LLM 流式失败: {e}")
        # 兜底
        fallback = _fallback_answer(question, hits)
        yield _json.dumps({"type": "chunk", "text": fallback}, ensure_ascii=False)

    # 5. 发送 done 事件（携带来源和置信度）
    yield _json.dumps({
        "type": "done",
        "sources": sources,
        "confidence": confidence,
        "conversation_id": conversation_id,
    }, ensure_ascii=False)


def _fallback_answer(question: str, hits: List[Dict]) -> str:
    """LLM 不可用时的兜底回答"""
    if not hits:
        return "抱歉，未能在知识库中找到相关信息。"

    parts = ["以下是与您问题最相关的内容摘要：\n\n"]
    for i, hit in enumerate(hits[:5], 1):
        source = hit.get("metadata", {}).get("source", "未知")
        parts.append(f"**来源 {i}** ({source}):\n{hit['chunk_text'][:500]}\n\n")

    parts.append("---\n*（LLM 服务暂不可用，以上为检索原始结果）*")
    return "".join(parts)
