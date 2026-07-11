# BUG-073: Milvus HNSW 索引迁移在 Collection 已加载时失败

| 属性 | 值 |
|------|---|
| **严重级别** | 🟡 Medium |
| **影响模块** | Milvus 向量存储 → 索引管理 |
| **发现方式** | Week 9 第二轮验收测试 |
| **状态** | 🔴 待修复 |
| **发现日期** | 2026-07-11 |

---

## 现象

`vector_store.py:ensure_index()` 的 HNSW 迁移逻辑执行时报错：

```
MilvusException: index cannot be dropped, collection is loaded, please release it first
MilvusException: CreateIndex failed: at most one distinct index is allowed per field
```

迁移流程期望 `drop_index() → create_index(HNSW)`，但 Collection 处于 loaded 状态，`drop_index()` 被 Milvus 拒绝。后续 `create_index()` 也因旧索引未删除而失败。

## 根因

`ensure_index()` 在尝试 `drop_index()` 前未调用 `coll.release()`。Milvus 要求 Collection 处于未加载状态才能删除索引。

## 修复建议

```python
# vector_store.py ensure_index() 第 96-105 行
if existing_type != "HNSW":
    coll.release()  # ← 先释放
    try:
        coll.drop_index()
        logger.info(f"已删除旧索引 {existing_type}")
    except Exception as e:
        logger.warning(f"删除旧索引失败: {e}")
    # 创建新索引后重新加载
    coll.create_index(...)
    coll.load()
```

## 影响

- 🟡 存量部署无法自动从 IVF_FLAT 迁移到 HNSW
- 🟡 新部署不受影响（首次创建即为 HNSW）
