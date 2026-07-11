# BUG-064: RAG 语义检索偏差 —「微服务」查询匹配到无关《白鹿原》文档

| 属性 | 值 |
|------|---|
| **严重级别** | 🟠 High |
| **影响模块** | RAG 检索管道（向量检索 + RRF 融合） |
| **发现方式** | 前端问答页面运行时测试 |
| **状态** | Open |
| **发现日期** | 2026-07-11 |

---

## 现象

知识库中有两份文档：
- 《Java 并发、分布式与微服务》PDF（预期命中）
- 《白鹿原》推荐.pptx（不应命中）

用户提问「我想知道微服务的概念」，系统**只检索到《白鹿原》PPTX**，返回"无《白鹿原》相关资料"，完全没有回应微服务相关问题。

---

## 根因分析

### 大概率原因：Java PDF 的 Embedding 未写入 Milvus/ES

最可能的场景：
1. 《白鹿原》PPTX 上传时 Celery Worker 正常运行 → Embedding 写入成功 → 可检索 ✅
2. 《Java》PDF 上传时 Embedding 任务失败（event loop 冲突 → 重试 → 最终可能失败）
   → Milvus/ES 中没有该文档的向量 → **向量搜索根本找不到它**
3. 用户提问"微服务" → 检索只能命中唯一已索引的《白鹿原》PPTX → 返回无关内容

**验证方法**：在 Swagger 或 curl 直接调搜索 API，检查 PDF 是否在结果中：
```
GET /api/v1/kb/{kb_id}/search/hybrid?q=微服务
```
如果 PDF 不出现在结果里 → 确认是索引缺失。

### 可能的代码层问题

#### 1. `cross_encoder_rerank` 是占位实现

`engine/rag/reranker.py:75-108`：Cross-encoder 精排是**空壳**，只做了 RRF 分 × 0.6 + 原始分 × 0.4 的加权。没有真正的语义相关性重排序。Phase 3 的 `bge-reranker-large` 未集成。

如果有多篇文档被召回，缺少 Cross-encoder 会导致排序不准，无关内容可能排到前面。

#### 2. RRF 去重 key 可能合并不同 chunk

`engine/rag/rreranker.py:48`：
```python
key = f"{doc_id}|{text_snippet[:100]}"
```

两个不同 chunk 的前 100 字符如果相同（例如都包含相同标题），会被错误合并，丢失一个检索结果。

#### 3. Embedding 模型领域适配不足

当前使用 `shibing624/text2vec-base-chinese`，是通用中文模型。对「Java 微服务」这种技术术语的语义表征能力有限，可能在向量空间中无法很好地区分技术和文学内容。

---

## 影响

- 🟠 用户提问得不到正确答案，RAG 核心价值失效
- 🟠 表面上系统"在运行"，实际上返回垃圾信息
- 🟠 检索结果中缺少目标文档时，LLM 只能基于已有（错误的）上下文强行回答

---

## 修复建议

### P0：确认 Java PDF 是否已索引

这是诊断的第一步，也是最可能的根因：
1. 检查文档状态：PDF 是否 `status=ready` 且 `chunk_count > 0`
2. 调搜索 API 看 PDF 是否出现在结果中
3. 如果不在 → Embedding 任务失败 → 同 BUG-059/060 的 event loop 问题

### P1：集成 Cross-encoder 精排

```python
# engine/rag/reranker.py
async def cross_encoder_rerank(query, hits, top_k=5):
    from FlagEmbedding import FlagReranker
    reranker = FlagReranker('BAAI/bge-reranker-large', use_fp16=True)
    pairs = [[query, hit['chunk_text']] for hit in hits]
    scores = reranker.compute_score(pairs)
    for hit, score in zip(hits, scores):
        hit['rerank_score'] = round(float(score), 4)
    return sorted(hits, key=lambda h: h['rerank_score'], reverse=True)[:top_k]
```

### P2：检索零结果时明确提示，避免 LLM 强行回答

```python
# services/qa_service.py
if not hits:
    return {
        "answer": "知识库中未找到与您问题相关的文档。请确认相关文档已上传并完成解析。",
        "sources": [],
        "confidence": 0.0
    }
```

当前行为是即使检索到无关文档，LLM 也会基于这些文档生成回答，造成"答非所问"。

### P3：RRF key 改进

```python
key = f"{doc_id}|{hashlib.md5(chunk_text.encode()).hexdigest()[:16]}"
```
