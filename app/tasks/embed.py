"""Celery Embedding 异步任务 — 使用 safe-asyncio 模式避免 event loop 冲突

方案：Celery task 内部使用与 _run_parse_sync 相同的安全 event loop 模式，
不再依赖 run_async_in_worker。同时提供 run_embed_sync 供轻量化模式直接调用。
"""

import asyncio
import concurrent.futures
import json

from loguru import logger
from celery.utils.log import get_task_logger

from tasks.celery_app import celery_app

task_logger = get_task_logger(__name__)


def _get_db_session():
    from core.database import async_session_factory
    return async_session_factory()


# ═══════════════════════════════════════════════════════════════
# 安全 asyncio 执行器（复刻 _run_parse_sync 的模式）
# ═══════════════════════════════════════════════════════════════

def _run_async_safe(coro) -> dict:
    """在任意上下文中安全执行 async 协程，避免 event loop 冲突

    与 document_service._run_parse_sync 使用相同的模式：
    - 当前线程无 event loop → asyncio.run()
    - 当前线程已有 running loop → ThreadPoolExecutor + asyncio.run()
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result(timeout=600)
    else:
        return asyncio.run(coro)


# ═══════════════════════════════════════════════════════════════
# Celery 任务入口 — 直接走安全 async 路径，不再用 run_async_in_worker
# ═══════════════════════════════════════════════════════════════

@celery_app.task(name="embed_document", bind=True, max_retries=2, default_retry_delay=10)
def embed_document(self, doc_id: str):
    """Embedding 任务 — 使用安全 event loop 模式执行

    不再经过 run_async_in_worker（会在 Celery thread-pool 中触发
    "Future attached to a different loop" 错误），而是用与 parse 同步回退
    相同的 _run_async_safe 模式。
    """
    try:
        return _run_async_safe(_async_embed(doc_id))
    except Exception as exc:
        task_logger.error(f"Embedding 任务失败 doc_id={doc_id}: {exc}")
        raise self.retry(exc=exc)


# ═══════════════════════════════════════════════════════════════
# 同步入口（轻量化部署 / 其他模块直接调用）
# ═══════════════════════════════════════════════════════════════

def run_embed_sync(doc_id: str) -> dict:
    """Embedding 同步入口 — 适用于轻量化模式或无 Celery 环境

    直接复用 _run_async_safe，与 embed_document task 完全一致的执行路径。
    """
    return _run_async_safe(_async_embed(doc_id))


# ═══════════════════════════════════════════════════════════════
# 异步实现（核心逻辑，唯一维护点）
# ═══════════════════════════════════════════════════════════════

async def _async_embed(doc_id: str) -> dict:
    """Embedding 核心逻辑：读解析结果 → 分块 → 向量化 → 写 Milvus + ES"""
    from sqlalchemy import select
    from models.models import Document
    from services.storage import storage_service
    from engine.rag.splitter import text_splitter
    from engine.rag.embedder import create_embedder
    from engine.rag.vector_store import vector_store

    async with _get_db_session() as session:
        async with session.begin():
            result = await session.execute(
                select(Document).where(Document.id == doc_id)
            )
            doc = result.scalar_one_or_none()
            # BUG-066: 接受 parsed（解析完成但尚未嵌入）和 ready（已完成嵌入）
            if not doc or doc.status not in ("parsed", "ready"):
                return {"status": "error", "error": "文档未就绪（状态不匹配）"}

            task_logger.info(f"Embedding 开始: doc_id={doc_id}")

            # 1. 读取解析结果
            try:
                chunks_json = await storage_service.download(f"chunks/{doc_id}.json")
                chunks_data = json.loads(chunks_json.decode("utf-8"))
            except Exception:
                task_logger.error(f"Embedding — 无法读取解析结果: doc_id={doc_id}")
                return {"status": "error", "error": "解析结果不存在"}

            from engine.parser.base import Chunk
            chunks = [Chunk.from_dict(c) for c in chunks_data]

            # 2. 文本分块
            split_chunks = text_splitter.split_documents(chunks)
            task_logger.info(f"Embedding 分块: {len(chunks)} → {len(split_chunks)}")

            # 3. 向量化
            texts = [c["content"] for c in split_chunks]
            try:
                embedder = create_embedder(use_dummy_fallback=True)
                embeddings = await embedder.embed(texts)
            except Exception as e:
                task_logger.error(f"Embedding 模型加载失败: {e}")
                return {"status": "error", "error": f"Embedding 模型不可用: {e}"}

            # 4. 写入 Milvus
            records = []
            for i, chunk in enumerate(split_chunks):
                records.append({
                    "doc_id": doc.id,
                    "kb_id": doc.kb_id,
                    "chunk_text": chunk["content"],
                    "chunk_index": chunk["metadata"].get("chunk_index", i),
                    "metadata_json": json.dumps(chunk["metadata"], ensure_ascii=False),
                    "embedding": embeddings[i],
                })

            milvus_ok = False
            try:
                vector_store.insert(records)
                task_logger.info(f"Embedding — Milvus 写入: doc_id={doc_id}, count={len(records)}")
                milvus_ok = True
            except Exception as e:
                task_logger.warning(f"Embedding — Milvus 写入失败（可能未启动/轻量化模式）: {e}")

            # 5. 写入 ES
            try:
                from engine.rag.es_store import es_store
                await es_store.index_chunks(records)
                task_logger.info(f"Embedding — ES 写入: doc_id={doc_id}")
            except Exception as e:
                task_logger.warning(f"Embedding — ES 写入失败（可能未启动/轻量化模式）: {e}")

            # BUG-066: Embedding 成功后设 ready，前端才显示「就绪」
            doc.status = "ready"
            doc.error_message = ""
            session.add(doc)

            task_logger.info(f"Embedding 完成: doc_id={doc_id}")
            status = "done" if milvus_ok else "partial"
            return {"status": status, "chunks": len(split_chunks)}
