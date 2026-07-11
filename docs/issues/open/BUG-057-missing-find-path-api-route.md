# BUG-057: 缺少实体最短路径 API 端点

| 属性 | 值 |
|------|---|
| **严重级别** | 🟢 Low |
| **影响模块** | 知识图谱 API |
| **发现方式** | 代码审查 |
| **状态** | Open |
| **发现日期** | 2026-07-06 |

## 现象

后端服务层和引擎层都实现了实体间最短路径查询功能（`services/graph_service.py:121-125` 导出 `find_path`，`engine/kg/query.py` 实现 `GraphQuery.find_shortest_path()`），但 `api/graph.py` 中没有对应的 HTTP 端点。用户无法通过 API 查询两个实体之间的关系路径。

## 根因

`api/graph.py` 只注册了三个路由：
- `GET /entities` — 实体搜索
- `GET /entity/{entity_name}/network` — 实体关系网络
- `GET /entity/{entity_name}` — 实体详情

缺少 `GET /path/{entity_a}/{entity_b}` 类的端点。

## 影响

- 前端图谱页面缺少"查找两个实体间的关联路径"功能

## 修复建议

在 `api/graph.py` 中添加路径查询端点：

```python
@router.get("/path/{entity_a}/{entity_b}", response_model=APIResponse[dict])
async def entity_path(
    kb_id: str,
    entity_a: str,
    entity_b: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询两个实体之间的最短关系路径"""
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.owner_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise NotFoundError("知识库")
    
    path = await find_path(entity_a, entity_b)
    if not path:
        raise NotFoundError("未找到关联路径")
    return APIResponse.success(path)
```
