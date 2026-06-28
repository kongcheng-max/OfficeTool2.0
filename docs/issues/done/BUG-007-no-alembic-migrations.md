# BUG-007: 无 Alembic 数据库迁移脚本

| 属性 | 值 |
|------|---|
| **严重级别** | 🟡 Medium |
| **影响 AC** | AC06, AC08 |
| **发现方式** | 代码审查 |
| **状态** | Open |

## 现象
`app/alembic/versions/` 目录为空，无任何迁移脚本。项目依赖 `Base.metadata.create_all()` 在应用启动时创建表。

## 根因
MVP 阶段未生成初始迁移。

## 影响
- 数据库 Schema 变更无版本控制
- 多环境部署时可能产生不一致的表结构
- 无法安全回滚

## 修复建议
```bash
cd app
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```
