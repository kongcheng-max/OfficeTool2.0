# BUG-049: 对话历史仅存储在 localStorage，多设备不同步

| 属性 | 值 |
|------|---|
| **严重级别** | 🟢 Low |
| **影响模块** | 前端多轮对话 |
| **发现方式** | 代码审查 |
| **状态** | Open |
| **发现日期** | 2026-07-06 |

## 现象

用户在设备 A 上进行的多轮对话记录完全存储在浏览器的 `localStorage` 中，切换到设备 B 后无法看到之前的对话历史。后端 Redis 中虽有对话数据，但仅保留 1 小时且无列表查询 API。

## 根因

`pages/Chat/index.tsx:48-61`:

```typescript
function loadConversations(kbId: string): Conversation[] {
  const raw = localStorage.getItem(LS_PREFIX + kbId);
  return raw ? JSON.parse(raw) : [];
}

function saveConversations(kbId: string, convs: Conversation[]) {
  const trimmed = convs.slice(0, 50);
  localStorage.setItem(LS_PREFIX + kbId, JSON.stringify(trimmed));
}
```

后端虽有 Redis 存储（`services/qa_service.py:91-105`），但：
1. TTL 仅为 1 小时（`CONVERSATION_TTL = 3600`）
2. 没有对话列表查询 API（`GET /api/v1/kb/{kb_id}/conversations` 不存在）
3. 没有单对话查询 API（无法从 Redis 恢复历史）

前端和后端的对话系统完全解耦——前端自管理对话列表和消息，后端仅存储上下文以供 LLM 推理。

## 影响

- 🟢 用户切换浏览器/设备后对话历史丢失
- 🟢 清除浏览器缓存后所有对话记录消失
- 🟢 localStorage 有 5-10MB 限制，大量对话可能超限

## 修复建议

**短期方案**（推荐优先实施）:
1. 添加后端对话列表 API：`GET /api/v1/kb/{kb_id}/conversations`，从 Redis 读取用户的所有对话摘要
2. 延长 Redis TTL 或使用数据库持久化对话元数据
3. 前端启动时从后端加载对话列表，合并到本地状态

**长期方案**:
1. 创建 `Conversation` 数据库模型持久化对话元数据（标题、创建时间、消息数）
2. 消息内容保留在 Redis 中（热数据），元数据持久化到 PostgreSQL
3. 前端以服务端数据为准，localStorage 仅作为离线缓存
