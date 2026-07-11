# BUG-066: 文档 status=ready 早于 Embedding 完成，导致检索无法命中

| 属性 | 值 |
|------|---|
| **严重级别** | 🟠 High |
| **影响模块** | 文档解析管线 + RAG 检索 |
| **发现方式** | 前端问答页面运行时测试 |
| **状态** | ✅ 已修复 — 2026-07-11 第三轮验收通过 |
| **发现日期** | 2026-07-11 |
| **修复日期** | 2026-07-11 |

---

## 现象

`战略合作协议.docx` 在前端显示绿色「就绪」（status=ready），但对该文档内容提问时，系统检索不到，LLM 回答"未找到相关信息"。实际上系统检索到了知识库中**其他已索引文档**（健身计划/Java资料/产品目录），唯独缺目标文档。

## 根因

**原始根因**：`tasks/parse.py` 解析完成后立即设置 `status="ready"`，不等 Embedding 完成。用户看到「就绪」以为可以用，但 Milvus 和 ES 都没有数据。

**第三轮发现的新根因**：`tasks/kg_build.py` 的 except handler 中使用 `_update_doc_status(doc_id, "ready", ...)`，当 KG 构建失败（如 Neo4j 不可用或 LLM API 超时）时会**覆盖** parse 设置的 `"parsed"` 状态，导致文档在 Embedding 未完成时就被标记为 `"ready"`。

## 影响

- 🟠 用户看到文档就绪，去提问却搜不到——功能假就绪
- 🟠 必须等 Embedding 重试成功（60-120s）才能真正检索
- 🟠 即使其他文档正常，用户也无法区分哪些可用、哪些还在索引中

## 修复方案

采用方案 A + 补充修复（三轮迭代）：

### 第一轮：parse.py 拆分状态
```python
# parse.py — 解析完成设 "parsed" 而非 "ready"
doc.status = "parsed"  # 旧: doc.status = "ready"
doc.chunk_count = len(chunks)

# 事务提交后 dispatch embed + kg
embed_document.delay(doc_id)
build_knowledge_graph.delay(doc_id)
```

### 第二轮：embed.py 独设 ready
```python
# embed.py — Embedding 写入 Milvus/ES 成功后设 ready
doc.status = "ready"  # ← 唯一的 ready 设置点
```

### 第三轮：kg_build.py 完全删除状态修改
```python
# kg_build.py — 删除 _update_doc_status 函数
# except handler 不再调用 _update_doc_status(doc_id, "ready", ...)
# KG 只做实体/关系抽取，不修改 doc.status
# ready 由 embed_document 独设，确保与 Milvus/ES 索引同步
```

## 验收结果（2026-07-11 第三轮）

### 状态流转验证

| 时间 | 状态 | chunks | 说明 |
|------|------|--------|------|
| 13:42:23 | `uploaded` | 0 | 文档上传 |
| 13:42:25 | `parsed` | 9 | Parse 完成 ✅ |
| 13:42:25~57 | `parsed` | 9 | **保持 32 秒**，等待 Embedding ✅ |
| 13:42:57 | `ready` | 9 | Embed 完成 → Milvus/ES 写入 ✅ |

### Q&A 检索验证

- 问题：「密码策略要求是什么？」
- 检索命中：**5 个来源**，全部来自 `网络安全管理制度.md`
- 答案：「密码长度不少于12位，包含大小写字母、数字和特殊字符，每90天强制更换」
- 答案准确性：✅ 与原文完全一致

### 关键代码改动

1. `app/tasks/parse.py:103` — `doc.status = "parsed"`（原为 `"ready"`）
2. `app/tasks/embed.py:157` — `doc.status = "ready"`（Embedding 成功后唯一设置点）
3. `app/tasks/kg_build.py:17-28` — 删除 `_update_doc_status` 函数调用，except handler 只 log + retry
4. `app/tasks/kg_build.py:117` — KG 完成注释："ready 由 embed 独设"

### 注意事项

- Celery worker 重启后需清理 `.pyc` 缓存（`find /app -name '__pycache__' -exec rm -rf {} +`），否则可能加载旧版本字节码
- Embed 任务首次执行仍可能遇到 event loop 冲突（`_run_async_safe` 的已知局限），但重试机制可保证最终成功
