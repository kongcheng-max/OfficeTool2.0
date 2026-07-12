# BUG-017: SSE 流结束无 done 事件时前端 loading 不重置

| 属性 | 值 |
|------|---|
| **严重级别** | 🟡 Medium |
| **影响 AC** | AC07 |
| **发现方式** | 代码审查 |
| **状态** | Open |

## 现象
`app/frontend/src/api/qa.ts:98-102` 中 SSE 流在 `reader.read()` 返回 `done=true` 但从未收到 `type: done` 事件时：

```typescript
if (streamEnded) {
    onDone([], 0, '');
}
```

这会调用 `onDone`，但 Frontend Chat 组件在 `onDone` 中设置 `setLoading(false);`（第84行），而 `handleSend` 也在 stream 期间保持 loading=true。

## 根因
流式响应的边界条件处理：如果 SSE 流被异常中断，服务器未发送 `{"type":"done"}` 时，前端通过 `streamEnded` 为 true 兜底调用 `onDone`。

## 评估
实际上这段代码正确处理了边界情况 — 它通过 done 回调重置了 loading 状态。但这依赖 `streamEnded=true` 分支的正确执行。在异常情况下（网络中断等），`catch` 块中 `onError` 也会 `setLoading(false)`（Chat:102）。

**结论**: 该逻辑在当前实现下正确处理了所有路径。记录为信息性条目，非功能性 bug。
