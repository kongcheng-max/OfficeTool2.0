"""图谱服务层 — 懒加载外部依赖 + 响应数据格式转换"""

from typing import Optional
from loguru import logger

_graph_available: Optional[bool] = None


def _get_graph_query():
    """懒加载图查询模块（Neo4j 依赖缺失时返回 None）"""
    global _graph_available
    if _graph_available is False:
        return None
    if _graph_available is None:
        try:
            from engine.kg.query import graph_query as gq
            _graph_available = True
            return gq
        except Exception as e:
            logger.warning(f"图谱服务不可用（缺少 Neo4j 依赖）: {e}")
            _graph_available = False
            return None
    if _graph_available:
        from engine.kg.query import graph_query
        return graph_query
    return None


async def list_entities(q: str = "", kb_id: Optional[str] = None, limit: int = 50) -> list:
    gq = _get_graph_query()
    if not gq:
        return []
    return await gq.search_entities(query=q, kb_id=kb_id, limit=limit)


async def get_entity(name: str) -> Optional[dict]:
    """获取实体详情，转换为前端 EntityDetail 格式:
    {entity: {...}, relations: [{source, target, type}], source_docs: [{doc_id, doc_name}]}
    """
    gq = _get_graph_query()
    if not gq:
        return None
    raw = await gq.get_entity(name)
    if not raw:
        return None

    # ── 转换 relations: 后端 {relation, predicate, entity, ...} → 前端 {source, target, type} ──
    frontend_relations = []
    for rel in raw.get("relations", []):
        if rel and rel.get("entity"):
            frontend_relations.append({
                "source": raw.get("name", ""),
                "target": rel.get("entity", ""),
                "type": rel.get("predicate", rel.get("relation", "RELATED_TO")),
                "doc_ids": raw.get("doc_ids", []),
            })

    # ── 转换 source_docs: 后端 source_files + doc_ids → 前端 [{doc_id, doc_name}] ──
    source_files = raw.get("source_files", []) or []
    doc_ids = raw.get("doc_ids", []) or []
    source_docs = []
    for i, doc_id in enumerate(doc_ids):
        doc_name = source_files[i] if i < len(source_files) else f"文档 #{doc_id[:8]}"
        source_docs.append({
            "doc_id": doc_id,
            "doc_name": doc_name,
        })

    # ── 附加 entity 属性 ──
    properties: dict = {}
    if raw.get("confidence") is not None:
        properties["confidence"] = raw["confidence"]
    if raw.get("mention_count") is not None:
        properties["mention_count"] = raw["mention_count"]
    if raw.get("normalized_name") and raw["normalized_name"] != raw["name"]:
        properties["normalized_name"] = raw["normalized_name"]

    return {
        "entity": {
            "name": raw.get("name", ""),
            "type": raw.get("type", "TERM"),
            "kb_id": "",
            "doc_count": len(source_docs),
            "properties": properties,
        },
        "relations": frontend_relations,
        "source_docs": source_docs,
    }


async def get_entity_network(name: str, depth: int = 2) -> dict:
    """获取实体关系网络，转换为前端 EntityNetwork 格式:
    {nodes: [{id, label, type}], edges: [{source, target, label}]}
    """
    gq = _get_graph_query()
    if not gq:
        return {"nodes": [], "edges": []}
    raw = await gq.get_entity_network(name, depth)

    # ── 转换 nodes: 后端 {name, type, size} → 前端 {id, label, type} ──
    nodes = []
    for n in raw.get("nodes", []):
        nodes.append({
            "id": n.get("name", n.get("id", "")),
            "label": n.get("name", n.get("label", "")),
            "type": n.get("type", "TERM"),
        })

    # ── 转换 edges: 后端 {from, to, predicate} → 前端 {source, target, label} ──
    edges = []
    for e in raw.get("edges", []):
        edges.append({
            "source": e.get("from", e.get("source", "")),
            "target": e.get("to", e.get("target", "")),
            "label": e.get("predicate", e.get("label", "")),
        })

    return {"nodes": nodes, "edges": edges}


async def find_path(entity_a: str, entity_b: str) -> Optional[dict]:
    gq = _get_graph_query()
    if not gq:
        return None
    return await gq.find_shortest_path(entity_a, entity_b)
