"""文档服务层 — 上传 / 替换 / MD5去重 / 版本追踪"""

import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.exceptions import BadRequestError, ConflictError, NotFoundError
from engine.parser.base import ParserRegistry
from models.models import Document, DocumentVersion, KnowledgeBase
from services.storage import storage_service


async def _check_kb_owner(db: AsyncSession, kb_id: str, user_id: str) -> KnowledgeBase:
    """验证知识库存在且属于当前用户"""
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.owner_id == user_id,
        )
    )
    kb = result.scalar_one_or_none()
    if not kb:
        raise NotFoundError("知识库")
    return kb


async def check_duplicate_md5(
    db: AsyncSession,
    kb_id: str,
    file_md5: str,
) -> Optional[Document]:
    """检查同一知识库下是否有相同 MD5 的文档（避免重复上传）

    Returns:
        重复文档对象，若不存在返回 None
    """
    result = await db.execute(
        select(Document).where(
            Document.kb_id == kb_id,
            Document.file_md5 == file_md5,
        )
    )
    return result.scalar_one_or_none()


def _file_size_mb(data: bytes) -> float:
    return len(data) / (1024 * 1024)


async def create_document(
    db: AsyncSession,
    kb_id: str,
    filename: str,
    file_data: bytes,
    mime_type: str = "",
    skip_md5_check: bool = False,
) -> Document:
    """创建文档记录并上传到 MinIO

    Args:
        skip_md5_check: 批量上传时跳过 MD5 检查以提高性能（上层调用方应预先去重）

    Raises:
        BadRequestError: 格式不支持 / 文件过大
        ConflictError: MD5 重复（skip_md5_check=False 时）
    """
    # 检查文件大小
    if _file_size_mb(file_data) > settings.MAX_FILE_SIZE_MB:
        raise BadRequestError(f"文件大小超过限制 ({settings.MAX_FILE_SIZE_MB}MB)")

    # 计算 MD5
    file_md5 = storage_service.compute_md5(file_data)

    # MD5 去重检查
    if not skip_md5_check:
        dup = await check_duplicate_md5(db, kb_id, file_md5)
        if dup:
            raise ConflictError(
                f"文件已存在: {dup.original_filename}（MD5 重复）"
            )

    # 检查格式支持
    parser = ParserRegistry.find_for(filename, mime_type)
    if not parser:
        raise BadRequestError(
            f"不支持的文件格式: {filename}。支持: PDF, DOCX, XLSX, PPTX, TXT, MD, CSV, JSON, HTML, XML, 图片"
        )

    # 上传到 MinIO（失败降级本地）
    object_name = f"{kb_id}/{uuid.uuid4().hex}_{filename}"
    try:
        await storage_service.upload(file_data, object_name, mime_type)
    except Exception as e:
        logger.error(f"MinIO 上传失败: {e}")
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        local_path = os.path.join(settings.UPLOAD_DIR, object_name.replace("/", "_"))
        with open(local_path, "wb") as f:
            f.write(file_data)
        object_name = local_path
        logger.info(f"降级到本地存储: {local_path}")

    # 创建记录
    doc = Document(
        kb_id=kb_id,
        filename=object_name,
        original_filename=filename,
        file_size=len(file_data),
        mime_type=mime_type,
        file_path=object_name,
        file_md5=file_md5,
        status="uploaded",
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)

    logger.info(f"文档已创建: {doc.id} -> {filename} (MD5={file_md5[:12]}...)")

    # 触发 Celery 异步解析
    try:
        _trigger_parse_task(doc.id)
    except RuntimeError as e:
        logger.warning(f"Celery 不可用: {e}")
        doc.status = "uploaded"
        doc.error_message = "等待解析（Celery Worker 未运行）"
        await db.flush()

    return doc


def _trigger_parse_task(doc_id: str):
    """触发文档解析 — 优先 Celery 异步，不可用时同步执行"""
    try:
        from tasks.parse import parse_document
        parse_document.delay(doc_id)
        logger.info(f"已提交异步解析: doc_id={doc_id}")
    except Exception as e:
        logger.warning(f"Celery 不可用，改为同步解析 doc_id={doc_id}: {e}")
        try:
            _run_parse_sync(doc_id)
        except Exception as sync_e:
            logger.error(f"同步解析也失败 doc_id={doc_id}: {sync_e}")
            raise RuntimeError(f"解析失败: {sync_e}") from sync_e


def _run_parse_sync(doc_id: str):
    """同步执行文档解析（无 Celery 时使用）"""
    import asyncio
    from tasks.parse import _async_parse
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        # 在已有 event loop 中（FastAPI 请求内），创建新线程执行
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, _async_parse(doc_id))
            future.result(timeout=600)
    else:
        asyncio.run(_async_parse(doc_id))


# ========================================================================
# 文档替换（带版本追踪）
# ========================================================================

async def _get_next_version(db: AsyncSession, doc_id: str) -> int:
    """获取文档的下一个版本号"""
    result = await db.execute(
        select(func.coalesce(func.max(DocumentVersion.version), 0)).where(
            DocumentVersion.document_id == doc_id
        )
    )
    return (result.scalar() or 0) + 1


async def create_document_version(
    db: AsyncSession,
    doc: Document,
    change_note: str = "",
) -> DocumentVersion:
    """为当前文档状态创建版本快照"""
    next_ver = await _get_next_version(db, doc.id)

    ver = DocumentVersion(
        document_id=doc.id,
        version=next_ver,
        file_path=doc.file_path,
        file_size=doc.file_size,
        file_md5=doc.file_md5,
        chunk_count=doc.chunk_count,
        change_note=change_note or f"v{next_ver}",
    )
    db.add(ver)
    await db.flush()
    await db.refresh(ver)
    logger.info(f"版本快照已创建: doc={doc.id} v{next_ver}")
    return ver


async def replace_document(
    db: AsyncSession,
    kb_id: str,
    doc_id: str,
    file_data: bytes,
    filename: str,
    mime_type: str = "",
    change_note: str = "",
) -> Tuple[Document, DocumentVersion]:
    """替换文档内容（创建版本快照 → 更新文档 → 触发重解析）

    流程:
      1. 为旧文件创建版本快照
      2. 上传新文件到 MinIO
      3. 更新 Document 记录的 file_* 字段
      4. 清理旧文件的 Milvus/ES 数据
      5. 触发 Celery 重解析

    Returns:
        (更新后的 Document, 版本快照)
    """
    # 验证文档存在
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.kb_id == kb_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise NotFoundError("文档")

    # 格式检查
    parser = ParserRegistry.find_for(filename, mime_type)
    if not parser:
        raise BadRequestError(f"不支持的文件格式: {filename}")

    # 1. 创建版本快照（保存旧文件信息）
    ver = await create_document_version(db, doc, change_note=change_note or f"替换为 {filename}")

    # 2. 上传新文件
    object_name = f"{kb_id}/{uuid.uuid4().hex}_{filename}"
    try:
        await storage_service.upload(file_data, object_name, mime_type)
    except Exception:
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        object_name = os.path.join(settings.UPLOAD_DIR, object_name.replace("/", "_"))
        with open(object_name, "wb") as f:
            f.write(file_data)

    # 3. 清理旧数据（Milvus + ES）
    _cleanup_old_indexes(doc_id)

    # 4. 更新文档记录
    doc.original_filename = filename
    doc.filename = object_name
    doc.file_path = object_name
    doc.file_size = len(file_data)
    doc.file_md5 = storage_service.compute_md5(file_data)
    doc.mime_type = mime_type
    doc.status = "uploaded"
    doc.chunk_count = 0
    doc.error_message = ""
    db.add(doc)
    await db.flush()
    await db.refresh(doc)

    # 5. 触发重解析
    try:
        _trigger_parse_task(doc.id)
    except RuntimeError:
        doc.error_message = "等待解析（Celery Worker 未运行）"
        await db.flush()

    logger.info(f"文档已替换: doc_id={doc_id} v{ver.version} -> {filename}")
    return doc, ver


def _cleanup_old_indexes(doc_id: str):
    """异步清理旧索引（失败不阻塞）"""
    import asyncio
    try:
        from engine.rag.vector_store import vector_store
        vector_store.delete_by_doc_id(doc_id)
        logger.info(f"旧 Milvus 向量已清理: doc_id={doc_id}")
    except Exception as e:
        logger.warning(f"Milvus 清理失败: {e}")

    try:
        loop = asyncio.get_event_loop()
        loop.create_task(_cleanup_es(doc_id))
    except Exception:
        pass


async def _cleanup_es(doc_id: str):
    try:
        from engine.rag.es_store import es_store
        await es_store.delete_by_doc_id(doc_id)
        logger.info(f"旧 ES 数据已清理: doc_id={doc_id}")
    except Exception:
        pass


# ========================================================================
# 查询辅助
# ========================================================================

async def get_document(db: AsyncSession, doc_id: str) -> Document:
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise NotFoundError("文档")
    return doc


async def get_document_contents(doc: Document) -> bytes:
    if doc.file_path.startswith(settings.UPLOAD_DIR) or os.path.isabs(doc.file_path):
        with open(doc.file_path, "rb") as f:
            return f.read()
    return await storage_service.download(doc.file_path)
