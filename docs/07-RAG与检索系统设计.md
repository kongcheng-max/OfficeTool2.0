# 07 — RAG 与检索系统设计

> **版本**: v3.0 | **日期**: 2026-06-27 | **作者**: 产品部/架构组
> **🏢 主责部门**: **AI**（算法） | **协作**: BE（向量库/ES集成、API接入）
> **关联**: [架构设计](./02-系统架构设计.md) | [解析引擎](./06-文档解析引擎设计.md) | [KG设计](./08-知识图谱与实体抽取设计.md)

---

## 目录

1. [RAG 管道总览](#1-rag-管道总览)
2. [文本分块策略](#2-文本分块策略)
3. [Embedding 方案](#3-embedding-方案)
4. [向量数据库](#4-向量数据库)
5. [混合检索架构](#5-混合检索架构)
6. [RRF 融合排序](#6-rrf-融合排序)
7. [重排序优化](#7-重排序优化)
8. [Prompt 工程](#8-prompt-工程)
9. [检索质量评估](#9-检索质量评估)

---

## 1. RAG 管道总览

### 1.1 完整管道

```
┌─────────────────────────────────────────────────────────────────────┐
│                          INDEXING (离线/异步)                        │
│                                                                     │
│  Document ──→ Parse ──→ Split ──→ Embed ──→ [Milvus + ES]         │
│               (解析)     (分块)     (向量化)     (双写存储)          │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                          QUERYING (在线/实时)                        │
│                                                                     │
│  Question ──→ Embed ──→ Hybrid Search ──→ RRF Merge ──→ Rerank     │
│              (向量化)    (三路并行检索)      (融合排序)     (精排)    │
│                                                                     │
│                                ↓                                    │
│                          LLM Generate                               │
│                     (Prompt + Context + Question)                    │
│                                ↓                                    │
│                     Answer + Sources + Confidence                    │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 核心模块

| 模块 | 职责 | 实现位置 |
|------|------|---------|
| Splitter | 文档分块，决定检索粒度 | `engine/rag/splitter.py` |
| Embedder | 文本向量化 | `engine/rag/embedder.py` |
| VectorStore | 向量存储与检索 | `engine/rag/vector_store.py` |
| Retriever | 多路检索编排 | `engine/rag/retriever.py` |
| Reranker | 结果重排序 | `engine/rag/reranker.py` |
| PromptBuilder | Prompt 模板构建 | `engine/rag/template.py` |

---

## 2. 文本分块策略

### 2.1 分块原则

| 原则 | 说明 |
|------|------|
| **语义完整** | 每个 Chunk 是一个语义完整单元（段落/章节），不截断句子 |
| **大小适中** | 中文 500-1000 tokens，英文 300-600 tokens |
| **重叠适当** | Chunk 间 10-20% 重叠，避免关键信息在边界丢失 |
| **保留元数据** | 每个 Chunk 携带来源文档、页码、章节等元信息 |

### 2.2 分块方案

使用 LangChain `RecursiveCharacterTextSplitter` 改良版：

```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

class ChineseTextSplitter:
    """中文文档分块器"""

    def __init__(self):
        self.splitter = RecursiveCharacterTextSplitter(
            separators=[
                "\n\n",    # 段落分隔
                "\n",      # 换行
                "。",      # 中文句号
                "；",      # 中文分号
                ".",       # 英文句号
                ";",       # 英文分号
                " ",       # 空格（最后手段）
            ],
            chunk_size=800,        # 目标大小：800 字符
            chunk_overlap=120,     # 重叠：120 字符 (15%)
            length_function=len,
        )

    def split(self, text: str, metadata: dict) -> List[Chunk]:
        docs = self.splitter.create_documents([text], [metadata])
        return [Chunk(content=d.page_content, metadata=d.metadata) for d in docs]
```

### 2.3 特殊类型处理

| 文档类型 | 分块策略 |
|------|---------|
| **表格** | 表格作为一个完整 Chunk，不拆分（保持数据完整性） |
| **代码块** | 整块保留，不按标点拆分 |
| **列表** | 优先在列表边界切分 |
| **长文档 (>50页)** | 按章节/页分组后再分块 |

### 2.4 分块参数调优指南

| 参数 | 推荐值 | 影响 |
|------|--------|------|
| chunk_size | 800 | ↑ 更大上下文 / ↓ 检索精度 |
| chunk_overlap | 120 | ↑ 减少信息丢失 / ↓ 存储效率 |
| 最小 Chunk | 50 字符 | 过滤无意义碎片 |

---

## 3. Embedding 方案

### 3.1 模型选型

| 模型 | 维度 | 中文能力 | 推荐场景 | 来源 |
|------|------|---------|---------|------|
| **text2vec-large-chinese** | 1024 | ⭐⭐⭐⭐⭐ | **主力推荐** | 开源/HuggingFace |
| bge-large-zh-v1.5 | 1024 | ⭐⭐⭐⭐⭐ | 备选 | BAAI |
| m3e-large | 1024 | ⭐⭐⭐⭐ | 轻量备选 | Moka AI |
| 通义 Embedding API | 1536 | ⭐⭐⭐⭐ | 云端方案 | 阿里云 |

### 3.2 Embedding 实现

```python
from sentence_transformers import SentenceTransformer

class Embedder:
    def __init__(self, model_name: str = "shibing624/text2vec-base-chinese"):
        self.model = SentenceTransformer(model_name)

    def embed(self, texts: List[str]) -> List[List[float]]:
        """批量向量化"""
        embeddings = self.model.encode(
            texts,
            normalize_embeddings=True,  # L2 归一化 → 余弦相似度
            show_progress_bar=False,
            batch_size=32,
        )
        return embeddings.tolist()

    def embed_query(self, query: str) -> List[float]:
        """单条查询向量化"""
        return self.model.encode(
            query,
            normalize_embeddings=True,
        ).tolist()
```

### 3.3 Embedding 缓存策略

- **文档 Chunk Embedding**: 持久化到 Milvus，不重复计算
- **查询 Embedding**: 相同查询 1 小时内 Redis 缓存
- **模型热更新**: 支持配置更换模型后全量重建向量

---

## 4. 向量数据库

### 4.1 Milvus 配置

| 配置项 | 值 | 说明 |
|------|------|------|
| 索引类型 | HNSW | 高召回+低延迟（Phase 3 优化后） |
| IVF_PQ | 备选 | 内存效率更高（MVP 阶段可用） |
| 度量方式 | COSINE | 余弦相似度（配合 L2 归一化） |
| nlist | 1024 | IVF 聚类数 |
| nprobe | 32 | 搜索时探测聚类数 |

### 4.2 Collection Schema

```yaml
Collection: doc_chunks
Fields:
  - chunk_id: VARCHAR (primary key, max_length=64)
  - kb_id: VARCHAR (partition key, max_length=36)
  - doc_id: VARCHAR (max_length=36)
  - content: VARCHAR (max_length=65535)   # 原文存储
  - embedding: FLOAT_VECTOR (dim=1024)     # 向量
  - metadata: JSON                         # 元信息

Index:
  - field: embedding
  - index_type: HNSW
  - metric_type: COSINE
  - params: {M: 16, efConstruction: 200}

Search Params:
  - ef: 64   # HNSW 搜索参数，越大越精确但越慢
  - top_k: 20
```

### 4.3 Qdrant 备选方案

轻量级场景提供 Qdrant 备选，API 保持一致（通过 `VectorStore` 抽象）。

```python
class VectorStore(ABC):
    @abstractmethod
    async def insert(self, chunks: List[ChunkWithVector]): ...
    @abstractmethod
    async def search(self, query_vector: List[float], kb_id: str, top_k: int = 20) -> List[SearchResult]: ...
    @abstractmethod
    async def delete(self, doc_id: str): ...
```

---

## 5. 混合检索架构

### 5.1 三路并行检索

```
                      用户问题
                         │
               ┌─────────┼─────────┐
               │         │         │
               ▼         ▼         ▼
         ┌─────────┐┌─────────┐┌─────────┐
         │ 向量检索  ││ BM25检索 ││ 图谱检索  │
         │ (Milvus) ││  (ES)   ││ (Neo4j) │
         │ Top-20   ││ Top-20  ││ Top-10  │
         └────┬────┘└────┬────┘└────┬────┘
              │          │          │
              └──────────┼──────────┘
                         │
                         ▼
                ┌─────────────────┐
                │   RRF 融合排序    │
                │  (Reciprocal    │
                │   Rank Fusion)  │
                └────────┬────────┘
                         │
                         ▼
                  Top-10 结果
```

### 5.2 各检索器说明

| 检索器 | 引擎 | 优势 | 劣势 | 阶段 |
|------|------|------|------|------|
| **向量检索** | Milvus | 语义理解、同义词、跨语言 | 对数字/精确词不敏感 | P0 |
| **BM25 检索** | Elasticsearch | 精确匹配、关键词、数字 | 无语义理解 | P1 |
| **图谱检索** | Neo4j | 实体关联、知识结构 | 依赖图谱质量 | P1 |

### 5.3 ES BM25 实现

```python
class BM25Retriever:
    def __init__(self, es_client):
        self.es = es_client

    async def search(self, query: str, kb_id: str, top_k: int = 20) -> List[SearchResult]:
        body = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"content": query}},
                        {"term": {"kb_id": kb_id}}
                    ]
                }
            },
            "size": top_k,
            "highlight": {
                "fields": {"content": {"fragment_size": 150, "number_of_fragments": 3}}
            }
        }
        resp = await self.es.search(index="chunks", body=body)
        return self._parse_results(resp)
```

### 5.4 图谱检索

```python
class KGRetriever:
    def __init__(self, neo4j_driver):
        self.driver = neo4j_driver

    async def search(self, query: str, kb_id: str, top_k: int = 10):
        # 1. 从 Query 中提取实体名 (快速正则 + 可能的 LLM NER)
        entities = self._extract_entity_mentions(query)

        # 2. 在 Neo4j 中查询与这些实体关联的文档块
        cypher = """
        MATCH (e:Entity)-[:MENTIONED_IN]->(d:Document)
        WHERE e.name IN $entities AND d.kb_id = $kb_id
        RETURN d.chunk_id, d.content, e.name as entity
        LIMIT $top_k
        """
        records = await self.driver.run(cypher, entities=entities, kb_id=kb_id, top_k=top_k)
        return self._format_results(records)
```

---

## 6. RRF 融合排序

### 6.1 算法

```
RRF_score(chunk) = Σ 1 / (k + rank_i(chunk))

其中:
- k = 60 (平滑参数，防止单个极低排名主导分数)
- rank_i(chunk) = chunk 在第 i 路检索器中的排名

三路加和 → 按总分降序排列 → 返回 Top-N
```

### 6.2 实现

```python
def rrf_fusion(results_lists: List[List[SearchResult]], k: int = 60) -> List[SearchResult]:
    """
    输入: 各路检索器的排序结果列表
    输出: RRF 融合后的排序结果
    """
    scores = defaultdict(float)

    for result_list in results_lists:
        for rank, result in enumerate(result_list, start=1):
            scores[result.chunk_id] += 1.0 / (k + rank)
            # 同时保留最好的 result 对象（取最高分的来源）
            if result.chunk_id not in best_result or scores[result.chunk_id] > old_best:
                best_result[result.chunk_id] = result

    # 按 RRF 分数降序排列
    sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

    return [best_result[cid] for cid in sorted_ids]
```

### 6.3 权重调优（Phase 3）

可对不同检索器引入权重：

```
weighted_RRF(chunk) = w_vector/(k+rank_vector) + w_bm25/(k+rank_bm25) + w_kg/(k+rank_kg)
默认权重: w_vector=1.0, w_bm25=1.0, w_kg=0.8
```

---

## 7. 重排序优化

### 7.1 Cross-encoder 精排

在 RRF 返回 Top-20 基础上，使用 Cross-encoder 对每个候选做精细打分。

```python
from sentence_transformers import CrossEncoder

class ReRanker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-large"):
        self.model = CrossEncoder(model_name, max_length=512)

    def rerank(self, query: str, candidates: List[SearchResult]) -> List[SearchResult]:
        pairs = [(query, c.content[:512]) for c in candidates]
        scores = self.model.predict(pairs)

        for c, score in zip(candidates, scores):
            c.rerank_score = float(score)
            c.final_score = c.rrf_score * 0.3 + c.rerank_score * 0.7

        candidates.sort(key=lambda x: x.final_score, reverse=True)
        return candidates[:5]  # 返回 Top-5
```

### 7.2 阶段策略

| 阶段 | 方案 | 延迟 |
|------|------|------|
| MVP | 仅 RRF (向量检索) | ~100ms |
| Beta | RRF (向量+BM25+KG) | ~200ms |
| GA | RRF + Cross-encoder | ~500ms (含精排) |

---

## 8. Prompt 工程

### 8.1 问答 Prompt 模板

```jinja2
## 角色
你是一个专业的企业文档问答助手。请严格基于以下提供的文档内容回答问题。
如果文档内容不足以回答问题，请如实告知"文档中未找到相关信息"，不要编造。

## 知识库上下文
{% for chunk in chunks %}
--- [来源: {{ chunk.metadata.source }}{% if chunk.metadata.page %}, 第{{ chunk.metadata.page }}页{% endif %}] ---
{{ chunk.content }}
{% endfor %}

## 用户问题
{{ question }}

## 回答要求
1. 直接回答问题，语言简洁准确
2. 如果涉及多个文档，请综合不同文档的信息
3. 在答案末尾列出引用的来源文档和页码
4. 如果信息不足以回答，回复"抱歉，当前知识库中未找到相关信息"
```

### 8.2 多轮对话 Prompt

```jinja2
## 对话历史
{% for msg in history %}
{{ msg.role }}: {{ msg.content }}
{% endfor %}

## 知识库上下文
{{ context }}

## 当前问题
{{ question }}

请基于以上对话历史和知识库上下文回答问题。
```

### 8.3 Prompt 优化原则

- System Prompt 明确角色和约束
- Context 按分数排序，相关性最高的在前
- Context 总量控制 ≤ 4000 tokens（避免超过 LLM 上下文窗口）
- 指令清晰：不编造、给来源、说不知道

---

## 9. 检索质量评估

### 9.1 评估指标

| 指标 | 定义 | 目标 |
|------|------|------|
| **Recall@K** | Top-K 结果中包含正确答案的比例 | Recall@20 ≥ 90% |
| **MRR** | Mean Reciprocal Rank — 第一个正确答案的排名倒数均值 | MRR ≥ 0.7 |
| **NDCG@K** | 考虑排名位置和相关性等级 | NDCG@10 ≥ 0.75 |
| **答案准确率** | 人工评估答案是否正确完整 | ≥ 85% |

### 9.2 评估数据集

- 每个知识库准备 50 道问题 + 标注答案 + 标注来源
- 使用 RaiEval / LangSmith 等评估框架
- 每次检索策略变更后重新评估对比

### 9.3 质量改进闭环

```
评估结果 → 分析 Bad Case → 调整策略 → 重新评估 → 达标
           ├── 分块策略不对？  → 调整 chunk_size/overlap
           ├── Embedding 不好？ → 换模型
           ├── 检索漏召回？     → 增加 BM25/图谱权重
           └── LLM 不听话？    → 优化 Prompt
```

---

> 📎 **关联**: [解析引擎](./06-文档解析引擎设计.md) | [KG设计](./08-知识图谱与实体抽取设计.md) | [架构设计](./02-系统架构设计.md) | [部署运维](./10-部署与运维方案.md)
