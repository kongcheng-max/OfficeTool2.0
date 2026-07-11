"""Elasticsearch 全文检索存储"""

from typing import Dict, List, Optional

from elasticsearch import AsyncElasticsearch
from loguru import logger

from core.config import settings


class ESStore:
    """Elasticsearch 8.x 封装 — BM25 关键词检索"""

    INDEX_NAME = "officetool_chunks"
    CHINESE_ANALYZER = "ik_smart"  # 优先 IK，不可用时降级 smartcn

    INDEX_MAPPING_IK = {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "analysis": {
                "analyzer": {
                    "ik_smart_analyzer": {
                        "type": "custom",
                        "tokenizer": "ik_smart",
                        "filter": ["lowercase"],
                    }
                }
            },
        },
        "mappings": {
            "properties": {
                "doc_id": {"type": "keyword"},
                "kb_id": {"type": "keyword"},
                "chunk_text": {
                    "type": "text",
                    "analyzer": "ik_smart_analyzer",
                    "search_analyzer": "ik_smart_analyzer",
                },
                "chunk_index": {"type": "integer"},
                "metadata_json": {"type": "text"},
                "created_at": {"type": "date"},
            }
        },
    }

    INDEX_MAPPING_SMARTCN = {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
        },
        "mappings": {
            "properties": {
                "doc_id": {"type": "keyword"},
                "kb_id": {"type": "keyword"},
                "chunk_text": {
                    "type": "text",
                    "analyzer": "standard",
                },
                "chunk_index": {"type": "integer"},
                "metadata_json": {"type": "text"},
                "created_at": {"type": "date"},
            }
        },
    }

    def __init__(self):
        self._client: Optional[AsyncElasticsearch] = None
        self._mapping = None  # 延迟探测后确定

    @property
    def client(self) -> AsyncElasticsearch:
        """FastAPI 稳定 event loop 下的单例客户端（search 用）"""
        if self._client is None:
            self._client = AsyncElasticsearch(
                hosts=[settings.ELASTICSEARCH_URL],
                request_timeout=30,
            )
        return self._client

    def _new_client(self) -> AsyncElasticsearch:
        """创建独立 ES 客户端 — 供 Celery/线程池 event loop 使用

        BUG-067: 单例 client 绑定在首次创建时的 event loop，在 _run_async_safe
        的 ThreadPoolExecutor + asyncio.run() 中会报 Event loop is closed。
        写操作（index_chunks / delete_by_doc_id）每次创建新客户端并关闭。
        """
        return AsyncElasticsearch(
            hosts=[settings.ELASTICSEARCH_URL],
            request_timeout=30,
        )

    async def _detect_analyzer(self, client: AsyncElasticsearch) -> str:
        """探测可用的中文分词器：IK > smartcn > standard"""
        try:
            resp = await client.cat.plugins(format="json")
            plugins = " ".join(p.get("component", "") for p in resp)
            if "analysis-ik" in plugins:
                logger.info("ES 中文分词器: ik_smart")
                return "ik_smart"
        except Exception:
            pass
        # smartcn 是 ES 8.x 内置插件，始终可用
        logger.info("ES 中文分词器: smartcn (IK 未安装)")
        return "smartcn"

    async def _get_mapping(self, client: AsyncElasticsearch) -> dict:
        """获取适合当前 ES 的索引 Mapping"""
        if self._mapping is None:
            analyzer = await self._detect_analyzer(client)
            self._mapping = (
                self.INDEX_MAPPING_IK if analyzer == "ik_smart"
                else self.INDEX_MAPPING_SMARTCN
            )
            self.CHINESE_ANALYZER = analyzer
        return self._mapping

    async def ensure_index(self, client: Optional[AsyncElasticsearch] = None):
        """创建索引（如果不存在）

        client=None 时使用单例（FastAPI 稳定 event loop），
        传入 client 时使用指定客户端（Celery worker / 线程池）。
        """
        if client is None:
            client = self.client
        if not await client.indices.exists(index=self.INDEX_NAME):
            mapping = await self._get_mapping(client)
            try:
                await client.indices.create(index=self.INDEX_NAME, body=mapping)
            except Exception as e:
                logger.warning(
                    f"ES 索引创建失败 (body= 方式): {e}, "
                    f"尝试直接传递 mappings/settings"
                )
                try:
                    await client.indices.create(
                        index=self.INDEX_NAME,
                        settings=mapping.get("settings"),
                        mappings=mapping.get("mappings"),
                    )
                except Exception as e2:
                    logger.error(f"ES 索引创建彻底失败: {e2}")
                    raise
            logger.info(f"ES 索引已创建: {self.INDEX_NAME}")
        else:
            logger.info(f"ES 索引已存在: {self.INDEX_NAME}")

    async def index_chunks(self, records: List[Dict]):
        """批量写入文档块到 ES

        BUG-067: 每次创建独立客户端，避免 Celery/线程池 event loop 冲突。
        Args:
            records: [{doc_id, kb_id, chunk_text, chunk_index, metadata_json}, ...]
        """
        if not records:
            return

        # 创建独立客户端（不在 Celery 线程中复用单例）
        client = self._new_client()
        try:
            await self.ensure_index(client=client)

            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()

            operations = []
            for rec in records:
                operations.append({"index": {"_index": self.INDEX_NAME}})
                operations.append({
                    "doc_id": rec["doc_id"],
                    "kb_id": rec["kb_id"],
                    "chunk_text": rec["chunk_text"],
                    "chunk_index": rec.get("chunk_index", 0),
                    "metadata_json": rec.get("metadata_json", "{}"),
                    "created_at": now,
                })

            try:
                resp = await client.bulk(operations=operations, refresh=True)
                if resp.get("errors"):
                    logger.warning(f"ES 批量写入有错误: {resp}")
                else:
                    logger.info(f"ES 写入完成: {len(records)} 条")
            except Exception as e:
                logger.warning(f"ES 写入失败（可能未启动）: {e}")
        finally:
            await client.close()

    async def search(
        self,
        query: str,
        kb_id: Optional[str] = None,
        top_k: int = 10,
    ) -> List[Dict]:
        """BM25 关键词检索

        Returns:
            [{doc_id, chunk_text, metadata_json, score}, ...]
        """
        await self.ensure_index()
        client = self.client

        must = [{"match": {"chunk_text": query}}]
        if kb_id:
            must.append({"term": {"kb_id": kb_id}})

        body = {
            "query": {"bool": {"must": must}},
            "size": top_k,
            "_source": ["doc_id", "chunk_text", "metadata_json"],
        }

        try:
            resp = await client.search(index=self.INDEX_NAME, body=body)
        except Exception as e:
            logger.warning(f"ES 检索失败（可能未启动）: {e}")
            return []

        hits = []
        for hit in resp["hits"]["hits"]:
            src = hit["_source"]
            hits.append({
                "doc_id": src.get("doc_id", ""),
                "chunk_text": src.get("chunk_text", ""),
                "metadata_json": src.get("metadata_json", "{}"),
                "score": hit["_score"],
                "source": "bm25",
            })

        return hits

    async def delete_by_doc_id(self, doc_id: str):
        """按文档 ID 删除

        BUG-067: 每次创建独立客户端，避免 Celery/线程池 event loop 冲突。
        """
        client = self._new_client()
        try:
            await client.delete_by_query(
                index=self.INDEX_NAME,
                body={"query": {"term": {"doc_id": doc_id}}},
                refresh=True,
            )
            logger.info(f"ES 文档已删除: doc_id={doc_id}")
        except Exception as e:
            logger.warning(f"ES 删除失败: {e}")
        finally:
            await client.close()


# 全局单例
es_store = ESStore()
