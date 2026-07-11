# BUG-055: 大文件上传在大小校验前已将全部数据读入内存

| 属性 | 值 |
|------|---|
| **严重级别** | 🟠 High |
| **影响模块** | 文档上传、服务稳定性 |
| **发现方式** | 代码审查 |
| **状态** | ✅ Done — 2026-07-06 验收通过 |
| **发现日期** | 2026-07-06 |

## 现象

文件上传端点（`POST /api/v1/kb/{kb_id}/documents`）在 `api/document.py:49` 调用 `file_data = await file.read()` 将整个文件读入内存，然后才在 `services/document_service.py:75` 中检查文件大小是否超过 `MAX_FILE_SIZE_MB (200MB)`。

如果攻击者或用户上传一个超大文件（如 2GB），服务器内存会先被整个文件填满，然后才被拒绝。在极端情况下可能导致 OOM（Out of Memory）。

## 根因

`api/document.py:48-51`:
```python
file_data = await file.read()        # ← 先读入内存
if not file_data:                     # ← 再检查是否为空
    raise BadRequestError("文件内容为空")

doc = await create_document(           # ← 在这里面才检查大小
    db=db, kb_id=kb_id, filename=file.filename,
    file_data=file_data, ...
)
```

而 `services/document_service.py:75`:
```python
if _file_size_mb(file_data) > settings.MAX_FILE_SIZE_MB:  # ← 读了所有数据后才检查
    raise BadRequestError(...)
```

大小检查的时机太晚。同样的问题存在于批量上传、ZIP导入和文档替换端点。

## 复现步骤

1. 构造一个 500MB+ 的文件
2. POST 到文档上传端点
3. 观察服务器内存飙升至 500MB+，然后请求被拒绝
4. 并发发送多个此类请求 → 服务器 OOM

## 影响

- 🟠 恶意上传可消耗服务器内存，导致 DoS
- 🟠 并发上传多个接近限制的大文件也可能耗尽内存

## 修复建议

在上传前进行流式大小检查。FastAPI/Starlette 支持通过 `request` 对象读取 `content-length` 头进行预检：

```python
from fastapi import Request

@router.post("", ...)
async def upload_document(
    kb_id: str,
    file: UploadFile = File(...),
    request: Request = None,  # 注入 Request
    ...
):
    # 预检 Content-Length
    content_length = request.headers.get("content-length")
    if content_length:
        size_mb = int(content_length) / (1024 * 1024)
        if size_mb > settings.MAX_FILE_SIZE_MB:
            raise BadRequestError(f"文件大小超过限制 ({settings.MAX_FILE_SIZE_MB}MB)")

    # 流式读取，在达到限制时截断
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    chunks = []
    total = 0
    while chunk := await file.read(8192):  # 8KB chunks
        total += len(chunk)
        if total > max_bytes:
            raise BadRequestError(f"文件大小超过限制")
        chunks.append(chunk)
    file_data = b"".join(chunks)
```

或者使用 Starlette 的 `request.stream()` 进行真正的流式处理。
