"""Neo4j 图谱存储 — 实体节点 + 关系边 + Cypher 查询"""

import asyncio
import json
from typing import Dict, List, Optional

from loguru import logger
from neo4j import AsyncGraphDatabase
from neo4j.exceptions import ServiceUnavailable, SessionExpired, TransientError

from core.config import settings

# 重试配置
MAX_RETRIES = 3
RETRY_DELAY = 1.0  # 秒


class Neo4jStore:
    """Neo4j 图谱存储封装"""

    def __init__(self):
        self._driver = None

    @property
    def driver(self):
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                max_connection_lifetime=3600,
                max_connection_pool_size=50,
                connection_acquisition_timeout=30,
            )
        return self._driver

    async def close(self):
        if self._driver:
            await self._driver.close()
            self._driver = None

    # ============================================================
    # 连接健康检查 & 自动重连
    # ============================================================

    async def health_check(self) -> bool:
        """检查 Neo4j 连接是否健康"""
        try:
            async with self.driver.session() as session:
                result = await session.run("RETURN 1 AS ok")
                record = await result.single()
                return record is not None and record.get("ok") == 1
        except Exception as e:
            logger.warning(f"Neo4j 健康检查失败: {e}")
            return False

    async def _ensure_connection(self) -> bool:
        """确保 Neo4j 连接可用，无效时自动重连"""
        if await self.health_check():
            return True

        logger.warning("Neo4j 连接不可用，尝试重连...")
        if self._driver:
            try:
                await self._driver.close()
            except Exception:
                pass
            self._driver = None

        # 重建 driver
        try:
            _ = self.driver
            if await self.health_check():
                logger.info("Neo4j 重连成功")
                return True
        except Exception as e:
            logger.error(f"Neo4j 重连失败: {e}")

        return False

    # ============================================================
    # 约束与索引
    # ============================================================

    async def ensure_constraints(self):
        """创建唯一性约束和索引"""
        if not await self._ensure_connection():
            logger.error("Neo4j 不可用，无法创建约束")
            return

        async with self.driver.session() as session:
            try:
                await session.run(
                    "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE"
                )
                await session.run(
                    "CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.name)"
                )
                await session.run(
                    "CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.type)"
                )
                await session.run(
                    "CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.normalized_name)"
                )
                logger.info("Neo4j 约束和索引已就绪")
            except Exception as e:
                logger.warning(f"Neo4j 约束创建失败（可能已存在）: {e}")

    # ============================================================
    # 实体操作
    # ============================================================

    async def upsert_entities(
        self,
        entities: List[Dict],
        doc_id: str = "",
        kb_id: str = "",
        source: str = "",
    ):
        """批量写入实体节点（存在则更新）

        Args:
            entities: [{name, type, normalized_name, source, confidence, evidence}, ...]
            doc_id: 来源文档 ID
            kb_id: 知识库 ID
            source: 来源文档名
        """
        if not entities:
            return

        if not await self._ensure_connection():
            logger.error("Neo4j 不可用，无法写入实体")
            return

        async with self.driver.session() as session:
            for ent in entities:
                await self._retry_execute(
                    session,
                    """
                    MERGE (e:Entity {name: $name, type: $type})
                    ON CREATE SET
                        e.id = randomUUID(),
                        e.created_at = datetime(),
                        e.confidence = $confidence,
                        e.source = $source_engine,
                        e.normalized_name = $normalized_name,
                        e.evidence = $evidence,
                        e.doc_ids = [$doc_id],
                        e.kb_ids = [$kb_id],
                        e.source_files = [$source_name],
                        e.mention_count = 1
                    ON MATCH SET
                        e.confidence = CASE
                            WHEN e.confidence < $confidence THEN $confidence
                            ELSE e.confidence
                        END,
                        e.normalized_name = CASE
                            WHEN e.normalized_name IS NULL THEN $normalized_name
                            ELSE e.normalized_name
                        END,
                        e.evidence = CASE
                            WHEN e.evidence IS NULL OR e.evidence = '' THEN $evidence
                            ELSE e.evidence
                        END,
                        e.mention_count = e.mention_count + 1,
                        e.doc_ids = CASE
                            WHEN $doc_id IN e.doc_ids THEN e.doc_ids
                            ELSE e.doc_ids + $doc_id
                        END,
                        e.kb_ids = CASE
                            WHEN $kb_id IN e.kb_ids THEN e.kb_ids
                            ELSE e.kb_ids + $kb_id
                        END,
                        e.source_files = CASE
                            WHEN $source_name IN e.source_files THEN e.source_files
                            ELSE e.source_files + $source_name
                        END
                    """,
                    name=ent["name"],
                    type=ent.get("type", "TERM"),
                    confidence=ent.get("confidence", 0.5),
                    source_engine=ent.get("source", "unknown"),
                    normalized_name=ent.get("normalized_name", ent["name"]),
                    evidence=ent.get("evidence", ""),
                    doc_id=doc_id,
                    kb_id=kb_id,
                    source_name=source,
                )

    async def batch_upsert_entities(
        self,
        entities: List[Dict],
        doc_id: str = "",
        kb_id: str = "",
        source: str = "",
    ):
        """批量 MERGE 实体（一次 Cypher 多个 UNWIND 操作，性能优化）

        相比逐条 upsert_entities，减少 round-trip 次数。
        建议当 entities 数量超过 10 时使用此方法。

        Args:
            entities: [{name, type, normalized_name, source, confidence, evidence}, ...]
            doc_id: 来源文档 ID
            kb_id: 知识库 ID
            source: 来源文档名
        """
        if not entities:
            return

        if not await self._ensure_connection():
            logger.error("Neo4j 不可用，无法批量写入实体")
            return

        async with self.driver.session() as session:
            # 使用 UNWIND 批量 MERGE
            params = [
                {
                    "name": ent["name"],
                    "type": ent.get("type", "TERM"),
                    "confidence": ent.get("confidence", 0.5),
                    "source_engine": ent.get("source", "unknown"),
                    "normalized_name": ent.get("normalized_name", ent["name"]),
                    "evidence": ent.get("evidence", ""),
                }
                for ent in entities
            ]

            await self._retry_execute(
                session,
                """
                UNWIND $batch AS row
                MERGE (e:Entity {name: row.name, type: row.type})
                ON CREATE SET
                    e.id = randomUUID(),
                    e.created_at = datetime(),
                    e.confidence = row.confidence,
                    e.source = row.source_engine,
                    e.normalized_name = row.normalized_name,
                    e.evidence = row.evidence,
                    e.doc_ids = [$doc_id],
                    e.kb_ids = [$kb_id],
                    e.source_files = [$source],
                    e.mention_count = 1
                ON MATCH SET
                    e.confidence = CASE
                        WHEN e.confidence < row.confidence THEN row.confidence
                        ELSE e.confidence
                    END,
                    e.normalized_name = CASE
                        WHEN e.normalized_name IS NULL THEN row.normalized_name
                        ELSE e.normalized_name
                    END,
                    e.evidence = CASE
                        WHEN e.evidence IS NULL OR e.evidence = '' THEN row.evidence
                        ELSE e.evidence
                    END,
                    e.mention_count = e.mention_count + 1,
                    e.doc_ids = CASE
                        WHEN $doc_id IN e.doc_ids THEN e.doc_ids
                        ELSE e.doc_ids + $doc_id
                    END,
                    e.kb_ids = CASE
                        WHEN $kb_id IN e.kb_ids THEN e.kb_ids
                        ELSE e.kb_ids + $kb_id
                    END,
                    e.source_files = CASE
                        WHEN $source IN e.source_files THEN e.source_files
                        ELSE e.source_files + $source
                    END
                """,
                batch=params,
                doc_id=doc_id,
                kb_id=kb_id,
                source=source,
            )

        logger.info(f"批量写入 {len(entities)} 个实体完成")

    async def delete_by_doc_id(self, doc_id: str) -> int:
        """删除指定文档的所有实体和关系

        对于实体节点:
        - 如果实体只被此文档引用，则删除节点
        - 如果实体还被其他文档引用，则只移除此 doc_id 的引用
        对于关系:
        - 如果关系只被此文档引用，则删除关系
        - 如果关系还被其他文档引用，则只移除此 doc_id 的引用

        Args:
            doc_id: 文档 ID

        Returns:
            删除/更新的实体数量
        """
        if not await self._ensure_connection():
            logger.error("Neo4j 不可用，无法删除")
            return 0

        deleted_count = 0

        async with self.driver.session() as session:
            # 1. 删除只属于此文档的关系
            await self._retry_execute(
                session,
                """
                MATCH ()-[r:RELATES]->()
                WHERE r.doc_ids = [$doc_id]
                DELETE r
                """,
                doc_id=doc_id,
            )

            # 2. 更新共享关系的 doc_ids（移除当前 doc_id）
            await self._retry_execute(
                session,
                """
                MATCH ()-[r:RELATES]->()
                WHERE $doc_id IN r.doc_ids AND size(r.doc_ids) > 1
                SET r.doc_ids = [id IN r.doc_ids WHERE id <> $doc_id]
                """,
                doc_id=doc_id,
            )

            # 3. 删除只属于此文档的实体节点（及其关联关系）
            result = await self._retry_execute(
                session,
                """
                MATCH (e:Entity)
                WHERE e.doc_ids = [$doc_id]
                DETACH DELETE e
                RETURN count(e) AS deleted
                """,
                doc_id=doc_id,
            )
            record = await result.single()
            if record:
                deleted_count = record.get("deleted", 0)

            # 4. 更新共享实体的 doc_ids（移除当前 doc_id）
            await self._retry_execute(
                session,
                """
                MATCH (e:Entity)
                WHERE $doc_id IN e.doc_ids AND size(e.doc_ids) > 1
                SET e.doc_ids = [id IN e.doc_ids WHERE id <> $doc_id],
                    e.mention_count = e.mention_count - 1,
                    e.source_files = [f IN e.source_files WHERE f <> '']
                """,
                doc_id=doc_id,
            )

        logger.info(f"文档 {doc_id} 图谱数据已清理: 删除 {deleted_count} 个独有实体")
        return deleted_count

    # ============================================================
    # 关系操作
    # ============================================================

    async def create_relations(
        self,
        relations: List[Dict],
        doc_id: str = "",
    ):
        """创建实体间的关系边

        Args:
            relations: [{subject, predicate, object, confidence}, ...]
            doc_id: 来源文档 ID
        """
        if not relations:
            return

        if not await self._ensure_connection():
            logger.error("Neo4j 不可用，无法创建关系")
            return

        async with self.driver.session() as session:
            for rel in relations:
                await self._retry_execute(
                    session,
                    """
                    MATCH (a:Entity {name: $subject})
                    MATCH (b:Entity {name: $object})
                    MERGE (a)-[r:RELATES {predicate: $predicate}]->(b)
                    ON CREATE SET
                        r.confidence = $confidence,
                        r.doc_ids = [$doc_id],
                        r.created_at = datetime()
                    ON MATCH SET
                        r.confidence = CASE
                            WHEN r.confidence < $confidence THEN $confidence
                            ELSE r.confidence
                        END,
                        r.doc_ids = CASE
                            WHEN $doc_id IN r.doc_ids THEN r.doc_ids
                            ELSE r.doc_ids + $doc_id
                        END
                    """,
                    subject=rel["subject"],
                    predicate=rel.get("predicate", "RELATED_TO"),
                    object=rel["object"],
                    confidence=rel.get("confidence", 0.5),
                    doc_id=doc_id,
                )

    # ============================================================
    # 查询操作
    # ============================================================

    async def search_entities(
        self,
        query: str = "",
        kb_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """搜索实体列表"""
        if not await self._ensure_connection():
            return []

        async with self.driver.session() as session:
            if query:
                params: dict = {"query": query, "limit": limit}
                if kb_id:
                    params["kb_id"] = kb_id
                result = await session.run(
                    """
                    MATCH (e:Entity)
                    WHERE (e.name CONTAINS $query OR e.normalized_name CONTAINS $query)
                    """ + (" AND $kb_id IN e.kb_ids" if kb_id else "") + """
                    RETURN e.name AS name, e.normalized_name AS normalized_name,
                           e.type AS type, e.confidence AS confidence,
                           e.mention_count AS mention_count, e.source_files AS source_files
                    ORDER BY e.mention_count DESC
                    LIMIT $limit
                    """,
                    params,
                )
            else:
                params = {"limit": limit}
                if kb_id:
                    params["kb_id"] = kb_id
                result = await session.run(
                    """
                    MATCH (e:Entity)
                    """ + ("WHERE $kb_id IN e.kb_ids" if kb_id else "") + """
                    RETURN e.name AS name, e.normalized_name AS normalized_name,
                           e.type AS type, e.confidence AS confidence,
                           e.mention_count AS mention_count, e.source_files AS source_files
                    ORDER BY e.mention_count DESC
                    LIMIT $limit
                    """,
                    params,
                )

            entities = []
            async for record in result:
                entities.append({
                    "name": record["name"],
                    "normalized_name": record.get("normalized_name", record["name"]),
                    "type": record["type"],
                    "confidence": record.get("confidence", 0.5),
                    "mention_count": record.get("mention_count", 0),
                    "source_files": record.get("source_files", []),
                })
            return entities

    async def get_entity_detail(self, entity_name: str) -> Optional[Dict]:
        """获取实体详情 + 关联实体"""
        if not await self._ensure_connection():
            return None

        async with self.driver.session() as session:
            # 获取实体（同时匹配 name 和 normalized_name）
            result = await session.run(
                """
                MATCH (e:Entity)
                WHERE e.name = $name OR e.normalized_name = $name
                OPTIONAL MATCH (e)-[r:RELATES]-(related:Entity)
                RETURN e, collect(DISTINCT {
                    relation: type(r),
                    predicate: r.predicate,
                    entity: related.name,
                    entity_normalized: related.normalized_name,
                    entity_type: related.type,
                    confidence: r.confidence
                }) AS relations
                """,
                name=entity_name,
            )
            record = await result.single()
            if not record:
                return None

            entity_data = record["e"]
            relations = [r for r in record["relations"] if r["relation"] is not None]

            return {
                "name": entity_data["name"],
                "normalized_name": entity_data.get("normalized_name", entity_data["name"]),
                "type": entity_data.get("type", "TERM"),
                "confidence": entity_data.get("confidence", 0.5),
                "mention_count": entity_data.get("mention_count", 0),
                "source_files": entity_data.get("source_files", []),
                "doc_ids": entity_data.get("doc_ids", []),
                "relations": relations,
            }

    async def search_related_chunks(
        self,
        entities: List[str] = None,
        query: str = "",
        kb_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict]:
        """通过实体关联检索相关文档块（KG 检索通道主入口）

        检索策略:
        1. 如果传入了 entities 列表，直接用 Cypher 批量精确匹配
        2. 如果只有 query（fallback），调用 prompts 接口提取实体，再精确匹配
        3. 使用 UNWIND + CONTAINS 做批量实体匹配，一次查询返回所有关联文档
        4. 按文档的关联实体数量排序（实体命中越多的文档块排名越高）

        Args:
            entities: 外部传入的实体名称列表（优先使用）
            query: 用户查询文本（entities 为空时作为 fallback 提取实体）
            kb_id: 知识库 ID
            limit: 最大返回数量

        Returns:
            关联文档块列表，按实体命中数降序
        """
        if not await self._ensure_connection():
            return []

        # 1. 确定实体列表: 优先使用传入的 entities, 否则从 query 提取
        search_entities = entities or []
        if not search_entities and query:
            search_entities = await self._extract_entity_keywords(query)

        if not search_entities:
            logger.info("未获取到实体关键词，KG 检索无结果")
            return []

        logger.info(f"KG 检索实体: {search_entities}")

        async with self.driver.session() as session:
            # 2. 使用 UNWIND 批量匹配实体，按文档维度聚合
            kb_filter = "AND $kb_id IN e.kb_ids" if kb_id else ""

            result = await session.run(
                f"""
                // 批量实体匹配
                UNWIND $entities AS entity_term
                MATCH (e:Entity)
                WHERE e.name CONTAINS entity_term OR e.normalized_name CONTAINS entity_term
                {kb_filter}
                // 展开文档关联
                WITH e, entity_term
                UNWIND e.doc_ids AS doc_id_inner
                // 可选: 获取关联实体
                OPTIONAL MATCH (e)-[:RELATES]-(related:Entity)
                // 按 (doc_id, entity) 聚合
                WITH doc_id_inner AS doc_id,
                     e.name AS entity_name,
                     e.normalized_name AS normalized_name,
                     e.type AS entity_type,
                     e.mention_count AS mention_count,
                     collect(DISTINCT related.name) AS related_entities
                ORDER BY mention_count DESC
                // 收集每个 doc_id 命中的所有实体
                WITH doc_id,
                     collect({{
                         entity_name: entity_name,
                         normalized_name: normalized_name,
                         entity_type: entity_type,
                         related_entities: related_entities,
                         mention_count: mention_count
                     }}) AS matched_entities,
                     count(*) AS entity_hit_count
                // 按实体命中数降序
                ORDER BY entity_hit_count DESC
                LIMIT $limit
                RETURN doc_id, matched_entities, entity_hit_count
                """,
                entities=search_entities,
                kb_id=kb_id,
                limit=limit,
            )

            kg_hits = []
            async for record in result:
                doc_id = record["doc_id"]
                matched_entities = record["matched_entities"]
                entity_hit_count = record["entity_hit_count"]

                # 为每个 matched_entity 生成一条 hit
                for ent in matched_entities:
                    # 实体命中越多的文档 score 越高 (归一化到 0-1)
                    score = min(0.95, 0.3 + entity_hit_count * 0.15)

                    kg_hits.append({
                        "doc_id": doc_id,
                        "chunk_text": (
                            f"[图谱关联] 实体: {ent['entity_name']}"
                            f"({ent['entity_type']})"
                        ),
                        "metadata_json": json.dumps({
                            "kg_entity_hit_count": entity_hit_count,
                            "kg_matched_entities": [
                                e["entity_name"] for e in matched_entities
                            ],
                            "kg_related_entities": ent.get("related_entities", []),
                        }),
                        "score": score,
                        "source": "kg",
                        "metadata": {
                            "source": "知识图谱",
                            "entity": ent["entity_name"],
                            "normalized_name": ent.get("normalized_name", ent["entity_name"]),
                            "entity_type": ent["entity_type"],
                            "entity_hit_count": entity_hit_count,
                        },
                    })

            # 按 (doc_id, entity) 去重
            seen = set()
            unique_hits = []
            for hit in kg_hits:
                key = f"{hit['doc_id']}|{hit['metadata']['entity']}"
                if key not in seen:
                    seen.add(key)
                    unique_hits.append(hit)

            logger.info(f"KG 检索: {len(unique_hits)} 条结果 (传入实体 {len(search_entities)})")
            return unique_hits[:limit]

    async def _extract_entity_keywords(self, query: str) -> List[str]:
        """使用 LLM 从查询文本中抽取实体关键词 (KG 检索 fallback)

        优先使用 prompts 模块中的专业 Prompt 模板进行提取。
        返回实体名称列表用于 Neo4j 精确匹配。
        """
        from engine.kg.prompts import get_query_entity_extraction_messages
        from engine.llm.factory import LLMFactory

        try:
            messages = get_query_entity_extraction_messages(query)
            answer = await LLMFactory.generate_with_fallback(
                messages=messages,
                temperature=0.2,
            )
            # 提取 JSON 对象
            import re
            json_match = re.search(r"\{.*\}", answer, re.DOTALL)
            if json_match:
                import json
                result = json.loads(json_match.group(0))
                if isinstance(result, dict):
                    entities = result.get("entities", [])
                    keywords = result.get("keywords", [])
                    # 合并 entities 和 keywords, entities 优先
                    all_keywords = entities + [
                        kw for kw in keywords
                        if kw not in entities and isinstance(kw, str) and len(kw) >= 1
                    ]
                    if all_keywords:
                        logger.info(f"LLM 提取查询实体: entities={entities}, keywords={keywords}")
                        return [k for k in all_keywords if isinstance(k, str) and len(k) >= 1]
        except Exception as e:
            logger.warning(f"查询实体关键词提取失败: {e}")

        logger.info("LLM 实体提取失败或无结果，KG 检索跳过")
        return []

    # ============================================================
    # 内部工具方法
    # ============================================================

    async def _retry_execute(self, session, query: str, **params):
        """带重试的 Cypher 执行（处理瞬时故障）"""
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                return await session.run(query, **params)
            except (ServiceUnavailable, SessionExpired, TransientError) as e:
                last_error = e
                logger.warning(f"Neo4j 瞬时故障 (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                    # 尝试重连
                    if not await self._ensure_connection():
                        raise e
            except Exception as e:
                last_error = e
                logger.warning(f"Neo4j 操作失败 ({query[:80]}...): {e}")
                break
        raise last_error


# 全局单例
neo4j_store = Neo4jStore()
