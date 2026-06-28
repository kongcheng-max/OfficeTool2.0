# BUG-037: 文档列表不显示标签列 + 列表 API 不返回标签

| 属性 | 值 |
|------|-----|
| 发现日期 | 2026-06-28 |
| 严重程度 | **低** / Low |
| 影响范围 | 文档管理可用性 |
| 责任部门 | 前端 + 后端 |
| 状态 | Open |

## 现象

文档管理页面（`/kb/:id/documents`）的表格中看不到任何标签信息。即使已通过 DocumentPreview 抽屉为文档分配了标签，表格中也完全不体现。

## 根因

### 前端

`E:\OfficeTool\app\frontend\src\pages\Documents\index.tsx` 表格列定义（第 121-186 行）：
- 列：序号、文件名、大小、状态、块数、上传时间、操作
- **没有标签列**

`E:\OfficeTool\app\frontend\src\api\document.ts` 中 `DocumentItem` 接口（第 6-18 行）：
```typescript
export interface DocumentItem {
  id: string;
  filename: string;
  file_size: number;
  status: string;
  chunk_count?: number;
  created_at: string;
  // 缺少 tags 字段！
}
```

### 后端

`E:\OfficeTool\app\api\document.py` 的 `list_documents` 返回 `DocumentResponse`（不含 tags），只有 `get_document_detail` 返回 `DocumentDetailResponse`（含 tags）。

## 修复方案

1. **后端**：`list_documents` 的 `DocumentResponse` 增加 `tags: list[TagResponse]`，查询时 `selectinload(Document.tags)`
2. **前端**：`DocumentItem` 接口增加 `tags: TagItem[]`，表格增加标签列（用彩色 Tag 组件渲染）
3. **前端**：文档列表页增加标签列过滤（已有后端 `tag_id` 参数支持，但前端无 UI）

## 影响

用户无法在列表中直观看到文档的标签状态，标签分配的闭环体验缺失。
