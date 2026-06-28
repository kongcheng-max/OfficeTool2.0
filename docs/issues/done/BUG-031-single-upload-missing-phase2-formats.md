# BUG-031: 单文件上传按钮不支持 Phase 2 文件格式

| 属性 | 值 |
|------|-----|
| 发现日期 | 2026-06-28 |
| 严重程度 | **高** / High |
| 影响范围 | 单文件上传功能 |
| 责任部门 | 前端开发组 |
| 状态 | Open |

## 现象

点击「上传文档」按钮（`DocumentUpload` 组件），只能选择 .pdf / .docx / .xlsx / .txt / .md 格式。
但「批量上传文档」Tab 可以上传 .pptx / .ppt / .csv / .json / .html / .xml。

## 根因

`E:\OfficeTool\app\frontend\src\components\DocumentUpload.tsx:8`

```typescript
const ALLOWED_EXTS = ['.pdf', '.docx', '.doc', '.xlsx', '.xls', '.txt', '.md', '.text', '.markdown', '.mdown'];
```

这个常量只包含 MVP Phase 1 的格式，缺少 Phase 2 的新格式。

对比批量上传 (`Documents/index.tsx:291`)：
```
accept=".pdf,.docx,.doc,.xlsx,.xls,.txt,.md,.pptx,.ppt,.csv,.json,.html,.xml"
```

后端 `ParserRegistry` 已注册 ​**全部 Phase 2 解析器**（PPTX, CSV, JSON, HTML, XML），后端完全支持这些格式。

## 修复方案

在 `DocumentUpload.tsx` 中：
1. `ALLOWED_EXTS` 数组追加：`.pptx`, `.ppt`, `.csv`, `.json`, `.html`, `.xml`
2. `accept` 属性（第 66 行）同样追加
3. 提示文案（第 78 行）更新

## 影响

用户通过「上传文档」按钮无法上传 PPTX、CSV、JSON、HTML、XML 文件，只能用批量上传。
