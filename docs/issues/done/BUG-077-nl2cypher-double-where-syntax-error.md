# BUG-077: NL2Cypher 生成的查询包含双 WHERE 子句导致 Cypher 语法错误

| 属性 | 值 |
|------|---|
| **严重级别** | 🟡 Medium |
| **影响模块** | 知识图谱 → NL2Cypher 自然语言查询 |
| **发现方式** | Week 11 验收测试 |
| **状态** | 🔴 待修复 |
| **发现日期** | 2026-07-11 |

---

## 现象

用户问「有哪些公司」时，NL2Cypher 生成的查询报语法错误：

```
Cypher: MATCH (e:Entity) WHERE e.type='ORG' WHERE $kb_id IN e.kb_ids RETURN e.name, e.type LIMIT 20
Error: Invalid input 'WHERE': expected an expression, ... (line 1, column 37)
```

## 根因

LLM 生成了含 `WHERE` 的 Cypher（`WHERE e.type='ORG'`），代码又在注入时追加了 `WHERE $kb_id IN e.kb_ids`，导致一条语句中出现两个 `WHERE` 子句。

正确的做法应该是用 `AND` 连接条件，或代码在注入前解析/合并 LLM 生成的 WHERE 条件。

## 修复建议

在 `engine/kg/query.py` 中，注入 kb_id 过滤条件前检测 LLM 生成的 Cypher 是否已含 WHERE，若已含则用 `AND` 追加：

```python
if 'WHERE' in generated_cypher.upper():
    # 已含 WHERE，用 AND 追加
    cypher = generated_cypher.replace('RETURN', f'AND $kb_id IN e.kb_ids RETURN', 1)
else:
    # 无 WHERE，直接添加
    cypher = generated_cypher.replace('RETURN', f'WHERE $kb_id IN e.kb_ids RETURN', 1)
```
