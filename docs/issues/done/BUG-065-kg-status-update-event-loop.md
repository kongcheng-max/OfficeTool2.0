# BUG-065: KG 构建完成后状态更新失败，文档永久卡在「解析中」

| 属性 | 值 |
|------|---|
| **严重级别** | 🟠 High |
| **影响模块** | KG 构建任务 (tasks/kg_build.py) |
| **发现方式** | Docker 全量环境运行时测试 |
| **状态** | Open |
| **发现日期** | 2026-07-11 |

---

## 现象

上传 `战略合作协议.docx`（或其他大文档），解析成功（40 chunks），KG 抽取成功（47 entities, 332 relations），但文档最终状态停在 **kg_building**（前端显示「解析中」），永远到不了 `ready`。

Celery 日志：
```
解析完成: chunks=40 ✅
KG 构建: entities=47, relations=332 ✅
更新 Document 状态失败: "Future attached to a different loop" ❌
KG 构建完成 ❌（因为状态更新失败，函数继续执行但状态没改）
```

---

## 根因

`tasks/kg_build.py:121`：
```python
# 5. 更新 Document 状态：KG 构建完成
await _update_doc_status(
    doc_id, "ready",
    f"KG 构建完成: entities={len(entities)}, relations={relation_count}"
)
```

`_update_doc_status` 内部创建了新的 `async DB session`，在 `_run_async_safe` 的线程池上下文中执行异步 DB 操作时触发：

```
RuntimeError: Task got Future attached to a different loop
```

**关键问题**：状态更新失败后**没有 catch**，但函数继续执行并 log "KG 构建完成"。实际上 Neo4j 数据写入了、文档状态永远停在 `kg_building`。

这是 event loop 冲突的又一个变体——之前 BUG-059/060 修了 embed 和 kg_build 的入口调度，但 **kg_build 内部的 `_update_doc_status` 调用**使用了新的 async DB session，仍然撞上同一个坑。

---

## 影响

- 🟠 所有大文档（chunks 多、entities 多）都会触发此问题
- 🟠 文档状态永久卡在 kg_building，用户看到「解析中」不变化
- 🟠 Neo4j 有数据、Milvus 可能有数据，但文档状态不对，前端无法确认可用

---

## 修复建议

### 方案 A：状态更新改为同步 DB session（推荐）

```python
# tasks/kg_build.py
def _update_doc_status_sync(doc_id: str, status: str, message: str = ""):
    """同步更新文档状态，避免 event loop 冲突"""
    from core.database import engine as sync_engine
    from sqlalchemy.orm import Session
    with Session(sync_engine) as s:
        doc = s.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.status = status
            doc.error_message = message
            s.commit()
```

### 方案 B：catch 状态更新错误，至少保证函数不卡住

```python
try:
    await _update_doc_status(doc_id, "ready", ...)
except Exception as e:
    task_logger.warning(f"状态更新失败（不影响 KG 数据）: {e}")
    # 即使状态没更新，KG 数据已成功写入
```
