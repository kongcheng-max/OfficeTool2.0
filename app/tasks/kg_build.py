"""知识图谱构建 Celery 任务 — 使用 safe-asyncio 模式避免 event loop 冲突"""

from loguru import logger
from celery.utils.log import get_task_logger

from tasks.celery_app import celery_app
from tasks.embed import _run_async_safe  # BUG-060: 统一 safe-asyncio 模式

task_logger = get_task_logger(__name__)


def _get_db_session():
    from core.database import async_session_factory
    return async_session_factory()


@celery_app.task(name="build_knowledge_graph", bind=True, max_retries=2, default_retry_delay=10)
def build_knowledge_graph(self, doc_id: str):
    """异步 KG 构建 — 使用安全 event loop 模式（同 embed_document）

    BUG-066: KG 是辅助管线，不修改文档主状态。
    ready 由 embed_document 独设，确保 doc status 与 Milvus/ES 索引同步。
    """
    try:
        return _run_async_safe(_async_build_kg(doc_id))
    except Exception as exc:
        task_logger.error(f"KG 构建任务失败 doc_id={doc_id}: {exc}")
        raise self.retry(exc=exc)


async def _async_build_kg(doc_id: str) -> dict:
    import json
    from sqlalchemy import select
    from models.models import Document
    from services.storage import storage_service
    from engine.kg.extractor import entity_extractor
    from engine.kg.relation import relation_extractor
    from engine.kg.neo4j_store import neo4j_store
    from engine.parser.base import Chunk

    async with _get_db_session() as session:
        async with session.begin():
            result = await session.execute(
                select(Document).where(Document.id == doc_id)
            )
            doc = result.scalar_one_or_none()
            # BUG-066: KG 只检查状态，不修改它；ready 由 embed 独设
            if not doc or doc.status not in ("parsed", "ready"):
                return {"status": "error", "error": "文档未就绪（状态不匹配）"}

            task_logger.info(f"开始 KG 构建: doc_id={doc_id}, file={doc.original_filename}")
            # 不设 kg_building — KG 是辅助管线，不改文档主状态

        await session.commit()

    # 阶段分离：先持久化状态，再进行耗时操作
    try:
        # 1. 读取解析结果
        try:
            chunks_json = await storage_service.download(f"chunks/{doc_id}.json")
            chunks_data = json.loads(chunks_json.decode("utf-8"))
        except Exception as e:
            task_logger.error(f"KG 构建 — 解析结果读取失败 doc_id={doc_id}: {e}")
            return {"status": "error", "error": "解析结果不存在"}

        chunks = [Chunk.from_dict(c) for c in chunks_data]
        full_text = "\n".join(c.content for c in chunks)
        task_logger.info(f"解析结果加载完成: doc_id={doc_id}, chunks={len(chunks)}, text_len={len(full_text)}")

        # 2. Neo4j 约束检查
        await neo4j_store.ensure_constraints()

        # 3. 实体抽取（规则引擎 + LLM，含标准化步骤）
        entities = await entity_extractor.extract(full_text, use_llm=True)
        task_logger.info(
            f"实体抽取完成: doc_id={doc_id}, entities={len(entities)}, "
            f"normalized={sum(1 for e in entities if e.get('normalized_name') != e['name'])}"
        )

        if entities:
            # 使用批量写入（当实体数量超过 10 时）以提高性能
            if len(entities) > 10:
                await neo4j_store.batch_upsert_entities(
                    entities=entities,
                    doc_id=doc_id,
                    kb_id=doc.kb_id if doc else "",
                    source=doc.original_filename if doc else "",
                )
            else:
                await neo4j_store.upsert_entities(
                    entities=entities,
                    doc_id=doc_id,
                    kb_id=doc.kb_id if doc else "",
                    source=doc.original_filename if doc else "",
                )

        # 4. 关系抽取
        relation_count = 0
        if len(entities) >= 2:
            relations = await relation_extractor.extract(
                text=full_text,
                entities=entities,
                use_llm=True,
            )
            relation_count = len(relations)
            task_logger.info(
                f"关系抽取完成: doc_id={doc_id}, relations={relation_count}, "
                f"predicates={list(set(r['predicate'] for r in relations))}"
            )

            if relations:
                await neo4j_store.create_relations(
                    relations=relations,
                    doc_id=doc_id,
                )

        # BUG-066: KG 完成不设 ready — ready 由 embed 独设，确保与 Milvus/ES 索引同步
        task_logger.info(
            f"KG 构建完成: doc_id={doc_id}, entities={len(entities)}, relations={relation_count}"
        )
        return {
            "status": "done",
            "entities": len(entities),
            "relations": relation_count,
        }

    except Exception as e:
        task_logger.error(f"KG 构建异常 doc_id={doc_id}: {e}")
        raise
