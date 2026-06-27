"""文档服务层"""

import os
import tempfile
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from core.config import settings
from core.exceptions import BadRequestError, NotFoundError
from engine.parser.base import ParserRegistry
from models.models import Document, KnowledgeBase
from services.storage import storage_service


async def create_document(
    db: AsyncSession,
    kb_id: str,
    filename: str,
    file_data: bytes,
    mime_type: str = "",
) -> Document:
    """创建文档记录并上传到 MinIO

    Args:
        db: 数据库会话
        kb_id: 知识库 ID
        filename: 原始文件名
        file_data: 文件内容
        mime_type: MIME 类型

    Returns:
        创建的 Document 对象
    """
    # 验证知识库存在
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    kb = result.scalar_one_or_none()
    if not kb:
        raise NotFoundError("知识库")

    # 检查文件大小
    file_size_mb = len(file_data) / (1024 * 1024)
    if file_size_mb > settings.MAX_FILE_SIZE_MB:
        raise BadRequestError(f"文件大小超过限制 ({settings.MAX_FILE_SIZE_MB}MB)")

    # 计算 MD5
    file_md5 = storage_service.compute_md5(file_data)

    # 检查是否支持的格式
    parser = ParserRegistry.find_for(filename, mime_type)
    if not parser:
        raise BadRequestError(
            f"不支持的文件格式: {filename}。支持: PDF, DOCX, XLSX, TXT, MD"
        )

    # 上传到 MinIO
    object_name = f"{kb_id}/{uuid.uuid4().hex}_{filename}"
    try:
        await storage_service.upload(file_data, object_name, mime_type)
    except Exception as e:
        logger.error(f"MinIO 上传失败: {e}")
        # 降级：保存到本地临时目录
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        local_path = os.path.join(settings.UPLOAD_DIR, object_name.replace("/", "_"))
        with open(local_path, "wb") as f:
            f.write(file_data)
        object_name = local_path
        logger.info(f"降级到本地存储: {local_path}")

    # 创建数据库记录
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

    logger.info(f"文档记录已创建: {doc.id} -> {filename}")

    # 触发异步解析（通过 Celery）
    try:
        _trigger_parse_task(doc.id)
    except RuntimeError as e:
        # Celery 不可用时，文档保持 uploaded 状态，等待后续手动/自动重试
        logger.warning(f"Celery 不可用，文档将保持 uploaded 状态: {e}")
        doc.status = "uploaded"
        doc.error_message = "等待解析（Celery Worker 未运行）"
        await db.flush()

    return doc


def _trigger_parse_task(doc_id: str):
    """触发 Celery 异步解析任务"""
    from tasks.parse import parse_document

    try:
        parse_document.delay(doc_id)
        logger.info(f"已提交解析任务: doc_id={doc_id}")
    except Exception as e:
        logger.error(
            f"Celery 解析任务提交失败 doc_id={doc_id}: {e}\n"
            f"请确认 Celery Worker 已启动: celery -A tasks.celery_app worker -l info"
        )
        raise RuntimeError(
            f"异步解析任务提交失败，请检查 Celery Worker 是否运行: {e}"
        ) from e


async def get_document(db: AsyncSession, doc_id: str) -> Document:
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise NotFoundError("文档")
    return doc


async def get_document_contents(doc: Document) -> bytes:
    """获取文档的原始内容"""
    # 判断是 MinIO 路径还是本地路径
    if doc.file_path.startswith(settings.UPLOAD_DIR) or os.path.isabs(doc.file_path):
        with open(doc.file_path, "rb") as f:
            return f.read()
    else:
        return await storage_service.download(doc.file_path)
