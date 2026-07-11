# BUG-069: Cross-encoder 精排模型代码已实现但未接入问答检索管线

| 属性 | 值 |
|------|---|
| **严重级别** | 🔴 Critical |
| **影响模块** | 检索精排 → 问答质量 |
| **发现方式** | Week 9 代码审查 + 集成测试 |
| **状态** | 🔴 待修复 |
| **发现日期** | 2026-07-11 |

---

## 现象

`engine/rag/reranker.py` 中已实现 `cross_encoder_rerank()` 函数和 `_get_cross_encoder()` 懒加载（bge-reranker-v2-m3 + bi-encoder 降级），但该函数在整个项目中**从未被调用**。

```
$ grep -rn "cross_encoder_rerank" app/
app/engine/rag/reranker.py:8:  cross_encoder_rerank(query, hits, top_k=5) → List[Dict]
app/engine/rag/reranker.py:13:  from engine.rag.reranker import rrf_fusion, cross_encoder_rerank
app/engine/rag/reranker.py:109:async def cross_encoder_rerank(
```

仅在自身文件中出现（docstring 示例 + 定义），`qa_service.py` 和 `retriever.py` 均未导入调用。

## 根因

`_retrieve()` → `HybridRetriever.retrieve()` → `rrf_fusion()` 后缺少 `cross_encoder_rerank()` 调用步骤。RRF 融合结果直接返回给 LLM，未经精排。

## 影响

- 🔴 精排模型未生效，检索结果仅依赖 RRF 融合排序
- 🔴 Week 9 核心交付物（精排准确率 > 纯 RRF）无法验收
- 额外问题：`FlagEmbedding` 包未加入 Docker 镜像依赖，即使接入也无法加载 bge-reranker-v2-m3

## 修复建议

1. 在 `qa_service.py` 的 `_retrieve()` 中，RRF 融合后调用 `cross_encoder_rerank()`:
```python
fused = rrf_fusion(all_hits, k=60)
fused = await cross_encoder_rerank(query, fused, top_k=top_k)
```

2. Dockerfile 添加 `FlagEmbedding` 依赖: `RUN pip install FlagEmbedding`
