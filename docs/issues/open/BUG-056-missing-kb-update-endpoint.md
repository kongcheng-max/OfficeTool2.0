# BUG-056: 缺少知识库更新 API 端点

| 属性 | 值 |
|------|---|
| **严重级别** | 🟡 Medium |
| **影响模块** | 知识库管理 |
| **发现方式** | 代码审查 |
| **状态** | Open |
| **发现日期** | 2026-07-06 |

## 现象

后端定义了 `KBUpdateRequest` Schema（`schemas/schemas.py:53-55`），支持更新 `name` 和 `description` 字段，但 `api/knowledge_base.py` 中没有对应的 PATCH 或 PUT 端点。用户创建知识库后无法修改其名称或描述。

## 根因

`schemas/schemas.py:53-55`:
```python
class KBUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    description: Optional[str] = None
```

Schema 已定义但未使用。`api/knowledge_base.py` 只有 `create_kb (POST)`, `list_kbs (GET)`, `get_kb (GET)`, `delete_kb (DELETE)`，缺少 update 端点。

## 影响

- 🟡 用户创建知识库后无法修改名称，只能删除重建
- 🟡 知识库描述无法更新

## 修复建议

在 `api/knowledge_base.py` 中添加 PATCH 端点：

```python
@router.patch("/{kb_id}", response_model=APIResponse[KBResponse])
async def update_kb(
    kb_id: str,
    req: KBUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新知识库名称/描述"""
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.owner_id == current_user.id,
        )
    )
    kb = result.scalar_one_or_none()
    if not kb:
        raise NotFoundError("知识库")
    
    if req.name is not None:
        kb.name = req.name
    if req.description is not None:
        kb.description = req.description
    
    await db.flush()
    await db.refresh(kb)
    data = await _enrich_kb(kb, db)
    return APIResponse.success(data, message="知识库已更新")
```
