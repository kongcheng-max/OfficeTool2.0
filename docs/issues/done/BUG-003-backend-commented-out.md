# BUG-003: Backend 服务在 docker-compose.yml 中被注释

| 属性 | 值 |
|------|---|
| **严重级别** | 🟠 High |
| **影响 AC** | AC08 |
| **发现方式** | 代码审查 |
| **状态** | Open |

## 现象
`docker compose up` 不会启动 FastAPI 后端，只有基础设施服务 (PG, Redis, MinIO, etcd, Milvus, Celery) 会启动。

## 根因
`app/docker-compose.yml` 中 backend 服务块被整段注释：
```yaml
# ========== 后端 API (可选，开发用 uvicorn 直接启动) ==========
# backend:
#   build: .
#   container_name: officetool-backend
#   ports:
#     - "8000:8000"
#   ...
```

注释说明是"开发用 uvicorn 直接启动"，但这与 AC08 "Docker Compose 一键启动所有服务" 矛盾。

## 影响
AC08 验收失败 — 无法通过 `docker compose up` 一键启动完整系统。用户需要手动启动 uvicorn。

## 修复建议
1. 取消注释 backend 服务块
2. 确保 Dockerfile 中 CMD 或 command 字段正确启动 FastAPI（如 `uvicorn main:app --host 0.0.0.0 --port 8000`）
