# BUG-059: Embedding 任务在 Celery 中静默失败，Milvus/ES 无数据写入

| 属性 | 值 |
|------|---|
| **严重级别** | 🔴 Critical |
| **影响模块** | 文档检索、问答 |
| **发现方式** | Docker 全量环境运行时测试 |
| **状态** | ✅ Done — 2026-07-09 第二次验收通过 |
| **发现日期** | 2026-07-09 |

## 验收记录

**2026-07-09 第一次验收**：
- ❌ Embedding 任务仍然报相同的 event loop 错误，Milvus/ES 无新数据写入

Celery 日志（修复后）：
```
[ERROR] embed_document: Embedding 任务失败 doc_id=xxx:
  Task got Future attached to a different loop
```

`run_embed_sync()` 函数已实现但**从未被调用**。原因：`parse.py:131` 使用 `embed_document.delay(doc_id)` 调度 Celery 任务，任务调度本身成功（Redis 可达），不会触发 except 分支里的 `run_embed_sync` fallback。但任务在 worker 中实际执行时仍然遇到 event loop 冲突。

**需要修改**: 让 parse 任务直接调 `run_embed_sync(doc_id)` 而非 `embed_document.delay(doc_id)`，或将 Celery pool 改为 `--pool=prefork`。

## 现象

文档上传后解析成功（status=ready），但 Embedding 任务在 Celery worker 中失败，导致：

1. Milvus 向量库中没有该文档的 embedding 向量
2. Elasticsearch 中没有该文档的 BM25 索引
3. 向量搜索返回空结果
4. 混合搜索返回空结果
5. 问答 API 虽返回 code=0，但 LLM 检索不到任何上下文，回答 "未能在知识库中找到相关信息"

Celery 日志关键片段：
```
[ERROR] embed_document[xxx]: Embedding 任务失败: Task got Future attached to a different loop
[INFO]  embed_document[xxx] retry: Retry in 60s
[INFO]  开始 Embedding: doc_id=xxx
[INFO]  ✅ 使用真实 Embedding 模型: shibing624/text2vec-base-chinese
[INFO]  HTTP GET model.safetensors "HTTP/1.1 200 OK"
-- 此后无任何日志，任务静默终止 --
```

## 根因

两阶段失败：

**阶段 1**（首次执行）：Celery 线程池模式下的 asyncio event loop 冲突。`run_async_in_worker()` 虽已修复（BUG-039），但 `_async_embed()` 内部创建的某些异步对象（如 httpx Client、DB session）引用了不同 event loop 的 Future，触发 `RuntimeError: attached to a different loop`。任务自动重试。

**阶段 2**（重试执行）：重试时 event loop 冲突不再触发，但下载 400MB 的 Embedding 模型文件后，`SentenceTransformer` 加载模型可能：
- 内存不足导致进程被 OOM Killer 杀掉（容器 MemoryMax=800M，模型 ~400MB + 进程开销）
- 模型加载耗时过长，超出 Celery `task_soft_time_limit`（600s）

无论如何，任务在模型加载后**静默终止**，没有任何完成/失败日志。

## 复现步骤

1. Docker 全量环境 `docker compose up -d`
2. 上传任意文档到知识库
3. 等待 Celery parse 任务完成（doc status → ready）
4. 观察 Celery logs：`embed_document` 任务失败/无结果
5. 调用搜索/问答 API → 无检索结果

## 影响

- 🔴 文档上传后无法被检索
- 🔴 问答功能虽然能用 LLM，但没有上下文，等于没用
- 🔴 向量检索和 BM25 检索全部失效
- 用户上传文档后提问，AI 永远回答 "未找到相关信息"

## 修复建议

**方案 A**（治本）：将 Celery worker 从 `--pool=threads` 改为 `--pool=prefork`，彻底避免 asyncio event loop 冲突：

```yaml
# docker-compose.yml celery-worker command
command: celery -A tasks.celery_app worker --loglevel=info --pool=prefork --concurrency=2
```

**方案 B**（治标）：将 Embedding 逻辑改为同步执行，在 Celery worker 中不创建新的 event loop：

```python
# tasks/embed.py
@celery_app.task(...)
def embed_document(self, doc_id):
    # 使用同步 SentenceTransformer 而非异步
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("shibing624/text2vec-base-chinese")
    ...
```

**方案 C**（临时）：增加 Celery worker 内存限制，确保模型加载有足够内存：

```yaml
# docker-compose.yml
celery-worker:
  deploy:
    resources:
      limits:
        memory: 2G
```

> **推荐方案 A**，因为 prefork 模式天然隔离进程，不存在 event loop 冲突。同时建议增加 worker 内存限制。
