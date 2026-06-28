# BUG-042: BC10 · 文档在线预览无法预览源文件内容

| 属性 | 值 |
|------|-----|
| 发现日期 | 2026-06-28 |
| 严重程度 | **高** / High |
| 影响范围 | 文档预览功能 |
| 责任部门 | 后端 + 前端 |
| 状态 | Open |

## 现象

在文档管理页面点击眼睛图标（预览），右侧抽屉只显示：
- 文档元信息（文件名、大小、状态、块数、上传时间）
- 标签编辑
- 版本历史

**完全没有原文内容预览**——看不到 PDF 页面、Word 文字、图片等源文件内容。

## 根因

### 前端

`DocumentPreview.tsx` 只有元信息展示（Descriptions）、标签编辑（Select）、版本历史（List），**没有任何文件内容渲染/下载组件**。

### 后端

`api/document.py` 没有提供文件下载/预览端点。`getDocumentDetail` 返回文档元信息（含 tags），但不返回文件内容的访问 URL。

## 修复方案

### 后端：增加文件访问端点

```python
# api/document.py
@router.get("/{doc_id}/download")
async def download_document(kb_id, doc_id, ...):
    """下载/预览源文件"""
    doc = await get_document(db, doc_id)
    content = await get_document_contents(doc)
    return StreamingResponse(
        io.BytesIO(content),
        media_type=doc.mime_type or "application/octet-stream",
    )

@router.get("/{doc_id}/preview")
async def preview_document(kb_id, doc_id, ...):
    """在线预览源文件（PDF/图片直接返回，其他格式转 HTML）"""
    doc = await get_document(db, doc_id)
    content = await get_document_contents(doc)
    if doc.mime_type == "application/pdf":
        # 返回 PDF 可直接在 iframe 展示
        return Response(content, media_type="application/pdf")
    elif doc.mime_type.startswith("image/"):
        return Response(content, media_type=doc.mime_type)
    ...
```

### 前端：增加预览区域

在 `DocumentPreview` 抽屉中增加：
1. PDF 文件：`<iframe src="/api/v1/kb/{id}/documents/{docId}/preview">`
2. 图片文件：`<img src="{downloadUrl}">`
3. 文本/代码文件：读取内容渲染
4. Office 文档：提供下载链接 + "使用本地应用打开"提示

## 影响

文档管理的最基本功能——预览文档内容——完全缺失。
