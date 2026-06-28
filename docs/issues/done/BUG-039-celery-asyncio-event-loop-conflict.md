# BUG-039: Celery asyncio 事件循环冲突导致 PDF/文档解析链断裂

| 属性 | 值 |
|------|-----|
| 发现日期 | 2026-06-28 |
| 严重程度 | **严重** / Critical |
| 影响范围 | 所有文档的 Embedding 和 KG 构建任务 |
| 责任部门 | 后端开发组 |
| 状态 | Open |

## 现象

1. 上传 PDF 后一直显示「📤 已上传」状态，块数为 0
2. 文档永远不进入「就绪」状态
3. 其他格式文档的 embedding / KG 构建也间歇性失败

## 根因

Celery Worker 使用 `prefork` 池（`--concurrency=4`），每个 ForkPoolWorker 进程通过 `fork()` 创建。父进程创建的 asyncio event loop 在 fork 后处于不可用状态，但 `parse_document` 下游触发的 `embed_document` 和 `build_knowledge_graph` 任务都需要用 `asyncio.new_event_loop()` 重新创建 loop。

问题在于这些任务中创建的 asyncpg/neo4j 连接复用了父进程的底层资源，导致 `RuntimeError: Task got Future attached to a different loop`。

Celery 日志：
```
embed_document[...]: Embedding 任务失败: Future attached to a different loop
embed_document[...] retry: Retry in 60s
build_knowledge_graph[...]: KG 构建任务失败: Future attached to a different loop
build_knowledge_graph[...] retry: Retry in 120s
```

`parse_document` 设置 `doc.status = "ready"` 在触发下游任务**之前**，但 `asyncio.new_event_loop()` + `loop.run_until_complete()` 模式在 prefork worker 中不稳定。

## 修复方案

修改 `docker-compose.yml` 中 celery-worker 的命令，将并发池从 `prefork` 改为 `solo` 或 `threads`：

```yaml
# 方案 A：单进程（最简单，适合低负载）
command: celery -A tasks.celery_app worker --loglevel=info --pool=solo

# 方案 B：线程池（支持并发，线程间共享 event loop）
command: celery -A tasks.celery_app worker --loglevel=info --pool=threads --concurrency=4
```

**推荐方案 B**（`--pool=threads`），因为：
- 线程池中 asyncio event loop 可以正确共享
- 保持并发能力（`--concurrency=4`）
- I/O 密集型任务（文件读写、HTTP 调用）用线程池足够

## 影响

文档上传后 parse_document 可能执行，但后续 embedding（Milvus 向量化）和 KG 构建（Neo4j 实体关系）全部失败重试，导致：
- 文档虽然有 chunk 但在 Milvus/ES 中没有向量数据 → 无法被检索
- 知识图谱无实体数据
- 用户体验：文档一直是「已上传」或 chunk_count=0
