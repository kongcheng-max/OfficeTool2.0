# BUG-079: `_retrieve` 中使用 `self._hit_key` 导致所有 Q&A 检索失败

| 属性 | 值 |
|------|-----|
| **编号** | BUG-079 |
| **严重度** | 🔴 BLOCKER |
| **模块** | `app/services/qa_service.py` |
| **发现日期** | 2026-07-12 |
| **状态** | 待修复 |
| **影响范围** | 全部 Q&A 功能（qa / qa_stream / chat / chat_stream） |

---

## 根因分析

`_retrieve()` 函数（第 252 行）是一个**模块级独立函数**（`async def _retrieve(...)`），但内部第 268 行和 279 行使用了 `self._hit_key(h)` —— `self` 在此上下文中不存在。

而 `_hit_key()`（第 312 行）被错误地标记了 `@staticmethod` 装饰器，但它也是一个模块级函数，不属于任何类。

### 错误代码

```python
# 第 252 行: 独立函数，不是类方法
async def _retrieve(question, kb_id, top_k=10, use_kg=True):
    ...
    # 第 268 行: self 不存在! → NameError
    all_hits = {self._hit_key(h): h for h in result["hits"]}
    ...
    # 第 279 行: self 不存在! → NameError
    k = self._hit_key(h)
```

### 异常堆栈

```
NameError: name 'self' is not defined
```

异常在第 308 行被 `try/except` 静默捕获:

```python
try:
    ...
    all_hits = {self._hit_key(h): h for h in result["hits"]}  # NameError!
except Exception as e:
    logger.warning(f"混合检索失败，降级为空列表: {e}")
    return []  # 返回空列表 → 所有问答返回"未找到相关文档"
```

---

## 复现步骤

1. 启动全部服务
2. 确保某个知识库中有 ready 状态的文档
3. 向该知识库发起任意问答请求（如"白鹿原是谁写的？"）
4. 答案始终为: "知识库中未找到与您问题相关的文档内容"
5. 后端日志显示: `混合检索失败，降级为空列表: name 'self' is not defined`

---

## 影响

- 🔴 **所有知识库的 Q&A 功能完全不可用**：`_retrieve()` 被 4 个路径调用（`qa`, `qa_stream`, `chat`, `chat_stream`），全部受影响
- 向量检索 + BM25 检索 + KG 检索均正常执行，但结果在去重阶段崩溃
- RRF 融合后的 10 条结果被丢弃，返回空列表
- 前端显示"知识库中未找到相关文档"，用户无法得到任何回答

---

## 修复方案

### 方案一: 去掉 `self.` 前缀（推荐）

`_hit_key` 本身是模块级函数，直接调用即可:

```python
# 修改第 268 行
- all_hits = {self._hit_key(h): h for h in result["hits"]}
+ all_hits = {_hit_key(h): h for h in result["hits"]}

# 修改第 279 行
- k = self._hit_key(h)
+ k = _hit_key(h)

# 修改第 312 行: 去掉多余的 @staticmethod
- @staticmethod
  def _hit_key(hit: Dict) -> str:
```

### 方案二: 将相关函数重构为类（工作量大，不推荐）

将 `_retrieve`、`_hit_key`、`_get_hybrid_retriever` 等改造成 `RetrievalService` 类的方法。

---

## 验证方法

1. 修复后重启 backend 容器
2. 调用 Q&A API 或后端直接调用 `qa()`:
```python
from services.qa_service import qa
result = await qa(question="白鹿原是谁写的？", kb_id="47e36926...")
assert len(result["sources"]) > 0
assert result["confidence"] > 0
assert "未找到" not in result["answer"]
```
3. 日志不应再出现 `name 'self' is not defined`

---

**报告人**: QA 测试部 | **日期**: 2026-07-12
