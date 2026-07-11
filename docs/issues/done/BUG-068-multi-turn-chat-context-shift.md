# BUG-068: 多轮对话消息结构错误导致上下文串位，LLM 答非所问

| 属性 | 值 |
|------|---|
| **严重级别** | 🔴 Critical |
| **影响模块** | Q&A 服务 → 多轮对话 Prompt 构建 |
| **发现方式** | 第二阶段测试知识库多轮对话会话 (`324f3a3d`) 内容审查 |
| **状态** | ✅ 已修复 — 2026-07-11 第二轮验收通过 |
| **发现日期** | 2026-07-11 |
| **修复日期** | 2026-07-11（两轮修复） |

---

## 现象

5 轮多轮对话中第 2 轮开始答案向后错一轮：问微服务答白鹿原，问测试报告答微服务。

## 根因

`qa_service.py:187-199` 的 `_build_prompt_messages`：
1. 把当前提问嵌入 system 消息尾部，历史对话放前面
2. DeepSeek 期待最后一个 user 消息是当前提问，但 system 消息里的 `用户问题：{question}` 与历史 user 消息产生冲突

## 修复内容（两轮）

### 第 1 轮：将当前提问作为独立 user 消息放末尾
```python
if history:
    messages = [Message(role="system", content=system_content)]
    messages += history
    messages.append(Message(role="user", content=question))  # 末尾 user
```

### 第 2 轮：SYSTEM_PROMPT_CHAT 模板去掉 {question}
```python
# 旧：模板含 "用户问题：{question} 请回答：" 
# 新：模板仅含 {context}，提问已在末尾 user 消息中
SYSTEM_PROMPT_CHAT = """你是一个专业的文档问答助手。...
{context}"""
```

## 验收结果（2026-07-11 第二轮）✅ 通过

5 轮多轮对话全部正确：

| 轮次 | 提问 | 回答 | 结果 |
|------|------|------|:--:|
| 1 | 性能指标的要求？ | P95<=500ms, 并发>=100, 可用性>=99.9% | ✅ |
| 2 | 核心功能通过率？ | 100% | ✅ |
| 3 | 测试报告延迟数据？ | 487ms | ✅ |
| 4 | 系统并发要求？ | >= 100 | ✅ |
| 5 | BUG修复验证率？ | >= 95% | ✅ |

Redis 会话 `96f362d64f58` 确认历史记录正确。

### 注意
验收时发现 Backend 容器需重启才能加载 `qa_service.py` 改动（bind mount 不会自动 reload Python 模块）。
