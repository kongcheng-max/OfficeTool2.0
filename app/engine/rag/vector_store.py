"""向量数据库服务 — Milvus 抽象层"""

import time
from typing import Dict, List, Optional

from loguru import logger
from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    MilvusClient,
    connections,
    utility,
)

from core.config import settings


class VectorStore:
    """Milvus 向量存储封装

    负责 Collection 创建、向量写入、ANN 检索。
    """

    COLLECTION_NAME = settings.MILVUS_COLLECTION
    DIM = 768  # text2vec-base-chinese 维度
    METRIC_TYPE = "COSINE"

    def __init__(self):
        self._connected = False

    def connect(self):
        """连接 Milvus"""
        if not self._connected:
            connections.connect(
                alias="default",
                host=settings.MILVUS_HOST,
                port=settings.MILVUS_PORT,
            )
            self._connected = True
            logger.info(f"Milvus 已连接: {settings.MILVUS_HOST}:{settings.MILVUS_PORT}")

    def disconnect(self):
        if self._connected:
            connections.disconnect("default")
            self._connected = False

    def create_collection_if_not_exists(self):
        """创建 Collection（如果不存在）"""
        self.connect()

        if utility.has_collection(self.COLLECTION_NAME):
            logger.info(f"Milvus Collection 已存在: {self.COLLECTION_NAME}")
            return

        # 定义 Schema
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=32),
            FieldSchema(name="kb_id", dtype=DataType.VARCHAR, max_length=32),
            FieldSchema(name="chunk_text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="chunk_index", dtype=DataType.INT64),
            FieldSchema(name="metadata_json", dtype=DataType.VARCHAR, max_length=4096),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.DIM),
        ]

        schema = CollectionSchema(fields=fields, description="OfficeTool 文档块向量")
        Collection(name=self.COLLECTION_NAME, schema=schema)

        logger.info(f"Milvus Collection 已创建: {self.COLLECTION_NAME}, dim={self.DIM}")

    def get_collection(self) -> Collection:
        """获取 Collection 对象（自动创建如果不存在）"""
        self.connect()
        self.create_collection_if_not_exists()
        return Collection(name=self.COLLECTION_NAME)

    def ensure_index(self):
        """确保索引已创建"""
        import json
        self.connect()
        coll = self.get_collection()

        # 检查是否已有索引
        indexes = coll.indexes
        if indexes:
            return

        index_params = {
            "metric_type": self.METRIC_TYPE,
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128},
        }
        coll.create_index(
            field_name="embedding",
            index_params=index_params,
        )
        logger.info(f"Milvus 索引已创建: {self.COLLECTION_NAME}")

    def insert(self, records: List[Dict]) -> List[int]:
        """批量插入向量记录

        Args:
            records: 每个元素包含 {doc_id, kb_id, chunk_text, chunk_index, metadata_json, embedding}

        Returns:
            插入的 ID 列表
        """
        if not records:
            return []

        self.connect()
        self.ensure_index()
        coll = self.get_collection()

        # 构建插入数据
        doc_ids = [r["doc_id"] for r in records]
        kb_ids = [r["kb_id"] for r in records]
        chunk_texts = [r["chunk_text"] for r in records]
        chunk_indices = [r.get("chunk_index", 0) for r in records]
        metadata_jsons = [r.get("metadata_json", "{}") for r in records]
        embeddings = [r["embedding"] for r in records]

        mr = coll.insert([
            doc_ids,
            kb_ids,
            chunk_texts,
            chunk_indices,
            metadata_jsons,
            embeddings,
        ])

        coll.flush()
        return mr.primary_keys

    def search(
        self,
        query_vector: List[float],
        kb_id: Optional[str] = None,
        top_k: int = 10,
    ) -> List[Dict]:
        """向量相似检索

        Args:
            query_vector: 查询向量
            kb_id: 可选，限制在指定知识库内检索
            top_k: 返回 Top-K 结果

        Returns:
            [{doc_id, chunk_text, metadata_json, score}, ...]
        """
        self.connect()
        coll = self.get_collection()
        coll.load()

        search_params = {
            "metric_type": self.METRIC_TYPE,
            "params": {"nprobe": 16},
        }

        # 构建过滤条件
        expr = None
        if kb_id:
            expr = f'kb_id == "{kb_id}"'

        results = coll.search(
            data=[query_vector],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=expr,
            output_fields=["doc_id", "chunk_text", "metadata_json", "kb_id"],
        )

        hits = []
        for result in results[0]:
            hits.append({
                "doc_id": result.entity.get("doc_id", ""),
                "chunk_text": result.entity.get("chunk_text", ""),
                "metadata_json": result.entity.get("metadata_json", "{}"),
                "score": result.distance,
            })

        return hits

    def delete_by_doc_id(self, doc_id: str):
        """按文档 ID 删除向量"""
        self.connect()
        coll = self.get_collection()
        coll.delete(f'doc_id == "{doc_id}"')

    def count(self) -> int:
        """返回向量总数"""
        self.connect()
        coll = self.get_collection()
        coll.flush()
        return coll.num_entities


# 全局单例
vector_store = VectorStore()
