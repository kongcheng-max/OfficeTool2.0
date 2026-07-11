# BUG-067: ES BM25 索引写入因 Event Loop 冲突静默失败，导致大量文档仅向量可检

| 属性 | 值 |
|------|---|
| **严重级别** | 🔴 Critical |
| **影响模块** | Embedding 管线 → ES 存储 → 混合检索 |
| **发现方式** | 第二阶段测试知识库 8 份文档全量 Q&A 验收 |
| **状态** | ✅ 已修复 — 2026-07-11 验收通过 |
| **发现日期** | 2026-07-11 |
| **修复日期** | 2026-07-11 |

---

## 现象

`第二阶段测试知识库` 8 份文档全部在 ES 中的 BM25 索引为空（Milvus 有数据，ES 全空）。5 份小文件在前端显示「就绪」但 Q&A 完全检索不到。

## 根因

1. `es_store.py` 的 `AsyncElasticsearch` 客户端是模块级单例，首次创建时绑定当前 event loop。在 Celery `_run_async_safe` → ThreadPoolExecutor → `asyncio.run()` 的新 event loop 中调用时，单例客户端仍绑着旧 loop → `Event loop is closed`
2. `embed.py` catch 异常后只记 warning，仍设 `doc.status = "ready"`

## 修复内容

`es_store.py`:
- 新增 `_new_client()` 方法创建独立 ES 客户端
- `index_chunks()` 和 `delete_by_doc_id()` 每次调用创建新客户端 + `try/finally close`
- `ensure_index()`, `_detect_analyzer()`, `_get_mapping()` 接受 `client` 参数
- `search()` 保持单例模式（FastAPI 稳定 event loop）

## 验收结果（2026-07-11）✅ 通过

### 验收数据

| 文档 | Milvus | ES | Q&A 检索 |
|------|:--:|:--:|:--:|
| 验收标准.md (3 chunks) | ✅ 3条 | ✅ 3条 | ✅ 命中 |
| 最终测试报告.txt (1 chunk) | ✅ 1条 | ✅ 1条 | ✅ "P95延迟487ms，并发120用户" |

Celery 日志确认不再报 `Event loop is closed`：
```
06:57:26 | ES 写入完成: 3 条
07:02:47 | ES 写入完成: 1 条
```

### 遗留注意

- Embed 任务首次 DB 查询（`_async_embed:94`）仍偶发 event loop 冲突，但重试后可成功
- 偶发 parse 任务 `received` 后无后续（task c2bfb9e7），需单独排查
