"""检索器 — 向量检索 + BM25 关键词检索 + 混合编排"""

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from loguru import logger

from engine.rag.embedder import BaseEmbedder
from engine.rag.vector_store import VectorStore


@dataclass
class RetrievalResult:
    """单路检索结果"""
    hits: List[Dict]
    source: str  # "vector" | "bm25" | "kg"
    latency_ms: float


class Retriever:
    """向量检索器"""

    def __init__(self, embedder: BaseEmbedder, store: VectorStore):
        self._embedder = embedder
        self._store = store

    async def retrieve(
        self,
        query: str,
        kb_id: Optional[str] = None,
        top_k: int = 10,
    ) -> List[Dict]:
        """向量相似检索"""
        logger.info(f"向量检索: {query[:100]}...")
        if self._embedder.__class__.__name__ == "DummyEmbedder":
            logger.warning("Vector retrieval skipped because only DummyEmbedder is available")
            return []

        query_vector = await self._embedder.embed_query(query)

        hits = self._store.search(
            query_vector=query_vector,
            kb_id=kb_id,
            top_k=top_k,
        )

        for hit in hits:
            try:
                hit["metadata"] = json.loads(hit.pop("metadata_json", "{}"))
            except (json.JSONDecodeError, TypeError):
                hit["metadata"] = {}
            hit["source"] = "vector"

        logger.info(f"向量检索结果: {len(hits)} 条")
        return hits


class BM25Retriever:
    """BM25 关键词检索器"""

    async def retrieve(
        self,
        query: str,
        kb_id: Optional[str] = None,
        top_k: int = 10,
    ) -> List[Dict]:
        """ES BM25 关键词检索"""
        from engine.rag.es_store import es_store

        logger.info(f"BM25 检索: {query[:100]}...")
        hits = await es_store.search(query=query, kb_id=kb_id, top_k=top_k)

        for hit in hits:
            try:
                hit["metadata"] = json.loads(hit.pop("metadata_json", "{}"))
            except (json.JSONDecodeError, TypeError):
                hit["metadata"] = {}

        logger.info(f"BM25 检索结果: {len(hits)} 条")
        return hits


class KGRetriever:
    """知识图谱检索器 — 利用 Neo4j 实体关联扩展检索

    检索流程: 用户查询 → LLM 抽取查询中的实体关键词 →
              Neo4j Cypher 精确查实体 → 扩展关联实体 → 返回关联文档块
    """

    async def retrieve(
        self,
        query: str,
        kb_id: Optional[str] = None,
        top_k: int = 10,
    ) -> List[Dict]:
        """从 Neo4j 检索与查询中实体相关的文档块

        1. 调用 LLM (prompts 模块) 从 query 中抽取实体关键词
        2. 将实体传给 Neo4j 做精确匹配 + 关联扩展检索
        3. 返回按实体命中数排序的文档块
        """
        try:
            from engine.kg.neo4j_store import neo4j_store
        except ImportError:
            return []

        # 1. 从查询中提取实体关键词
        entities = await self._extract_query_entities(query)

        # 2. 将实体传给 Neo4j 检索 (query 作为 fallback)
        try:
            hits = await neo4j_store.search_related_chunks(
                entities=entities,
                query=query,
                kb_id=kb_id,
                limit=top_k,
            )
        except Exception as e:
            logger.warning(f"Neo4j 检索异常，返回空结果: {e}")
            return []

        for hit in hits:
            # 反序列化 metadata_json 并合并已有 metadata
            try:
                stored_meta = json.loads(hit.pop("metadata_json", "{}"))
            except (json.JSONDecodeError, TypeError):
                stored_meta = {}
            existing = hit.pop("metadata", {})
            if isinstance(existing, dict):
                stored_meta.update(existing)
            hit["metadata"] = stored_meta
            hit["source"] = "kg"
        return hits

    @staticmethod
    async def _extract_query_entities(query: str) -> List[str]:
        """使用 LLM 从用户查询中提取实体关键词

        调用 engine.kg.prompts 中的专用 Prompt 模板进行提取。
        """
        try:
            from engine.kg.prompts import get_query_entity_extraction_messages
            from engine.llm.factory import LLMFactory

            messages = get_query_entity_extraction_messages(query)
            answer = await LLMFactory.generate_with_fallback(
                messages=messages,
                temperature=0.2,
            )

            import re
            json_match = re.search(r"\{.*\}", answer, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
                if isinstance(result, dict):
                    entities = result.get("entities", [])
                    keywords = result.get("keywords", [])

                    logger.info(
                        f"KGRetriever 实体提取: entities={entities}, keywords={keywords}"
                    )

                    # 合并 entities + keywords (去重, entities 优先)
                    all_entities = list(dict.fromkeys(
                        [e for e in entities if isinstance(e, str) and len(e) >= 1]
                        + [k for k in keywords if isinstance(k, str) and len(k) >= 1]
                    ))
                    return all_entities
        except Exception as e:
            logger.warning(f"KGRetriever 实体提取失败: {e}")

        return []


class HybridRetriever:
    """混合检索编排器 — 并行三路检索 + RRF 融合排序"""

    def __init__(
        self,
        vector_retriever: Retriever,
        bm25_retriever: BM25Retriever,
        kg_retriever: Optional[KGRetriever] = None,
    ):
        self.vector = vector_retriever
        self.bm25 = bm25_retriever
        self.kg = kg_retriever

    async def retrieve(
        self,
        query: str,
        kb_id: Optional[str] = None,
        top_k: int = 10,
        use_kg: bool = True,
    ) -> Dict[str, Any]:
        """混合检索：并行三路 → RRF 融合 → Top-K

        Args:
            query: 查询文本
            kb_id: 知识库 ID
            top_k: 最终返回数量
            use_kg: 是否启用图谱检索

        Returns:
            {"hits": List[Dict], "total_sources": {"vector": N, "bm25": N, "kg": N}}
        """
        import asyncio

        from engine.rag.reranker import rrf_fusion

        # 构建并行任务
        tasks = []
        sources = []

        tasks.append(self.vector.retrieve(query, kb_id=kb_id, top_k=top_k * 2))
        sources.append("vector")

        tasks.append(self.bm25.retrieve(query, kb_id=kb_id, top_k=top_k * 2))
        sources.append("bm25")

        if use_kg and self.kg:
            tasks.append(self.kg.retrieve(query, kb_id=kb_id, top_k=top_k))
            sources.append("kg")

        # 真正并行执行（asyncio.gather 并发运行所有协程）
        t0 = time.monotonic()
        gathered = await asyncio.gather(*tasks, return_exceptions=True)
        total_latency_ms = round((time.monotonic() - t0) * 1000, 1)

        # 组装 RetrievalResult
        retrieval_results: List[RetrievalResult] = []
        total_sources: Dict[str, int] = {}

        for raw, src in zip(gathered, sources):
            if isinstance(raw, Exception):
                logger.warning(f"{src} 检索异常: {raw}")
                hits: List[Dict] = []
            else:
                hits = raw
            retrieval_results.append(RetrievalResult(
                hits=hits, source=src, latency_ms=total_latency_ms,
            ))
            total_sources[src] = len(hits)

        logger.info(
            f"混合检索: 向量{total_sources.get('vector', 0)} + "
            f"BM25{total_sources.get('bm25', 0)} + "
            f"KG{total_sources.get('kg', 0)}"
        )

        # RRF 融合排序（使用 engine/rag/reranker.py 的公开函数）
        all_hits = [r.hits for r in retrieval_results]
        fused = rrf_fusion(all_hits, k=60)

        # 截取 Top-K
        fused = fused[:top_k]

        logger.info(f"RRF 融合后: {len(fused)} 条")
        return {"hits": fused, "total_sources": total_sources}
