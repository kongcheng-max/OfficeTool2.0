# BUG-074: Week 10 数据库索引缺少 Alembic 迁移文件

| 属性 | 值 |
|------|---|
| **严重级别** | 🟡 Medium |
| **影响模块** | 数据库 → 查询性能 |
| **发现方式** | Week 10 验收测试 |
| **状态** | 🔴 待修复 |
| **发现日期** | 2026-07-11 |

---

## 现象

`models.py` 中已定义 4 个复合索引，但数据库中不存在：

```sql
-- models.py 已定义但 DB 中缺失:
CREATE INDEX ix_documents_kb_status ON documents (kb_id, status);     -- ❌ 不存在
CREATE INDEX ix_documents_kb_md5 ON documents (kb_id, file_md5);      -- ❌ 不存在
CREATE INDEX ix_documents_kb_created ON documents (kb_id, created_at); -- ❌ 不存在
CREATE INDEX ix_tags_kb_name ON tags (kb_id, name);                   -- ❌ 不存在
```

## 根因

`models.py` 中的 `__table_args__` 索引定义仅对新建表生效（`create_all()`），已有表不会自动添加索引。需通过 Alembic migration 在存量数据库上创建。

`alembic/versions/` 目录仅有 `001_initial_schema.py`，无 W10.7 索引变更的 migration。

## 修复

在 `alembic/versions/` 下创建新 migration：

```bash
cd app && alembic revision --autogenerate -m "w10_7_add_composite_indexes"
alembic upgrade head
```

或直接执行 SQL：
```sql
CREATE INDEX IF NOT EXISTS ix_documents_kb_status ON documents (kb_id, status);
CREATE INDEX IF NOT EXISTS ix_documents_kb_md5 ON documents (kb_id, file_md5);
CREATE INDEX IF NOT EXISTS ix_documents_kb_created ON documents (kb_id, created_at);
CREATE INDEX IF NOT EXISTS ix_tags_kb_name ON tags (kb_id, name);
```
