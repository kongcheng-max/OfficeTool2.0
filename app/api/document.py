"""文档管理 API — 上传 / 批量 / 替换 / 列表 / 删除 / 版本"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, UploadFile, File, Request
from loguru import logger
from sqlalchemy import func, select, text
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_current_user_from_query
from core.config import settings
from core.database import get_db
from core.exceptions import BadRequestError, ConflictError, NotFoundError
from core.response import APIResponse, PaginatedData
from engine.rag.vector_store import vector_store
from models.models import Document, DocumentVersion, KnowledgeBase, Tag, User
from schemas.schemas import (
    BatchItemResult, BatchUploadResponse,
    DocumentDetailResponse, DocumentReplaceRequest,
    DocumentResponse, DocumentUploadResponse, DocumentVersionResponse,
    TagResponse,
)
from services.document_service import (
    _check_kb_owner, check_duplicate_md5, create_document,
    get_document, get_document_contents, replace_document,
)
from services.storage import storage_service

router = APIRouter(prefix="/api/v1/kb/{kb_id}/documents", tags=["文档"])

# ── Upload safety: prevent OOM from large files ──────────────

_MAX_BYTES = settings.MAX_FILE_SIZE_MB * 1024 * 1024  # 200 MB
_CHUNK_SIZE = 8192  # 8 KB streaming read


async def _read_file_safe(file: UploadFile, request: Request) -> bytes:
    """流式读取上传文件，在超过限制时尽早拒绝，防止 OOM。

    1. Content-Length 头快速预检（不精确但零成本）
    2. 分块读取，累计超过 MAX_FILE_SIZE_MB 即抛出错误
    """
    # ── 预检 Content-Length ──
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            size_mb = int(content_length) / (1024 * 1024)
            if size_mb > settings.MAX_FILE_SIZE_MB:
                raise BadRequestError(
                    f"文件大小超过限制 ({settings.MAX_FILE_SIZE_MB}MB，实际 {size_mb:.1f}MB)"
                )
        except ValueError:
            pass  # Content-Length 不可解析则跳过预检

    # ── 流式分块读取 ──
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > _MAX_BYTES:
            raise BadRequestError(
                f"文件大小超过限制 ({settings.MAX_FILE_SIZE_MB}MB)"
            )
        chunks.append(chunk)

    return b"".join(chunks)


# ====================================================================
# 上传（单文件 + 批量 + ZIP 导入）
# ====================================================================

@router.post("", response_model=APIResponse[DocumentUploadResponse])
async def upload_document(
    kb_id: str,
    file: UploadFile = File(...),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """上传文档到指定知识库（multipart/form-data）"""
    await _check_kb_owner(db, kb_id, current_user.id)

    if not file.filename:
        raise BadRequestError("文件名不能为空")

    file_data = await _read_file_safe(file, request)
    if not file_data:
        raise BadRequestError("文件内容为空")

    doc = await create_document(
        db=db, kb_id=kb_id, filename=file.filename,
        file_data=file_data, mime_type=file.content_type or "",
    )
    return APIResponse.success(
        DocumentUploadResponse(
            document_id=doc.id, status=doc.status,
            message="文档已上传，正在解析中",
        )
    )


@router.post("/batch", response_model=APIResponse[BatchUploadResponse])
async def batch_upload_documents(
    kb_id: str,
    files: list[UploadFile] = File(...),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """批量上传文档（多文件，含 MD5 去重）

    每文件独立处理：成功→创建文档；MD5重复→跳过；其他错误→记录原因。
    返回每个文件的处理结果。
    """
    await _check_kb_owner(db, kb_id, current_user.id)

    # 预读所有文件数据并计算 MD5（避免重复读）
    file_items: list[dict] = []
    seen_md5: set[str] = set()
    skipped_md5 = 0

    for file in files:
        if not file.filename:
            continue
        try:
            data = await _read_file_safe(file, request)
            if not data:
                continue
            md5 = storage_service.compute_md5(data)

            # 同批次内去重
            if md5 in seen_md5:
                skipped_md5 += 1
                continue
            seen_md5.add(md5)

            # 同知识库内去重
            if await check_duplicate_md5(db, kb_id, md5):
                skipped_md5 += 1
                continue

            file_items.append({
                "filename": file.filename,
                "data": data,
                "mime_type": file.content_type or "",
            })
        except Exception:
            continue

    results = []
    success_count = 0
    failed_count = 0

    for item in file_items:
        try:
            doc = await create_document(
                db=db, kb_id=kb_id, filename=item["filename"],
                file_data=item["data"], mime_type=item["mime_type"],
                skip_md5_check=True,
            )
            results.append(BatchItemResult(
                filename=item["filename"],
                document_id=doc.id,
                status="success",
                message="已提交",
            ))
            success_count += 1
        except Exception as e:
            results.append(BatchItemResult(
                filename=item["filename"],
                document_id="",
                status="failed",
                message=str(e)[:200],
            ))
            failed_count += 1
            logger.warning(f"批量上传单文件失败: {item['filename']}: {e}")

    return APIResponse.success(
        BatchUploadResponse(
            success_count=success_count,
            failed_count=failed_count,
            skipped_count=skipped_md5,
            results=results,
        ),
        message=f"批量完成: 成功{success_count}, 失败{failed_count}, 跳过{skipped_md5}",
    )


@router.post("/import-zip", response_model=APIResponse[BatchUploadResponse])
async def import_zip(
    kb_id: str,
    file: UploadFile = File(...),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """压缩包导入 — 自动解压 ZIP 并将所有支持的文件导入"""
    import io, zipfile

    await _check_kb_owner(db, kb_id, current_user.id)

    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise BadRequestError("仅支持 ZIP 压缩包")

    file_data = await _read_file_safe(file, request)
    zip_buffer = io.BytesIO(file_data)

    results = []
    success_count = 0
    failed_count = 0
    skipped_count = 0

    try:
        with zipfile.ZipFile(zip_buffer, "r") as zf:
            for info in zf.infolist():
                if info.is_dir() or info.filename.startswith("."):
                    continue
                if "__MACOSX" in info.filename:
                    continue

                fname = info.filename.split("/")[-1]
                if not fname:
                    continue

                try:
                    inner_data = zf.read(info.filename)
                    if not inner_data:
                        failed_count += 1
                        continue

                    md5 = storage_service.compute_md5(inner_data)
                    if await check_duplicate_md5(db, kb_id, md5):
                        skipped_count += 1
                        continue

                    doc = await create_document(
                        db=db, kb_id=kb_id, filename=fname,
                        file_data=inner_data, mime_type="",
                        skip_md5_check=True,
                    )
                    results.append(BatchItemResult(
                        filename=fname, document_id=doc.id, status="success",
                    ))
                    success_count += 1
                except Exception as e:
                    results.append(BatchItemResult(
                        filename=fname, document_id="", status="failed",
                        message=str(e)[:200],
                    ))
                    failed_count += 1

    except zipfile.BadZipFile:
        raise BadRequestError("无效的 ZIP 文件")

    return APIResponse.success(
        BatchUploadResponse(
            success_count=success_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            results=results,
        ),
        message=f"ZIP 导入完成: 成功{success_count}, 失败{failed_count}, 跳过{skipped_count}",
    )


# ====================================================================
# 文档列表 / 详情
# ====================================================================

@router.get("", response_model=APIResponse[PaginatedData[DocumentResponse]])
async def list_documents(
    kb_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tag_id: Optional[str] = Query(None, description="按标签筛选"),
    status: Optional[str] = Query(None, description="按状态筛选: uploaded/processing/parsed/ready/failed"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """知识库内文档列表（分页，支持标签/状态筛选）"""
    await _check_kb_owner(db, kb_id, current_user.id)

    # 构建查询
    query = select(Document).where(Document.kb_id == kb_id).options(selectinload(Document.tags))

    # 标签筛选：子查询（通过关联表）
    if tag_id:
        from models.models import document_tags
        query = query.where(
            Document.id.in_(
                select(document_tags.c.document_id).where(
                    document_tags.c.tag_id == tag_id
                )
            )
        )

    if status:
        query = query.where(Document.status == status)

    # 总数
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # 分页
    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(Document.created_at.desc())
        .offset(offset).limit(page_size)
    )
    docs = result.scalars().all()
    total_pages = max(1, (total + page_size - 1) // page_size)

    return APIResponse.success(
        PaginatedData(
            items=[DocumentResponse.model_validate(d) for d in docs],
            total=total, page=page, page_size=page_size, total_pages=total_pages,
        )
    )


@router.get("/{doc_id}", response_model=APIResponse[DocumentDetailResponse])
async def get_document_detail(
    kb_id: str,
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """文档详情（含标签列表）"""
    await _check_kb_owner(db, kb_id, current_user.id)

    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.kb_id == kb_id)
        .options(selectinload(Document.tags))
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise NotFoundError("文档")

    # eager load tags
    tags = [TagResponse.model_validate(t) for t in doc.tags] if doc.tags else []

    return APIResponse.success(
        DocumentDetailResponse(
            id=doc.id,
            kb_id=doc.kb_id,
            filename=doc.filename,
            original_filename=doc.original_filename,
            file_size=doc.file_size,
            mime_type=doc.mime_type,
            status=doc.status,
            error_message=doc.error_message,
            chunk_count=doc.chunk_count,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            tags=tags,
        )
    )


# ====================================================================
# 文档替换（带版本追踪）
# ====================================================================

@router.post("/{doc_id}/replace", response_model=APIResponse[DocumentUploadResponse])
async def replace_document_endpoint(
    kb_id: str,
    doc_id: str,
    file: UploadFile = File(...),
    request: Request = None,
    change_note: str = Query("", description="版本变更说明"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """替换文档内容 — 自动创建版本快照 + 重新解析

    旧文件索引被清理，新文件进入标准解析流水线。
    版本历史：GET /documents/{doc_id}/versions
    """
    await _check_kb_owner(db, kb_id, current_user.id)

    if not file.filename:
        raise BadRequestError("文件名不能为空")

    file_data = await _read_file_safe(file, request)
    if not file_data:
        raise BadRequestError("文件内容为空")

    doc, ver = await replace_document(
        db=db, kb_id=kb_id, doc_id=doc_id,
        file_data=file_data, filename=file.filename,
        mime_type=file.content_type or "",
        change_note=change_note,
    )

    return APIResponse.success(
        DocumentUploadResponse(
            document_id=doc.id,
            status=doc.status,
            message=f"文档已替换（新版本 v{ver.version}），正在重新解析",
        )
    )


# ====================================================================
# 删除
# ====================================================================

@router.delete("/{doc_id}", response_model=APIResponse)
async def delete_document(
    kb_id: str,
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除文档 — 同步清理 Milvus + ES + MinIO + DB + 版本历史"""
    await _check_kb_owner(db, kb_id, current_user.id)

    # 查询文档
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.kb_id == kb_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise NotFoundError("文档")

    # 1. Milvus
    try:
        vector_store.delete_by_doc_id(doc_id)
        logger.info(f"Milvus 已清理: doc_id={doc_id}")
    except Exception as e:
        logger.warning(f"Milvus 清理失败: {e}")

    # 2. ES
    try:
        from engine.rag.es_store import es_store
        await es_store.delete_by_doc_id(doc_id)
    except Exception as e:
        logger.warning(f"ES 清理失败: {e}")

    # 3. MinIO / 本地文件
    try:
        await storage_service.delete(doc.file_path)
    except Exception as e:
        logger.warning(f"文件删除失败: {e}")

    # 4. 解析结果 JSON
    try:
        await storage_service.delete(f"chunks/{doc_id}.json")
    except Exception:
        pass

    # 5. 删除版本历史 + 文档
    from models.models import document_tags
    await db.execute(
        text("DELETE FROM document_versions WHERE document_id = :did"), {"did": doc_id}
    )
    await db.execute(
        text("DELETE FROM document_tags WHERE document_id = :did"), {"did": doc_id}
    )
    await db.delete(doc)
    await db.flush()

    # 6. 更新 KB chunk 计数
    await db.execute(
        text(
            """UPDATE knowledge_bases SET chunk_count = (
               SELECT COALESCE(SUM(chunk_count), 0)
               FROM documents WHERE kb_id = :kb_id AND status IN ('parsed', 'ready')
            ) WHERE id = :kb_id"""
        ),
        {"kb_id": kb_id},
    )

    # W10.1: 文档删除后清除 QA 缓存
    try:
        from services.qa_cache import qa_cache
        await qa_cache.invalidate_kb(kb_id)
    except Exception:
        pass

    return APIResponse.success(message="文档已删除")


# ====================================================================
# 版本历史
# ====================================================================

@router.get("/{doc_id}/versions", response_model=APIResponse[list[DocumentVersionResponse]])
async def list_document_versions(
    kb_id: str,
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """文档版本历史 — 按版本号降序"""
    await _check_kb_owner(db, kb_id, current_user.id)

    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.kb_id == kb_id)
    )
    if not result.scalar_one_or_none():
        raise NotFoundError("文档")

    ver_result = await db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == doc_id)
        .order_by(DocumentVersion.version.desc())
    )
    versions = ver_result.scalars().all()
    return APIResponse.success([DocumentVersionResponse.model_validate(v) for v in versions])


# ====================================================================
# 文件下载 / 预览
# ====================================================================

@router.get("/{doc_id}/download")
async def download_document(
    kb_id: str,
    doc_id: str,
    current_user: User = Depends(get_current_user_from_query),
    db: AsyncSession = Depends(get_db),
):
    """下载源文件或在线预览

    返回文件字节流。PDF 和图片可浏览器直接预览，其他格式触发下载。
    支持通过 ?token=xxx URL 参数传递 JWT，兼容 iframe/img/浏览器原生请求。
    """
    from fastapi.responses import Response
    import io

    await _check_kb_owner(db, kb_id, current_user.id)

    doc = await get_document(db, doc_id)
    if doc.kb_id != kb_id:
        raise NotFoundError("文档")

    content = await get_document_contents(doc)

    media_type = doc.mime_type or "application/octet-stream"
    # PDF 可内联预览
    if media_type == "application/pdf":
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f"inline; filename*=UTF-8''{doc.original_filename}"},
        )
    # 图片可内联预览
    if media_type.startswith("image/"):
        return Response(content=content, media_type=media_type)

    # 其他格式触发下载
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{doc.original_filename}"},
    )


@router.get("/{doc_id}/preview")
async def preview_document(
    kb_id: str,
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """在线预览源文件内容

    PDF/图片: 直接返回二进制（浏览器内嵌预览）
    文本类: 返回纯文本（解析内容）
    Office文档: 返回元信息 + 下载链接
    """
    from fastapi.responses import PlainTextResponse, Response

    await _check_kb_owner(db, kb_id, current_user.id)

    doc = await get_document(db, doc_id)
    if doc.kb_id != kb_id:
        raise NotFoundError("文档")

    content = await get_document_contents(doc)
    mime = doc.mime_type or ""

    # PDF 直接预览
    if mime == "application/pdf" or doc.original_filename.lower().endswith(".pdf"):
        return Response(content, media_type="application/pdf")

    # 图片直接预览
    if mime.startswith("image/"):
        return Response(content, media_type=mime)

    # 纯文本类直接返回
    text_mimes = {"text/plain", "text/markdown", "text/csv", "text/html",
                  "application/json", "application/xml", "text/xml"}
    if mime in text_mimes or doc.original_filename.lower().endswith(
        (".txt", ".md", ".csv", ".json", ".xml", ".html", ".htm")
    ):
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("latin-1", errors="replace")
        return PlainTextResponse(text[:100000])

    # Office 文档返回元信息 + 下载链接
    return {
        "document_id": doc.id,
        "filename": doc.original_filename,
        "file_size": doc.file_size,
        "mime_type": doc.mime_type,
        "status": doc.status,
        "chunk_count": doc.chunk_count,
        "message": "此格式不支持在线预览，请使用下载端点获取源文件",
        "download_url": f"/api/v1/kb/{kb_id}/documents/{doc_id}/download",
    }
