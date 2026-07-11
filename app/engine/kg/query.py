"""图谱查询 — Cypher 查询 / NL2Cypher (W11.10)"""

import json
import re
from typing import Any, Dict, List, Optional

from loguru import logger


class GraphQuery:
    """图谱查询封装"""

    def __init__(self, neo4j_store=None):
        from engine.kg.neo4j_store import neo4j_store as store
        self._store = neo4j_store or store

    async def search_entities(
        self,
        query: str = "",
        kb_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[dict]:
        """实体搜索"""
        return await self._store.search_entities(query=query, kb_id=kb_id, limit=limit)

    async def get_entity(self, name: str) -> Optional[dict]:
        """获取实体详情（支持 name 和 normalized_name 匹配）"""
        return await self._store.get_entity_detail(name)

    async def find_shortest_path(
        self,
        entity_a: str,
        entity_b: str,
    ) -> Optional[dict]:
        """查找两个实体间的最短路径（支持 name / normalized_name 匹配）"""
        try:
            async with self._store.driver.session() as session:
                result = await session.run(
                    """
                    MATCH (a:Entity)
                    WHERE a.name = $name_a OR a.normalized_name = $name_a
                    MATCH (b:Entity)
                    WHERE b.name = $name_b OR b.normalized_name = $name_b
                    MATCH path = shortestPath((a)-[*..4]-(b))
                    RETURN [node in nodes(path) | node.name] AS path_nodes,
                           [node in nodes(path) | node.normalized_name] AS path_normalized,
                           [rel in relationships(path) | {
                               from: startNode(rel).name,
                               to: endNode(rel).name,
                               predicate: rel.predicate
                           }] AS path_rels,
                           length(path) AS path_length
                    """,
                    name_a=entity_a,
                    name_b=entity_b,
                )
                record = await result.single()
                if not record:
                    return None

                return {
                    "entity_a": entity_a,
                    "entity_b": entity_b,
                    "path": record["path_nodes"],
                    "path_normalized": record.get("path_normalized", record["path_nodes"]),
                    "relations": record["path_rels"],
                    "length": record["path_length"],
                }
        except Exception as e:
            logger.warning(f"最短路径查询失败 ({entity_a}→{entity_b}): {e}")
            return None

    async def get_entity_network(
        self,
        entity_name: str,
        depth: int = 2,
    ) -> dict:
        """获取实体的关系网络（子图）

        Args:
            entity_name: 中心实体名（支持 name / normalized_name）
            depth: 扩展深度（当前简化为 1-hop 直接邻居，避免可变长路径空值问题）

        Returns:
            {nodes: [{name, type, size}], edges: [{from, to, predicate}]}
        """
        try:
            async with self._store.driver.session() as session:
                # 使用 1-hop 直接关系（比可变长路径更健壮，不会因 null path 出错）
                result = await session.run(
                    """
                    MATCH (center:Entity)
                    WHERE center.name = $name OR center.normalized_name = $name
                    OPTIONAL MATCH (center)-[r:RELATES]-(neighbor:Entity)
                    RETURN center,
                           collect(DISTINCT CASE WHEN neighbor IS NOT NULL
                               THEN {name: neighbor.name, normalized_name: neighbor.normalized_name,
                                     type: neighbor.type, mention_count: neighbor.mention_count}
                               ELSE NULL END) AS neighbors,
                           collect(DISTINCT CASE WHEN r IS NOT NULL
                               THEN {from: startNode(r).name, to: endNode(r).name, predicate: r.predicate}
                               ELSE NULL END) AS edges
                    """,
                    name=entity_name,
                )
                record = await result.single()
                if not record:
                    return {"nodes": [], "edges": []}

                nodes = []
                center_data = record["center"]
                nodes.append({
                    "name": center_data["name"],
                    "normalized_name": center_data.get("normalized_name", center_data["name"]),
                    "type": center_data.get("type", ""),
                    "size": center_data.get("mention_count", 1),
                })

                seen_names = {center_data["name"]}
                for neighbor in (record.get("neighbors") or []):
                    if neighbor and neighbor.get("name") and neighbor["name"] not in seen_names:
                        seen_names.add(neighbor["name"])
                        nodes.append({
                            "name": neighbor["name"],
                            "normalized_name": neighbor.get("normalized_name", neighbor["name"]),
                            "type": neighbor.get("type", ""),
                            "size": neighbor.get("mention_count", 1),
                        })

                # 过滤有效边
                edges = []
                edge_seen = set()
                for edge in (record.get("edges") or []):
                    if edge and edge.get("from") and edge.get("to"):
                        key = f"{edge['from']}|{edge.get('predicate', '')}|{edge['to']}"
                        if key not in edge_seen:
                            edge_seen.add(key)
                            edges.append(edge)

                logger.info(
                    f"实体关系网络: center={entity_name}, nodes={len(nodes)}, edges={len(edges)}"
                )
                return {"nodes": nodes, "edges": edges}
        except Exception as e:
            logger.warning(f"实体关系网络查询失败 ({entity_name}, depth={depth}): {e}")
            return {"nodes": [], "edges": []}


# 全局单例
graph_query = GraphQuery()


# ═══════════════════════════════════════════════════════════════
# NL2Cypher — 自然语言 → Cypher 查询 (W11.10)
# ═══════════════════════════════════════════════════════════════

NL2CYPHER_SYSTEM = """你是一个 Neo4j Cypher 查询生成专家。将用户自然语言问题转为 Cypher 查询语句。

## 数据库 Schema
- (e:Entity {name, type, doc_ids[], kb_ids[]})
- (e1)-[r:RELATES {predicate, doc_ids[], evidence}]->(e2)
- Entity type: PERSON, ORG, DATE, MONEY, LOCATION, TERM

## 规则
1. 只生成 SELECT 查询
2. 使用 MATCH ... RETURN ... 格式
3. 实体名模糊匹配: WHERE e.name CONTAINS 'xxx'
4. 关系方向不定: MATCH (a)-[r]-(b)
5. LIMIT 20
6. 返回纯 Cypher 语句

## Few-shot 示例
问: 华为签署了哪些合同？
答: MATCH (e:Entity)-[r:RELATES]->(t:Entity) WHERE e.name CONTAINS '华为' AND r.predicate='SIGNS' RETURN e.name, r.predicate, t.name, r.evidence LIMIT 20

问: 张三与哪些公司有关联？
答: MATCH (p:Entity)-[r:RELATES]-(org:Entity) WHERE p.name CONTAINS '张三' AND org.type='ORG' RETURN p.name, r.predicate, org.name, r.evidence LIMIT 20
"""

NL2CYPHER_USER = """将以下问题转为 Cypher 查询：

{question}

Cypher："""


class KGQueryEngine:
    """图谱 NL2Cypher 查询引擎"""

    async def query(self, question: str, kb_id: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
        """NL → Cypher → Neo4j 执行"""
        cypher = await self._generate_cypher(question)
        if not cypher:
            return {"cypher": "", "results": [], "error": "Cypher 生成失败"}

        try:
            from engine.kg.neo4j_store import neo4j_store
            results = await self._execute_cypher(neo4j_store, cypher, kb_id, limit)
            return {"cypher": cypher, "results": results, "error": None}
        except Exception as e:
            logger.warning(f"NL2Cypher 执行失败: {e}")
            return {"cypher": cypher, "results": [], "error": str(e)}

    async def _generate_cypher(self, question: str) -> str:
        """LLM → Cypher"""
        try:
            from engine.llm.factory import LLMFactory
            messages = [
                {"role": "system", "content": NL2CYPHER_SYSTEM},
                {"role": "user", "content": NL2CYPHER_USER.format(question=question)},
            ]
            answer = await LLMFactory.generate_with_fallback(messages=messages, temperature=0.1)
            cypher = answer.strip()
            m = re.search(r'```(?:cypher)?\s*(.*?)\s*```', cypher, re.DOTALL | re.IGNORECASE)
            if m:
                cypher = m.group(1).strip()
            logger.info(f"NL2Cypher: '{question[:60]}' → {cypher[:120]}")
            return cypher
        except Exception as e:
            logger.error(f"NL2Cypher LLM 失败: {e}")
            return ""

    async def _execute_cypher(self, store, cypher: str, kb_id: Optional[str], limit: int) -> List[Dict]:
        """执行 Cypher"""
        if not await store._ensure_connection():
            return []

        params = {"limit": limit}
        if kb_id:
            params["kb_id"] = kb_id
            # BUG-077: LLM 可能已生成 WHERE，检测后用 AND 追加避免双 WHERE
            if re.search(r'\bWHERE\b', cypher, re.IGNORECASE):
                cypher = re.sub(
                    r'\bRETURN\b',
                    'AND $kb_id IN e.kb_ids RETURN',
                    cypher, count=1, flags=re.IGNORECASE,
                )
            else:
                cypher = re.sub(
                    r'\bRETURN\b',
                    'WHERE $kb_id IN e.kb_ids RETURN',
                    cypher, count=1, flags=re.IGNORECASE,
                )

        async with store.driver.session() as session:
            result = await session.run(cypher, params)
            return await result.data()


# 全局单例
kg_query_engine = KGQueryEngine()
