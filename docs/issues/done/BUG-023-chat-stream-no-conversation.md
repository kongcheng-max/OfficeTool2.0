# BUG-023: 多轮流式对话不传递 conversation_id，流式追问丢失上下文

| 属性 | 值 |
|------|---|
| **严重级别** | 🟡 Medium |
| **影响 AC** | Week 7: 多轮对话 (5 轮上下文追问) |
| **发现方式** | 代码审查 |
| **状态** | Open |

## 现象
`api/qa.py:145` 的 `chat_conversation_stream` 端点调用 `qa_stream()` 而非专用 `chat_stream()`:

```python
async def generate():
    async for chunk_json in qa_stream(question=req.question, kb_id=kb_id):
        yield f"data: {chunk_json}\n\n"
```

`qa_stream()` 不接受 `conversation_id` 参数，也不从 Redis 读取对话历史。而非流式的 `chat()` 函数正确实现了完整的多轮对话（读历史 → 检索 → 生成 → 存历史）。

## 影响
- 非流式多轮对话正常 ✅
- 流式多轮对话的追问丢失上下文 ❌
- 用户使用 SSE 流式输出时无法进行多轮对话

## 修复
创建 `chat_stream()` 函数，将 `chat()` 的多轮逻辑与 `qa_stream()` 的 SSE 流式输出合并，或在 `qa_stream()` 中增加 `conversation_id` 参数支持。
