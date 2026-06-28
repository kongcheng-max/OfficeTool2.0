"""图谱查询 — Cypher 查询 / NL2Cypher"""

from typing import List, Optional

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
