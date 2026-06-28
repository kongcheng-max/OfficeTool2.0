# BUG-034: 创建标签后标签列表不显示标签名

| 属性 | 值 |
|------|-----|
| 发现日期 | 2026-06-28 |
| 严重程度 | **严重** / Critical |
| 影响范围 | 标签管理功能完全不可用 |
| 责任部门 | 后端开发组（简单修复） |
| 状态 | Open |

## 现象

1. 点击知识库卡片上的「标签管理」按钮
2. 输入标签名「合同」→ 点击创建 → 提示「标签创建成功」
3. 但右侧标签列表中**标签名和颜色全部不显示**——列表项存在但名称为空白

## 根因

**字段名不匹配：后端返回 `tag_id` / `tag_name`，前端期望 `id` / `name`**

### 后端 (`schemas.py:183-187`)
```python
class TagStatResponse(BaseModel):
    tag_id: str       # ← 前端期望 "id"
    tag_name: str     # ← 前端期望 "name"
    color: str
    document_count: int
```

### 后端 SQL (`api/tag.py:79`)
```sql
SELECT t.id AS tag_id, t.name AS tag_name, t.color,
       COUNT(dt.document_id) AS document_count
```

别名 `AS tag_id` / `AS tag_name` 导致 Pydantic 序列化后的 JSON key 为 `tag_id` / `tag_name`。

### 前端 (`api/tag.ts:11-13`)
```typescript
export interface TagStat extends TagItem {
  document_count: number;
}
// TagItem 期望: { id, name, color, kb_id, created_at }
// 实际收到: { tag_id, tag_name, color, document_count }
// id = undefined, name = undefined → 渲染空白
```

### 前端渲染 (`KnowledgeBase/index.tsx:273`)
```tsx
<span style={{ width: 10, height: 10, background: item.color }} />  {/* color 正常 */}
<Text>{item.name}</Text>  {/* name = undefined → 空白 */}
```

## 修复方案

**方案 A（推荐）**：修改后端 SQL 别名 + `TagStatResponse` 字段名：

```python
# schemas.py
class TagStatResponse(BaseModel):
    id: str           # 原 tag_id
    name: str         # 原 tag_name
    color: str
    document_count: int

# api/tag.py SQL
SELECT t.id AS id, t.name AS name, ...
```

**方案 B**：前端做字段映射（需要改多处）。

推荐方案 A，改动最小且字段名与 `TagItem` 保持一致。

## 影响

标签管理是 Phase 2 核心功能，目前标签列表完全无法显示标签名，用户无法确认标签是否创建成功，也无法删除已有标签。
