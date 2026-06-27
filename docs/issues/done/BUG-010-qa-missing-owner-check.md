# BUG-010: Q&A 端点不验证知识库归属

| 属性 | 值 |
|------|---|
| **严重级别** | 🟡 Medium |
| **影响 AC** | AC05 |
| **发现方式** | 代码审查 |
| **状态** | Open |

## 现象
`app/api/qa.py:28` 的问答端点仅验证知识库存在，不检查当前用户是否为知识库的 owner：

```python
result = await db.execute(
    select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
)
kb = result.scalar_one_or_none()
if not kb:
    raise NotFoundError("知识库")
```

而文档上传 API (`app/api/document.py:27-33`) 正确验证了归属：
```python
select(KnowledgeBase).where(
    KnowledgeBase.id == kb_id,
    KnowledgeBase.owner_id == current_user.id,
)
```

## 影响
- **AC05 多知识库数据隔离**：用户 A 可以通过构造 URL 对用户 B 的知识库提问
- 虽然上传有校验，但问答绕过权限，存在数据泄露风险

## 修复建议
在问答端点加上 `KnowledgeBase.owner_id == current_user.id` 条件。
