"""Celery Embedding 异步任务"""

from loguru import logger
from celery.utils.log import get_task_logger

from tasks.celery_app import celery_app

task_logger = get_task_logger(__name__)


def _get_db_session():
    from core.database import async_session_factory
    return async_session_factory()


@celery_app.task(name="embed_document", bind=True, max_retries=2, default_retry_delay=60)
def embed_document(self, doc_id: str):
    """异步 Embedding：读取解析结果 → 分块 → 向量化 → 写入 Milvus"""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        result = loop.run_until_complete(_async_embed(doc_id))
        return result
    except Exception as exc:
        task_logger.error(f"Embedding 任务失败 doc_id={doc_id}: {exc}")
        raise self.retry(exc=exc)


async def _async_embed(doc_id: str) -> dict:
    import json
    from sqlalchemy import select
    from models.models import Document
    from services.storage import storage_service
    from engine.rag.splitter import text_splitter
    from engine.rag.embedder import create_embedder
    from engine.rag.vector_store import vector_store
    from core.config import settings

    async with _get_db_session() as session:
        async with session.begin():
            result = await session.execute(
                select(Document).where(Document.id == doc_id)
            )
            doc = result.scalar_one_or_none()
            if not doc or doc.status != "ready":
                return {"status": "error", "error": "文档未就绪"}

            task_logger.info(f"开始 Embedding: doc_id={doc_id}")

            # 1. 读取解析结果 (Chunks JSON)
            try:
                chunks_json = await storage_service.download(f"chunks/{doc_id}.json")
                chunks_data = json.loads(chunks_json.decode("utf-8"))
            except Exception:
                task_logger.error(f"无法读取解析结果: doc_id={doc_id}")
                return {"status": "error", "error": "解析结果不存在"}

            from engine.parser.base import Chunk
            chunks = [Chunk.from_dict(c) for c in chunks_data]

            # 2. 文本分块
            split_chunks = text_splitter.split_documents(chunks)
            task_logger.info(f"分块完成: {len(chunks)} → {len(split_chunks)}")

            # 3. 向量化
            texts = [c["content"] for c in split_chunks]
            try:
                embedder = create_embedder(use_dummy_fallback=True)
                embeddings = await embedder.embed(texts)
            except Exception as e:
                task_logger.error(f"Embedding 模型加载失败: {e}")
                return {"status": "error", "error": f"Embedding 模型不可用: {e}"}

            # 4. 写入 Milvus
            try:
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
                vector_store.insert(records)
                task_logger.info(f"Milvus 写入完成: doc_id={doc_id}, count={len(records)}")
            except Exception as e:
                task_logger.warning(f"Milvus 写入失败（可能未启动）: {e}")
                return {"status": "partial", "error": str(e)}

            task_logger.info(f"Embedding 完成: doc_id={doc_id}")
            return {"status": "done", "chunks": len(split_chunks)}
