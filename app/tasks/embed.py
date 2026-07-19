"""Celery embedding tasks."""

import asyncio
import concurrent.futures
import json

from celery.utils.log import get_task_logger

from tasks.celery_app import celery_app

task_logger = get_task_logger(__name__)


def _get_db_session():
    from core.database import async_session_factory

    return async_session_factory()


def _ensure_windows_selector_event_loop():
    if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def _run_async_safe(coro) -> dict:
    """Run an async coroutine safely from Celery threads and Windows dev scripts."""
    _ensure_windows_selector_event_loop()

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_run_coroutine_in_new_loop, coro)
            return future.result(timeout=600)
    return _run_coroutine_in_new_loop(coro)


def _run_coroutine_in_new_loop(coro):
    _ensure_windows_selector_event_loop()
    return asyncio.run(coro)


@celery_app.task(name="embed_document", bind=True, max_retries=2, default_retry_delay=10)
def embed_document(self, doc_id: str):
    """Index one parsed document into vector and keyword stores."""
    try:
        return _run_async_safe(_async_embed(doc_id))
    except Exception as exc:
        task_logger.error(f"Embedding task failed doc_id={doc_id}: {exc}")
        raise self.retry(exc=exc)


def run_embed_sync(doc_id: str) -> dict:
    """Synchronous entry point for environments without a running worker."""
    return _run_async_safe(_async_embed(doc_id))


async def _async_embed(doc_id: str) -> dict:
    """Read parsed chunks, embed them, write Milvus/ES, and mark the document ready."""
    from sqlalchemy import select

    from engine.parser.base import Chunk
    from engine.rag.embedder import create_embedder
    from engine.rag.splitter import text_splitter
    from engine.rag.vector_store import vector_store
    from models.models import Document
    from services.storage import storage_service

    async with _get_db_session() as session:
        async with session.begin():
            result = await session.execute(select(Document).where(Document.id == doc_id))
            doc = result.scalar_one_or_none()
            if not doc or doc.status not in ("parsed", "ready"):
                return {"status": "error", "error": "document is not parsed"}

            task_logger.info(f"Embedding started: doc_id={doc_id}")

            try:
                chunks_json = await storage_service.download(f"chunks/{doc_id}.json")
                chunks_data = json.loads(chunks_json.decode("utf-8"))
            except Exception:
                task_logger.error(f"Embedding cannot read chunks: doc_id={doc_id}")
                return {"status": "error", "error": "parsed chunks not found"}

            chunks = [Chunk.from_dict(c) for c in chunks_data]
            split_chunks = text_splitter.split_documents(chunks)
            task_logger.info(
                f"Embedding split chunks: doc_id={doc_id}, {len(chunks)} -> {len(split_chunks)}"
            )

            texts = [c["content"] for c in split_chunks]
            try:
                embedder = create_embedder(use_dummy_fallback=True)
                embeddings = await embedder.embed(texts)
            except Exception as e:
                task_logger.error(f"Embedding model unavailable: {e}")
                return {"status": "error", "error": f"embedding model unavailable: {e}"}

            records = []
            for i, chunk in enumerate(split_chunks):
                records.append(
                    {
                        "doc_id": doc.id,
                        "kb_id": doc.kb_id,
                        "chunk_text": chunk["content"],
                        "chunk_index": chunk["metadata"].get("chunk_index", i),
                        "metadata_json": json.dumps(chunk["metadata"], ensure_ascii=False),
                        "embedding": embeddings[i],
                    }
                )

            milvus_ok = False
            try:
                vector_store.insert(records)
                task_logger.info(
                    f"Embedding wrote Milvus: doc_id={doc_id}, count={len(records)}"
                )
                milvus_ok = True
            except Exception as e:
                task_logger.warning(f"Embedding skipped Milvus write: {e}")

            try:
                from engine.rag.es_store import es_store

                await es_store.index_chunks(records)
                task_logger.info(f"Embedding wrote Elasticsearch: doc_id={doc_id}")
            except Exception as e:
                task_logger.warning(f"Embedding skipped Elasticsearch write: {e}")

            doc.status = "ready"
            doc.error_message = ""
            session.add(doc)

            task_logger.info(f"Embedding finished: doc_id={doc_id}")
            return {"status": "done" if milvus_ok else "partial", "chunks": len(split_chunks)}
