"""检索器 — 向量相似检索"""

import json
from typing import Dict, List, Optional

from loguru import logger

from engine.rag.embedder import BaseEmbedder
from engine.rag.vector_store import VectorStore


class Retriever:
    """文档检索器

    封装向量化 → 检索流程。
    """

    def __init__(self, embedder: BaseEmbedder, store: VectorStore):
        self._embedder = embedder
        self._store = store

    async def retrieve(
        self,
        query: str,
        kb_id: Optional[str] = None,
        top_k: int = 10,
    ) -> List[Dict]:
        """
        检索相关文档块

        Args:
            query: 查询文本
            kb_id: 可选，限制在指定知识库内
            top_k: 返回数量

        Returns:
            [{doc_id, chunk_text, metadata_json, score}, ...]
        """
        # 1. 向量化查询
        logger.info(f"检索查询: {query[:100]}...")
        query_vector = await self._embedder.embed_query(query)

        # 2. 向量检索
        hits = self._store.search(
            query_vector=query_vector,
            kb_id=kb_id,
            top_k=top_k,
        )

        # 3. 反序列化 metadata_json
        for hit in hits:
            try:
                hit["metadata"] = json.loads(hit.pop("metadata_json", "{}"))
            except (json.JSONDecodeError, TypeError):
                hit["metadata"] = {}

        logger.info(f"检索结果: {len(hits)} 条")
        return hits
