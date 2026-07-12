# BUG-080: 后端未实现问答计数，所有知识库 `qa_count` 始终为 0

| 属性 | 值 |
|------|-----|
| **编号** | BUG-080 |
| **严重度** | 🟡 MEDIUM |
| **模块** | `app/models/models.py` / `app/schemas/schemas.py` / `app/api/knowledge_base.py` / `app/services/qa_service.py` |
| **发现日期** | 2026-07-12 |
| **状态** | 待修复 |
| **影响范围** | 仪表盘 Q&A KPI、知识库卡片"0次问答"显示 |

---

## 根因分析

前端 `Dashboard` 和 `KnowledgeBaseCard` 均读取 `qa_count` 字段用于展示，但**后端从未实现该字段**。具体缺失:

### 1. 数据库模型无此列
`KnowledgeBase` 模型 ([models.py:43-62](app/models/models.py#L43-L62)) 只有 `chunk_count`，无 `qa_count`:

```python
class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"
    id, name, description, owner_id = ...
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)  # 仅有 chunk_count
    # ❌ 缺少: qa_count
```

### 2. Schema 无此字段
`KBResponse` ([schemas.py:80-91](app/schemas/schemas.py#L80-L91)):

```python
class KBResponse(BaseModel):
    ...
    chunk_count: int
    doc_count: int = 0
    # ❌ 缺少: qa_count
```

### 3. 问答调用处无自增逻辑
`qa_service.py` 的 `qa()` / `chat()` / `qa_stream()` 函数执行问答后，**没有更新** KB 的问答计数。

### 4. `_enrich_kb()` 未补充此字段
```python
async def _enrich_kb(kb, db):
    # 仅统计 doc_count，无 qa_count 逻辑
```

### 5. 前端已有预期
- `kb.ts:9`: `qa_count?: number;`
- `Dashboard.tsx:62`: `totalQAs = list.reduce((sum, kb) => sum + (kb.qa_count || 0), 0)`
- `KnowledgeBaseCard.tsx:67`: `<MessageOutlined /> {qaCount} 问答`

---

## 复现步骤

1. 创建知识库，上传文档并等待 ready
2. 进行多次问答（功能恢复后）
3. 仪表盘 "累计问答" 始终显示 0
4. 知识库管理页每个卡片始终显示 "0 问答"

---

## 修复方案

需端到端实现问答计数，涉及 5 处改动：

### A. 模型添加字段
```python
# models.py — KnowledgeBase 类新增
qa_count: Mapped[int] = mapped_column(Integer, default=0)
```

### B. 数据库迁移
```bash
alembic revision -m "add qa_count to knowledge_bases"
# upgrade: ALTER TABLE knowledge_bases ADD COLUMN qa_count INTEGER DEFAULT 0;
```

### C. Schema 添加字段
```python
# schemas.py — KBResponse 新增
qa_count: int = 0
```

### D. QA Service 中增加计数
在 `qa_service.py` 的 `qa()` / `qa_stream()` / `chat()` / `chat_stream()` 四个函数中，入库成功后递增。考虑使用 Redis 批量写入减轻 DB 压力:

```python
# 每次问答/chat 后调用
async def _incr_qa_count(kb_id: str):
    """递增知识库问答计数（Redis 暂存 + 定期刷入 DB）"""
    r = await _get_redis()
    if r:
        await r.incr(f"qa_counter:{kb_id}")
        await r.expire(f"qa_counter:{kb_id}", 3600 * 24)
```

或直接用 SQL:

```python
from sqlalchemy import update
async def _incr_qa_count(kb_id: str, db: AsyncSession):
    await db.execute(
        update(KnowledgeBase)
        .where(KnowledgeBase.id == kb_id)
        .values(qa_count=KnowledgeBase.qa_count + 1)
    )
```

### E. `_enrich_kb()` 包含 `qa_count`
KB 列表查询时直接使用模型字段即可（已从 DB 加载）。

---

## 验证方法

1. 应用迁移后创建新 KB 并上传文档
2. 执行几次 Q&A 问答
3. 检查:
   - 仪表盘 "累计问答" > 0
   - KB 卡片显示 "N 问答"（N > 0）
   - DB: `SELECT qa_count FROM knowledge_bases WHERE id = '...'` 返回正确值

---

**关联**: [[BUG-079]] (Q&A 检索失败，修复后问答计数才能被触发)

**报告人**: QA 测试部 | **日期**: 2026-07-12
