# BUG-058: 搜索端点直接访问未初始化的 _hybrid_retriever 导致 500 错误

| 属性 | 值 |
|------|---|
| **严重级别** | 🔴 Critical |
| **影响模块** | 搜索 API、知识库问答前置检索 |
| **发现方式** | Docker 全量环境运行时测试 |
| **状态** | ✅ Done — 2026-07-09 第二次验收通过 |
| **发现日期** | 2026-07-09 |

## 验收记录

**2026-07-09 第一次验收**：
- ✅ `GET /search`（向量搜索）→ code=0, 不再报 500
- ❌ `GET /search/hybrid`（混合搜索）→ 新的 500 错误

混合搜索新错误日志：
```
ResponseValidationError: 1 validation error:
  {'type': 'list_type', 'loc': ('response', 'data'), 'msg': 'Input should be a valid list'}
```

原因：`hybrid_search` 返回 `APIResponse.success({items:[...], total:1, ...})` 是一个 dict，但 `response_model=APIResponse[list]` 期望 data 是数组。需要改为 `APIResponse[dict]`。

## 现象

`GET /api/v1/kb/{kb_id}/search` 和 `GET /api/v1/kb/{kb_id}/search/hybrid` 两个搜索端点均返回 HTTP 500：

```json
{"code":500,"message":"服务器内部错误","data":null}
```

后端日志：
```
AttributeError: 'NoneType' object has no attribute 'vector'
  File "/app/api/search.py", line 50, in search
    hits = await _hybrid_retriever.vector.retrieve(q, kb_id=kb_id, top_k=top_k)
```

## 根因

`api/search.py:12` 直接导入了模块级变量 `_hybrid_retriever`：

```python
from services.qa_service import _hybrid_retriever
```

该变量在 `services/qa_service.py:25` 初始值为 `None`，只有通过 `_get_hybrid_retriever()` 函数调用才会懒加载初始化（首次使用时加载 Embedding 模型）。

问答端点 `qa()` / `chat()` 内部调用了 `_retrieve()` → `_get_hybrid_retriever()`，所以正常工作。但搜索端点绕过了这个初始化函数，直接访问未初始化的 `_hybrid_retriever.vector`，触发 `AttributeError`。

## 复现步骤

1. Docker 全量环境启动（不经过任何 QA 操作）
2. 直接调用搜索 API：`GET /api/v1/kb/{kb_id}/search?q=test`
3. 返回 HTTP 500

如果先调用一次问答 API（会触发初始化），再调用搜索 API → 正常工作。这就是为什么这个 bug 之前没被发现——测试流程通常是先测问答再测搜索。

## 影响

- 🔴 用户首次使用搜索功能必定报错
- 🔴 前端搜索框和混合检索页面不可用
- 依赖触发顺序：必须先问答一次 "预热" 后才能搜索

## 修复建议

`api/search.py` 不应直接导入模块变量，应导入初始化函数：

```python
# 修改前
from services.qa_service import _hybrid_retriever
hits = await _hybrid_retriever.vector.retrieve(q, kb_id=kb_id, top_k=top_k)

# 修改后
from services.qa_service import _get_hybrid_retriever
retriever = _get_hybrid_retriever()
hits = await retriever.vector.retrieve(q, kb_id=kb_id, top_k=top_k)
```

同时建议将 `_hybrid_retriever` 改为模块私有（加下划线前缀），避免外部直接访问。
