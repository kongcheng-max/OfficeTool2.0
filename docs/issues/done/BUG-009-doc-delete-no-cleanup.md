# BUG-009: 文档删除时未清理 Milvus/MinIO 数据

| 属性 | 值 |
|------|---|
| **严重级别** | 🟡 Medium |
| **影响 AC** | AC05 |
| **发现方式** | 代码审查 |
| **状态** | Open |

## 现象
删除文档时，API 仅从 PostgreSQL 删除记录，不清理：
1. MinIO 中的原始文件
2. MinIO 中的 chunks JSON 文件
3. Milvus 中的向量数据

## 根因
`app/api/document.py:112-135` 的 `delete_document` 只执行 `await db.delete(doc)`，未触发 MinIO/Milvus 清理。

## 影响
- 存储空间持续增长（"存储泄漏"）
- 已删除文档的向量仍参与检索（Milvus 数据未被移除）
- 长期运行可能导致 MinIO 磁盘满

## 修复建议
在 `delete_document` 中增加：
1. `vector_store.delete_by_doc_id(doc.id)` 清除 Milvus 数据
2. `storage_service.delete(doc.file_path)` 清除 MinIO 原始文件
3. `storage_service.delete(f"chunks/{doc.id}.json")` 清除解析结果
