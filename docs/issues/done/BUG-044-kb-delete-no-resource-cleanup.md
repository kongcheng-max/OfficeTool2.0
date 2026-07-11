# BUG-044: 知识库删除不清理 Milvus/ES/文件资源

| 属性 | 值 |
|------|---|
| **严重级别** | 🔴 Critical |
| **影响模块** | 知识库管理、数据完整性 |
| **发现方式** | 代码审查 |
| **状态** | ✅ Done — 2026-07-06 验收通过 |
| **发现日期** | 2026-07-06 |

## 现象

删除知识库时（`api/knowledge_base.py:114`，`DELETE /api/v1/knowledge-bases/{kb_id}`），仅删除了数据库中的 KnowledgeBase 行。SQLAlchemy 的 `cascade="all, delete-orphan"` 只级联删除 `documents` 和 `document_versions` 表的数据库记录，但以下资源**不会被清理**：

1. **Milvus 向量数据**: 所有文档的向量 Embedding 残留在 Milvus collection 中
2. **Elasticsearch BM25 索引**: 所有文档的 ES 索引数据残留
3. **文件存储**: MinIO（或本地文件系统）中的源文件和 chunks JSON 文件残留
4. **Neo4j 图谱数据**: 知识库相关的实体和关系节点残留（若按 kb_id 划分）

## 根因

`api/knowledge_base.py:97-115` 的 `delete_kb` 函数仅执行 `db.delete(kb)`，没有逐个清理文档关联的外部资源。对比 `api/document.py:369-435` 的单文档删除逻辑（包含 Milvus/ES/文件清理），KB 删除缺少对等的资源清理流程。

## 复现步骤

1. 创建一个包含多个文档的知识库
2. 上传文档并等待解析完成（Milvus/ES 中有数据）
3. 通过 API 或前端删除该知识库
4. 检查 Milvus collection、ES index、文件存储 → 数据仍然存在

## 影响

- 🔴 **存储泄漏**: 每次删除 KB 都会遗留不可达的向量、索引和文件数据
- 🔴 **Milvus/ES 膨胀**: 长期运行后存储空间被废弃数据占满
- 🟡 **安全风险**: 敏感文档的向量和内容残留可能被意外的跨 KB 检索命中（取决于 `kb_id` 过滤是否严格）

## 修复建议

在 `delete_kb` 中添加资源清理流程：

1. 先查询 KB 下所有文档列表
2. 对每个文档执行 Milvus 向量清理、ES 索引清理、文件删除
3. 清理 Neo4j 中该 KB 相关的实体节点
4. 最后删除数据库记录

或者使用 Celery 异步任务执行清理，避免删除操作阻塞过久。

```python
@router.delete("/{kb_id}", response_model=APIResponse)
async def delete_kb(kb_id: str, ...):
    # 1. 查询所有文档
    docs = await db.execute(select(Document).where(Document.kb_id == kb_id))
    docs = docs.scalars().all()
    
    # 2. 逐个清理外部资源
    for doc in docs:
        try: vector_store.delete_by_doc_id(doc.id)
        except: pass
        try: await es_store.delete_by_doc_id(doc.id)
        except: pass
        try: await storage_service.delete(doc.file_path)
        except: pass
    
    # 3. 删除 KB（cascade 会删 DB 中的文档记录）
    await db.delete(kb)
```
