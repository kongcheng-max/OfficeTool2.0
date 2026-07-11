# BUG-045: 文档状态 'error' vs 'failed' 前后端不一致

| 属性 | 值 |
|------|---|
| **严重级别** | 🟠 High |
| **影响模块** | 前端文档管理（筛选 + 状态显示） |
| **发现方式** | 代码审查 |
| **状态** | ✅ Done — 2026-07-06 验收通过 |
| **发现日期** | 2026-07-06 |

## 现象

后端定义和使用的文档失败状态是 `"failed"`，但前端 TypeScript 类型定义、状态筛选下拉框和状态徽章组件全部使用 `"error"`，导致两个功能失效：

1. **状态筛选失效**: 在文档管理页面选择「❌ 失败」筛选时，前端发送 `status=error` 到 API，API 用此值匹配 `Document.status == 'failed'`，永远匹配不到任何文档
2. **失败文档状态显示错误**: 当文档后台状态为 `"failed"` 时，前端 `DocumentStatusBadge` 找不到匹配配置，降级为默认的「解析中」图标+标签

## 根因

前后端在 Phase 1/Phase 2 独立开发时使用了不同的枚举值，未进行对齐。

**后端** (`models/models.py:79`):
```python
status: Mapped[str] = mapped_column(...)  # uploaded | processing | ready | failed
```

**后端** (`tasks/parse.py:151`):
```python
doc.status = "failed"
```

**前端** (`api/document.ts:4`):
```typescript
export type DocStatus = 'uploaded' | 'processing' | 'ready' | 'error';
```

**前端** (`Documents/index.tsx:317`):
```tsx
{ value: 'error', label: '❌ 失败' },
```

**前端** (`DocumentStatusBadge.tsx:22`):
```tsx
error: { color: '#FF4D4F', icon: <CloseCircleOutlined />, label: '失败' },
```

## 影响

- 🟠 用户无法筛选查看解析失败的文档
- 🟠 解析失败的文档在列表中显示为「解析中」而非「失败」
- 用户可能对实际上已失败的文档进行重复操作

## 修复建议

**推荐方案**: 修改前端，将 `'error'` 统一改为 `'failed'`，与后端保持一致：

1. `api/document.ts:4` — `DocStatus` 类型定义：`'error'` → `'failed'`
2. `components/DocumentStatusBadge.tsx:22` — 状态配置 key：`error:` → `failed:`
3. `pages/Documents/index.tsx:317` — 筛选下拉值：`value: 'error'` → `value: 'failed'`
4. 全局搜索 `'error'` 在文档状态相关代码中的使用，确保全部替换

**备选方案**: 修改后端，将 `'failed'` 统一改为 `'error'`（影响面更大，不推荐，因为已有存量的 failed 数据）。
