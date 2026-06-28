# BUG-020: Docker 容器内 Celery/Milvus/LLM 三个链路断裂导致 chunk_count=0 且问答无结果

| 属性 | 值 |
|------|---|
| **严重级别** | 🔴 Critical |
| **影响 AC** | AC01, AC02, AC03, AC04 |
| **发现方式** | 人工手动测试 |
| **发现人** | 产品/用户 |
| **状态** | Fixed |

## 现象
1. 上传文档后 chunk_count 始终为 0，状态始终为 `uploaded`
2. 问答提示"抱歉，未能在知识库中找到相关信息"
3. 后台实际上传成功但无法使用

## 根因（3 层断裂）

**断裂1 — Celery 任务无法提交**: backend 容器缺少 `CELERY_BROKER_URL`，默认 `redis://localhost:6379/1` 无法连接 Redis 容器 → `parse_document.delay()` 静默失败

**断裂2 — Celery Fork 子进程 import 失败**: Worker fork 后 `sys.path` 不含 `/app` → `No module named 'models'` → 任务无限重试

**断裂3 — Milvus Collection 未自动创建**: `vector_store.get_collection()` 不调用 `create_collection_if_not_exists()` → embedding 写入失败

## 修复
1. `docker-compose.yml`: backend 添加 `CELERY_BROKER_URL=redis://redis:6379/1`，添加 LLM 环境变量
2. `docker-compose.yml`: backend + celery 添加 `PYTHONPATH=/app`、`HF_ENDPOINT=https://hf-mirror.com`
3. `tasks/celery_app.py`: 添加 `sys.path.insert(0, '/app')` 确保 fork 子进程可导入模块
4. `engine/rag/vector_store.py`: `get_collection()` 中添加 `create_collection_if_not_exists()` 自动建表

## 验证
- 上传文档 → 20s 后 status=ready, chunks=6 ✅
- Celery log: `Embedding 完成` + `Milvus 写入完成` ✅
- 问答: "AI应用开发有几个阶段？" → 返回 5 阶段详细表格 + 5 条来源 ✅
