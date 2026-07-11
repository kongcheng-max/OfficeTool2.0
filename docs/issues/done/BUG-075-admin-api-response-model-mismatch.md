# BUG-075: Admin API response_model 类型错误导致序列化 500

| 属性 | 值 |
|------|---|
| **严重级别** | 🔴 Critical |
| **影响模块** | Admin API → 用户管理 + 审计日志 |
| **发现方式** | Week 11 验收测试 |
| **状态** | 🔴 待修复 |
| **发现日期** | 2026-07-11 |

---

## 现象

`GET /api/v1/admin/users` 和 `GET /api/v1/admin/audit-logs` 均返回 500：

```
ResponseValidationError: {'type': 'list_type', 'loc': ('response', 'data'),
  'msg': 'Input should be a valid list', 'input': {'items': [...], 'total': 22, ...}}
```

## 根因

`admin.py:28` 声明了 `response_model=APIResponse[list]`，但实际返回的是分页 dict `{"items": [...], "total": N, "page": P, "page_size": S}`。

同样 `admin.py:113` 声明了 `response_model=APIResponse[dict]`，实际返回结构相同，但 `dict` 泛型 FastAPI 不会严格校验内部结构——这个可能不受影响。

## 修复

```python
# admin.py:28
@router.get("/users", response_model=APIResponse[dict])  # list → dict

# admin.py:113
@router.get("/audit-logs", response_model=APIResponse[dict])  # 保持不变
```
