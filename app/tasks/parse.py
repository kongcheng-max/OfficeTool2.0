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


@celery_app.task(name="parse_document", bind=True, max_retries=3, default_retry_delay=10)
def parse_document(self, doc_id: str):
    """异步解析文档 — 使用安全 event loop 模式（同 embed/kg_build）"""
    from tasks.embed import _run_async_safe
    try:
        return _run_async_safe(_async_parse(doc_id))
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

                # W9.3: 解析缓存 — 相同 MD5 跳过重解析
                chunks = None
                if doc.file_md5:
                    from services.parse_cache import parse_cache
                    cached = await parse_cache.get(doc.file_md5)
                    if cached:
                        from engine.parser.base import Chunk
                        chunks = [Chunk.from_dict(c) for c in cached]
                        task_logger.info(
                            f"解析缓存命中: doc_id={doc_id}, md5={doc.file_md5[:12]}..., "
                            f"chunks={len(chunks)}（跳过重解析）"
                        )

                if chunks is None:
                    # 执行解析
                    task_logger.info(
                        f"开始解析: doc_id={doc_id}, parser={parser.name}, "
                        f"file={doc.original_filename}"
                    )
                    chunks = await parser.parse(tmp_path, doc.original_filename)

                    # 写入缓存
                    if doc.file_md5 and chunks:
                        try:
                            from services.parse_cache import parse_cache as pc
                            await pc.set(doc.file_md5, [c.to_dict() for c in chunks])
                        except Exception as cache_err:
                            task_logger.debug(f"解析缓存写入跳过: {cache_err}")

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

                # 更新文档状态 — BUG-066: parsed ≠ ready，等 Embedding 完成后再设 ready
                doc.status = "parsed"
                doc.chunk_count = len(chunks)
                doc.error_message = ""

                # 更新知识库 chunk 计数（parsed + ready 都算已完成解析）
                from sqlalchemy import text
                await session.execute(
                    text(
                        """UPDATE knowledge_bases
                           SET chunk_count = (
                               SELECT COALESCE(SUM(chunk_count), 0)
                               FROM documents
                               WHERE kb_id = :kb_id AND status IN ('parsed', 'ready')
                           )
                           WHERE id = :kb_id"""
                    ),
                    {"kb_id": doc.kb_id},
                )

                await session.flush()

                task_logger.info(
                    f"解析完成: doc_id={doc_id}, chunks={len(chunks)}"
                )

                # 收集 commit 后需要的数据（事务内可见，事务外只读）
                _kb_id = doc.kb_id
                _chunks_len = len(chunks)
                _parser_name = parser.name

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

        # ═══════════════════════════════════════════════════════════
        # 事务已提交（session.begin() 退出 → commit）
        # BUG-066: 在事务外触发 embed / kg，确保它们能看到 committed 状态
        # ═══════════════════════════════════════════════════════════

        # 触发 Embedding 任务（Celery 不可用时同步回退）
        try:
            from tasks.embed import embed_document
            embed_document.delay(doc_id)
            task_logger.info(f"已提交 Embedding 任务: doc_id={doc_id}")
        except Exception as e:
            task_logger.warning(f"Embedding 异步提交失败，尝试同步执行: {e}")
            try:
                from tasks.embed import run_embed_sync
                result = run_embed_sync(doc_id)
                task_logger.info(
                    f"同步 Embedding 完成: doc_id={doc_id}, {result}"
                )
            except Exception as sync_e:
                task_logger.warning(f"同步 Embedding 也失败: {sync_e}")

        # 触发 KG 构建任务（可通过 KG_ENABLED=false 跳过以加速测试）
        from core.config import settings
        if settings.KG_ENABLED:
            try:
                from tasks.kg_build import build_knowledge_graph
                build_knowledge_graph.delay(doc_id)
                task_logger.info(f"已提交 KG 构建任务: doc_id={doc_id}")
            except Exception as e:
                task_logger.warning(
                    f"KG 构建异步提交失败，尝试同步执行: {e}"
                )
                try:
                    from tasks.embed import _run_async_safe
                    from tasks.kg_build import _async_build_kg
                    result = _run_async_safe(_async_build_kg(doc_id))
                    task_logger.info(
                        f"同步 KG 构建完成: doc_id={doc_id}, {result}"
                    )
                except Exception as sync_e:
                    task_logger.warning(f"同步 KG 构建也失败: {sync_e}")
        else:
            task_logger.info(f"KG 构建已禁用 (KG_ENABLED=false): doc_id={doc_id}")

        return {
            "status": "parsed",
            "chunks": _chunks_len,
            "parser": _parser_name,
        }
