# BUG-015: parse.py 中使用 f-string 拼接 SQL 存在注入风险

| 属性 | 值 |
|------|---|
| **严重级别** | 🟡 Medium |
| **影响 AC** | 安全性 |
| **发现方式** | 代码审查 |
| **状态** | Open |

## 现象
`app/tasks/parse.py:120-126` 使用 f-string 拼接 SQL 更新知识库 chunk_count：

```python
await session.execute(
    f"""UPDATE knowledge_bases
       SET chunk_count = (SELECT COALESCE(SUM(chunk_count), 0)
                          FROM documents
                          WHERE kb_id = '{doc.kb_id}' AND status = 'ready')
       WHERE id = '{doc.kb_id}'"""
)
```

## 根因
直接使用字符串插值而非参数化查询。

## 影响
- `doc.kb_id` 是由系统生成的 UUID hex 字符串，来自数据库，不是用户输入，**实际 SQL 注入风险极低**
- 但是不符合安全编码规范，且绕过了 ORM

## 修复建议
使用 ORM 方式替代：
```python
from sqlalchemy import update
await session.execute(
    update(KnowledgeBase).where(KnowledgeBase.id == doc.kb_id).values(
        chunk_count=select(func.coalesce(func.sum(Document.chunk_count), 0))
        .where(Document.kb_id == doc.kb_id, Document.status == 'ready')
    )
)
```
