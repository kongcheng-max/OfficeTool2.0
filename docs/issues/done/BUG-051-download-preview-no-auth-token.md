# BUG-051: 文档下载/预览 URL 不含 JWT 认证，iframe/图片/下载均返回 401

| 属性 | 值 |
|------|---|
| **严重级别** | 🔴 Critical |
| **影响模块** | 前端文档预览、文档下载 |
| **发现方式** | 代码审查 |
| **状态** | ✅ Done — 2026-07-06 验收通过 |
| **发现日期** | 2026-07-06 |

## 现象

文档预览页面（`DocumentPreview.tsx`）中的**下载按钮**、**PDF iframe 预览**、**图片预览**三项功能均无法正常工作，因为浏览器发起的请求不携带 JWT Authorization 请求头，后端返回 401 Unauthorized。

## 根因

`components/DocumentPreview.tsx:109`:
```tsx
const downloadUrl = `/api/v1/kb/${kbId}/documents/${docId}/download`;
```

此 URL 在三种场景中被使用，但全都绕过了 Axios 拦截器：

1. **下载按钮** (line 165): `window.open(downloadUrl, '_blank')` — 浏览器原生导航请求，不带自定义 Header
2. **PDF iframe** (line 187): `<iframe src={downloadUrl} .../>` — iframe 的 GET 请求由浏览器发出，不带 Authorization
3. **图片预览** (line 194): `<img src={downloadUrl} .../>` — 同上

而后端端点 `api/document.py:471-475` 依赖 `Depends(get_current_user)` 进行认证：
```python
@router.get("/{doc_id}/download")
async def download_document(
    kb_id: str,
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
```

`get_current_user` 从 `Authorization: Bearer <token>` Header 中提取 JWT，浏览器原生请求不包含此 Header，因此所有请求返回 401。

## 复现步骤

1. 登录系统，进入任意知识库的文档管理页面
2. 点击某个文档的预览按钮
3. 查看 PDF/图片预览区域 → 空白或错误
4. 点击「下载 / 预览源文件」按钮 → 新标签页显示 401 错误或跳转到登录页

## 影响

- 🔴 **文档预览功能完全不可用**（PDF、图片格式）
- 🔴 **文档下载功能完全不可用**
- 🔴 用户只能看到文档元信息，无法确认文档内容

## 修复建议

### 方案 A: 为下载端点添加 Token 查询参数支持（推荐）

后端 `download_document` 端点同时支持从 Query 参数中读取 token：
```python
@router.get("/{doc_id}/download")
async def download_document(
    ...,
    token: str = Query(None),  # 新增：支持 URL 参数传递 token
):
    # 如果 Header 中没有，尝试从 query param 获取
    ...
```

前端在 URL 后附加 token：
```tsx
const token = localStorage.getItem('token');
const downloadUrl = `/api/v1/kb/${kbId}/documents/${docId}/download?token=${encodeURIComponent(token || '')}`;
```

### 方案 B: 前端通过 Axios 获取 Blob 再渲染（适用于图片/下载）

```tsx
// 用 axios 获取 authenticated blob
const res = await axios.get(downloadUrl, { responseType: 'blob' });
const blobUrl = URL.createObjectURL(res.data);
// 用于 img src 或 download link
```

### 方案 C: 下载端点使用短期签名 URL

类似 MinIO presigned URL，后端生成带有时效性签名的下载 URL，不依赖 Authorization Header。

> **推荐方案 A**，实现最简单，改动最小。同时兼容方案 B 用于 iframe（iframe 不能用 Blob URL + Authorization header，需要用 srcdoc 或 方案 A）。
