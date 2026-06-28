"""Celery 异步解析任务"""

import json
import os
import tempfile

from loguru import logger
from celery.utils.log import get_task_logger

from tasks.celery_app import celery_app
from engine.parser.base import Chunk, ParserRegistry

task_logger = get_task_logger(__name__)

# 解析器在 engine.parser 包导入时自动注册（见 engine/parser/__init__.py）
# ParserRegistry.register() 是幂等的，重复调用不会产生副作用


def _get_db_session():
    """延迟导入数据库会话"""
    from core.database import async_session_factory
    return async_session_factory()


@celery_app.task(name="parse_document", bind=True, max_retries=3, default_retry_delay=30)
def parse_document(self, doc_id: str):
    """异步解析文档"""
    from tasks.celery_app import run_async_in_worker
    try:
        return run_async_in_worker(lambda: _async_parse(doc_id))
    except Exception as exc:
        task_logger.error(f"解析任务失败 doc_id={doc_id}: {exc}")
        raise self.retry(exc=exc)


async def _async_parse(doc_id: str) -> dict:
    """异步解析主逻辑"""
    from sqlalchemy import select
    from models.models import Document, KnowledgeBase
    from services.storage import storage_service
    from engine.parser.base import ParserRegistry

    async with _get_db_session() as session:
        async with session.begin():
            # 查询文档
            result = await session.execute(
                select(Document).where(Document.id == doc_id)
            )
            doc = result.scalar_one_or_none()
            if not doc:
                return {"status": "error", "error": "文档不存在"}

            # 更新状态为 processing
            doc.status = "processing"
            await session.flush()

            # 下载文件到临时目录
            with tempfile.NamedTemporaryFile(
                suffix=os.path.splitext(doc.original_filename)[1],
                delete=False,
            ) as tmp:
                try:
                    file_data = await storage_service.download(doc.file_path)
                except Exception:
                    # 降级：从本地读取
                    with open(doc.file_path, "rb") as f:
                        file_data = f.read()
                tmp.write(file_data)
                tmp_path = tmp.name

            try:
                # 匹配解析器
                parser = ParserRegistry.find_for(
                    doc.original_filename, doc.mime_type
                )
                if not parser:
                    doc.status = "failed"
                    doc.error_message = f"不支持的格式: {doc.original_filename}"
                    await session.flush()
                    return {"status": "failed", "error": doc.error_message}

                # 执行解析
                task_logger.info(
                    f"开始解析: doc_id={doc_id}, parser={parser.name}, "
                    f"file={doc.original_filename}"
                )
                chunks = await parser.parse(tmp_path, doc.original_filename)

                # 存储 Chunk 结果到 MinIO
                chunks_json = json.dumps(
                    [c.to_dict() for c in chunks],
                    ensure_ascii=False,
                    indent=2,
                )
                chunks_path = f"chunks/{doc_id}.json"
                await storage_service.upload(
                    chunks_json.encode("utf-8"),
                    chunks_path,
                    "application/json",
                )

                # 更新文档状态
                doc.status = "ready"
                doc.chunk_count = len(chunks)
                doc.error_message = ""

                # 更新知识库 chunk 计数（使用参数化查询）
                from sqlalchemy import text
                await session.execute(
                    text(
                        """UPDATE knowledge_bases
                           SET chunk_count = (
                               SELECT COALESCE(SUM(chunk_count), 0)
                               FROM documents
                               WHERE kb_id = :kb_id AND status = 'ready'
                           )
                           WHERE id = :kb_id"""
                    ),
                    {"kb_id": doc.kb_id},
                )

                await session.flush()

                task_logger.info(
                    f"解析完成: doc_id={doc_id}, chunks={len(chunks)}"
                )

                # 触发 Embedding 任务
                try:
                    from tasks.embed import embed_document
                    embed_document.delay(doc_id)
                    task_logger.info(f"已提交 Embedding 任务: doc_id={doc_id}")
                except Exception as e:
                    task_logger.warning(f"Embedding 任务提交失败: {e}")

                # 触发 KG 构建任务
                try:
                    from tasks.kg_build import build_knowledge_graph
                    build_knowledge_graph.delay(doc_id)
                    task_logger.info(f"已提交 KG 构建任务: doc_id={doc_id}")
                except Exception as e:
                    task_logger.warning(f"KG 构建任务提交失败: {e}")

                return {
                    "status": "ready",
                    "chunks": len(chunks),
                    "parser": parser.name,
                }

            except Exception as parse_err:
                doc.status = "failed"
                doc.error_message = str(parse_err)
                await session.flush()
                task_logger.error(f"解析失败 doc_id={doc_id}: {parse_err}")
                return {"status": "failed", "error": str(parse_err)}

            finally:
                # 清理临时文件
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
