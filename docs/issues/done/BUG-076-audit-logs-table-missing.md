# BUG-076: audit_logs 表未创建，审计日志中间件写入静默失败

| 属性 | 值 |
|------|---|
| **严重级别** | 🔴 Critical |
| **影响模块** | 审计日志 → 安全合规 |
| **发现方式** | Week 11 验收测试 |
| **状态** | 🔴 待修复 |
| **发现日期** | 2026-07-11 |

---

## 现象

1. `audit_logs` 表在数据库中不存在：`relation "audit_logs" does not exist`
2. `AuditMiddleware` 尝试写入审计日志时静默失败（异常被 catch 后仅 debug log）
3. `GET /api/v1/admin/audit-logs` 查询失败

## 根因

`models/audit_log.py` 定义了 `AuditLog` 模型，且 `main.py` 已注册 `AuditMiddleware`，但缺少对应的 Alembic migration 创建表。与 BUG-074（索引 migration 缺失）属于同一类问题。

## 修复

创建 Alembic migration 或在数据库中手动创建表：

```sql
CREATE TABLE IF NOT EXISTS audit_logs (
    id VARCHAR(32) PRIMARY KEY,
    user_id VARCHAR(32),
    username VARCHAR(64),
    action VARCHAR(64) NOT NULL,
    resource_type VARCHAR(32),
    resource_id VARCHAR(32),
    detail TEXT,
    ip_address VARCHAR(45),
    user_agent VARCHAR(256),
    success BOOLEAN DEFAULT TRUE,
    status_code INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

或执行:
```bash
cd app && alembic revision --autogenerate -m "w11_add_audit_logs" && alembic upgrade head
```

## 备注

此 Bug 与 BUG-074（缺少索引 migration）叠加影响：即使创建了 `audit_logs` 表，W10.7 的复合索引也需要一并迁移。
