# BUG-001: DummyEmbedder 硬编码导致语义搜索失效

| 属性 | 值 |
|------|---|
| **严重级别** | 🔴 Critical |
| **影响 AC** | AC03, AC04 |
| **发现方式** | 代码审查 |
| **状态** | Open |

## 现象
所有向量搜索使用 `DummyEmbedder`（SHA-256 哈希向量），而非真正的 Embedding 模型。检索结果本质上是随机的，语义相似度搜索完全失效。

## 根因
以下 3 处硬编码了 `DummyEmbedder()`：

1. `app/services/qa_service.py:18` — 全局检索器
   ```python
   _retriever = Retriever(
       embedder=DummyEmbedder(),
       store=vector_store,
   )
   ```

2. `app/tasks/embed.py:70` — Celery 异步 Embedding
   ```python
   embedder = DummyEmbedder()  # MVP 使用 Dummy
   ```

3. `app/engine/rag/embedder.py:62-87` — DummyEmbedder 实现使用 SHA-256 哈希

## 影响
- **AC03 (10s 响应)**: 可能通过（检索快但无意义）
- **AC04 (80% 相关性)**: ❌ 必定失败 — 向量相似度基于哈希碰撞而非语义

## 修复建议
1. 将 `HuggingFaceEmbedder` 接入生产流程
2. 在 `pyproject.toml` 添加 `sentence-transformers` 依赖
3. 通过环境变量/配置控制 Embedder 类型选择
