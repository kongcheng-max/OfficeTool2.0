# BUG-062: 批量上传时 Celery Worker 线程不足导致部分文档任务饿死

| 属性 | 值 |
|------|---|
| **严重级别** | 🟢 Low |
| **影响模块** | Celery 任务调度 |
| **发现方式** | Docker 全量环境批量上传测试 |
| **状态** | Open |
| **发现日期** | 2026-07-09 |

---

## 现象

批量上传 5 个文档（HTML/JSON/CSV/XML/MD），4 个正常完成（uploaded → processing → ready），**1 个永远停留在 `uploaded`**，parse 任务从未被 worker 执行。

Celery 配置：`--pool=threads --concurrency=4`

---

## 根因

`--concurrency=4` 限制了同时运行的任务数为 4。上传 5 个文档时，5 个 `parse_document.delay()` 被提交到 Redis 队列：

```
Worker 线程池 (4 slots):
  Thread-1: parse(t.csv)   → embed → kg_build
  Thread-2: parse(t.json)  → embed → kg_build
  Thread-3: parse(t.xml)   → embed → kg_build
  Thread-4: parse(t.md)    → embed → kg_build
  队列等待: parse(t.html)  ← 永远等不到

4 个线程都在跑 parse → embed → kg_build 三级任务链，
后续又有 embed + kg_build 新任务被塞进队列前端，
排队的 parse(t.html) 被不断插队，形成"饿死"。
```

每个文档触发 3 个 Celery 任务（parse → embed → kg_build），5 个文档 = 15 个任务。4 个线程处理 15 个任务时，部分任务因调度顺序永远轮不到。

---

## 复现步骤

1. Docker 环境：`docker compose up -d`，确认 Celery `--pool=threads --concurrency=4`
2. 批量上传 5+ 个小文件
3. 观察文档状态：N-1 个变为 ready，1 个永远 uploaded

---

## 影响

- 🟢 轻量环境偶发，生产环境影响小（生产应配置更高并发）
- 🟢 用户可刷新后手动重试，没有数据丢失风险

---

## 修复建议

**方案 A**：提高 Celery 并发数
```yaml
# docker-compose.yml
command: celery ... --pool=threads --concurrency=8
```

**方案 B**：将 embed + kg_build 作为 parse 任务的同步后置步骤，不拆分为独立 Celery 任务
```python
# parse.py — 在同一个 task 内顺序执行完 parse → embed → kg
async def _async_parse(doc_id):
    ...  # parse
    await _async_embed(doc_id)    # 同步等待
    await _async_build_kg(doc_id) # 同步等待
```

这样可以确保 parse 任务完成后，embed 和 kg 直接在同一个线程内执行，不额外占用 Celery 队列。

**方案 C**：任务优先级队列（Celery task priority），让 parse 优先于 embed/kg
