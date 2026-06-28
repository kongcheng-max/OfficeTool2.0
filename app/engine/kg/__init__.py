"""知识图谱引擎 — 实体抽取 / 关系抽取 / Neo4j 存储 / 查询"""

from loguru import logger

# === 抽取器（不依赖 Neo4j） ===
from engine.kg.extractor import ENTITY_TYPES, RULE_PATTERNS, EntityExtractor, entity_extractor
from engine.kg.relation import RELATION_TYPES, RelationExtractor, relation_extractor

# === Neo4j 存储（懒加载，缺失依赖不阻断启动） ===
Neo4jStore = None
neo4j_store = None
_graph_query = None

try:
    from engine.kg.neo4j_store import Neo4jStore as _Neo4jStore, neo4j_store as _neo4j_store
    Neo4jStore = _Neo4jStore
    neo4j_store = _neo4j_store
except ImportError as e:
    logger.warning(f"Neo4j 存储不可用（缺少依赖）: {e}")
except Exception as e:
    logger.error(f"Neo4j 存储加载失败: {e}")

try:
    from engine.kg.query import GraphQuery, graph_query
    _graph_query = graph_query
except ImportError as e:
    logger.warning(f"图查询不可用（缺少依赖）: {e}")
except Exception as e:
    logger.error(f"图查询加载失败: {e}")

# 为兼容旧代码，保持 graph_query 和 GraphQuery 在顶层
if _graph_query is not None:
    GraphQuery = GraphQuery
    graph_query = _graph_query

__all__ = [
    "EntityExtractor", "entity_extractor",
    "RelationExtractor", "relation_extractor",
    "Neo4jStore", "neo4j_store",
    "GraphQuery", "graph_query",
    "ENTITY_TYPES", "RELATION_TYPES", "RULE_PATTERNS",
]
