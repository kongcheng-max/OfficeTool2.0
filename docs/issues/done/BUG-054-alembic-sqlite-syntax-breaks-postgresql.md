# BUG-054: Alembic 迁移脚本使用 SQLite 语法，PostgreSQL 部署时迁移失败

| 属性 | 值 |
|------|---|
| **严重级别** | 🔴 Critical |
| **影响模块** | 数据库迁移、Docker 部署 |
| **发现方式** | 代码审查 |
| **状态** | ✅ Done — 2026-07-06 验收通过 |
| **发现日期** | 2026-07-06 |

## 现象

`alembic/versions/001_initial_schema.py` 中的 `server_default` 使用了 SQLite 专有语法 `(datetime('now'))`，在 PostgreSQL 环境执行 `alembic upgrade head` 时会报错，导致数据库初始化失败。

## 根因

`alembic/versions/001_initial_schema.py` 中所有 datetime 列的 `server_default` 定义：

```python
sa.Column("created_at", sa.DateTime(timezone=True),
          server_default=sa.text("(datetime('now'))"), nullable=False),
```

`datetime('now')` 是 SQLite 的内置函数语法。PostgreSQL 中应使用 `now()` 或 `CURRENT_TIMESTAMP`。

**注意**：这是迁移脚本中的硬编码问题，与 ORM 模型定义无关。ORM 模型使用 Python 侧的 `default=_utcnow` 函数，不受影响。但 `alembic upgrade head` 执行的是迁移脚本中的 SQL 语句。

## 复现步骤

1. 使用 PostgreSQL 作为数据库
2. 运行 `alembic upgrade head`
3. 观察错误：`function datetime(text) does not exist`

## 影响

- 🔴 PostgreSQL 环境下无法通过 Alembic 创建数据库表
- 🔴 Docker Compose 部署流程中，Backend 容器启动后的自动迁移会失败

## 修复建议

将迁移脚本中的 `server_default` 改为跨数据库兼容的方式，或使用 Alembic 的 `render_as_batch` + 数据库检测：

**方案 A**: 移除 server_default（推荐）
模型已通过 Python `default=_utcnow` 处理时间戳，不需要数据库层默认值。直接删除 `server_default` 即可：

```python
sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
```

**方案 B**: 使用数据库条件判断
```python
from alembic import op
# 检测数据库方言
if op.get_context().dialect.name == 'postgresql':
    server_default = sa.text("now()")
else:
    server_default = sa.text("(datetime('now'))")
```

> 推荐方案 A，因为 Python 层 default 已足够。
