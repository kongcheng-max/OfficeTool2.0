# BUG-046: SSE 流式端点不处理客户端断开连接

| 属性 | 值 |
|------|---|
| **严重级别** | 🟡 Medium |
| **影响模块** | 流式问答、资源消耗 |
| **发现方式** | 代码审查 |
| **状态** | Open |
| **发现日期** | 2026-07-06 |

## 现象

SSE 流式问答端点（`/qa/stream`、`/chat/stream`）在客户端断开连接（关闭页面、导航离开、网络中断）后，服务端继续消费 LLM token stream 直到完成，浪费 LLM API 调用配额和计算资源。

## 根因

`api/qa.py:71-82` 和 `qa.py:144-159` 的 `generate()` 异步生成器中没有检查客户端连接状态：

```python
async def generate():
    async for chunk_json in qa_stream(question=req.question, kb_id=kb_id):
        yield f"data: {chunk_json}\n\n"
```

FastAPI 的 `StreamingResponse` 支持通过 `request.is_disconnected()` 检查客户端状态，但当前代码未使用。

## 复现步骤

1. 在知识库中提问一个需要较长时间回答的问题
2. 在 LLM 仍在生成时关闭浏览器标签页或点击「新对话」
3. 观察后端日志 → LLM 调用仍在继续，直到完整回答生成完毕

## 影响

- 🟡 **LLM API 浪费**: 每次客户端断开都浪费一次完整的 LLM 调用
- 🟡 **后端资源占用**: generate() 协程持续运行直到 LLM 流结束
- 🟡 高频使用场景下可能触发 LLM API 的速率限制

## 修复建议

在 `generate()` 协程中注入 `Request` 对象，每次 yield 前检查连接状态：

```python
from fastapi import Request

@router.post("/api/v1/kb/{kb_id}/qa/stream")
async def ask_question_stream(kb_id: str, req: QARequest, request: Request, ...):
    async def generate():
        async for chunk_json in qa_stream(...):
            if await request.is_disconnected():
                logger.info(f"客户端断开，停止 SSE 流")
                break
            yield f"data: {chunk_json}\n\n"
```

同时可以考虑在 LLM 调用层（`engine/llm/base.py`）传递 abort signal，从根本上取消 HTTP 请求。
