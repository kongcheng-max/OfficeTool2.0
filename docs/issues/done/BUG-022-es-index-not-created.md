# BUG-022: Elasticsearch 索引未创建导致 BM25 通路失效

| 属性 | 值 |
|------|---|
| **严重级别** | 🔴 Critical |
| **影响 AC** | Week 5: ES BM25 检索, Week 7: 混合检索 RRF |
| **发现方式** | 运行时测试 |
| **状态** | Open |

## 现象
Celery embed 任务日志显示：
```
HEAD http://elasticsearch:9200/officetool_chunks [status:400]
ES 写入失败（可能未启动）: BadRequestError(400, 'None')
```
直接查询 ES：
```json
{"error":{"type":"index_not_found_exception","reason":"no such index [officetool_chunks]"}}
```

## 根因
`es_store.ensure_index()` 方法存在，但在 `tasks/embed.py` 调用 `es_store.index_chunks()` 之前未显式调用 `ensure_index()`。查看代码发现 ES store 的 `index_chunks()` 方法可能需要先检查并创建索引。

## 影响
- BM25 关键词检索完全不可用
- 混合检索 (RRF) 只剩向量 + KG 两路，比设计少一路
- 文档上传后 ES 中无数据

## 修复
在 `es_store.index_chunks()` 开头增加 `self.ensure_index()` 自动创建索引。
