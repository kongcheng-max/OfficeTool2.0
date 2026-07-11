# BUG-060: 文档解析管线过慢 — 串行阻塞 + 无效重试 + KG 构建失败

| 属性 | 值 |
|------|---|
| **严重级别** | 🟠 High |
| **影响模块** | 文档解析管线（parse → embed → kg_build） |
| **发现方式** | 本地 Windows 运行时测试 |
| **状态** | ✅ Done — 2026-07-09 验收通过 |
| **发现日期** | 2026-07-09 |

---

## 现象

本地启动 Celery Worker (`--pool=solo`) 后，文档解析速度很慢，一个文件从上传到 ready 需要数分钟。具体表现：

1. 文档在 "已上传" → "解析中" → "就绪" 之间转换极慢
2. 日志中看到大量 "任务失败 → retry in 60s" 的等待
3. KG 构建任务始终报 event loop 错误，重试 2 次后放弃

---

## 根因分析（三个叠加问题）

### 问题 1：KG 构建未同步修复（仍用旧 event loop 模式）

`tasks/kg_build.py:19-21`：
```python
def build_knowledge_graph(self, doc_id: str):
    from tasks.celery_app import run_async_in_worker
    return run_async_in_worker(lambda: _async_build_kg(doc_id))
```

BUG-059 只修复了 `embed.py`（引入 `_run_async_safe`），但 **`kg_build.py` 仍然使用旧的 `run_async_in_worker`**。在 `--pool=threads` 或 `--pool=solo` 下均会触发 event loop 冲突：

```
ERROR: KG 构建任务失败: Task got Future attached to a different loop
```

每次失败 → 重试 60s 后 → 再失败 → 再重试 60s → 最终放弃。**每个文档浪费 120 秒**。

### 问题 2：Embed 首次执行必定失败 + 60s 重试间隔

`tasks/embed.py` 的 `_run_async_safe` 在 retry 时能成功，但 **首次执行仍然失败**，触发 60s 固定等待。流水线：

```
parse (1s) → embed 1st fail (1s) → wait 60s → embed retry OK (15s) → kg 1st fail (1s) → wait 60s → kg retry fail (1s) → wait 60s → kg final fail
                                                                                                ↑ 仍在用旧 run_async_in_worker
```

一个文档走完整个管线 = **解析 1s + 等待 60s + Embedding 15s + 等待 120s + KG 重试** ≈ 3 分钟以上。

### 问题 3：solo pool 串行执行

`--pool=solo` 模式下，所有任务（parse、embed、kg_build）由单个进程**串行执行**。如果 Redis 队列里堆积了多个文档的任务，必须等前一个文档的三个任务全部走完（包括中间的 60s 重试等待），下一个文档才能开始。

---

## 影响

- 🟠 用户上传文档后，等待 3-5 分钟才看到状态变为 ready
- 🟠 批量上传时，文档逐个串行处理，N 个文档需要 N×3 分钟
- 🟠 KG 构建始终失败，知识图谱无数据（实体/关系丢失）
- 🟠 前端用户看到 "解析中" 长时间不变化，容易认为系统故障

---

## 修复建议

### P0：统一 KG 构建的 event loop 模式（复制 embed 的修复）

```python
# tasks/kg_build.py
from tasks.embed import _run_async_safe  # 从 embed.py 导入

@celery_app.task(...)
def build_knowledge_graph(self, doc_id: str):
    try:
        return _run_async_safe(_async_build_kg(doc_id))
    except Exception as exc:
        ...
```

### P1：减少无效的 60s 重试等待

- 将 `default_retry_delay` 从 60s 降到 **10s**（首次 event loop 错误重试不需要等那么久）
- 或者：检测到 RuntimeError("event loop") 时**立即同步重试**，不经过 Celery retry 机制

### P2：Windows 下使用 `--pool=threads` 替代 solo

```bash
celery -A tasks.celery_app worker --loglevel=info --pool=threads --concurrency=2
```

实测 `--pool=threads` + `_run_async_safe` 可以正常工作（embed 已验证）。

### P3：允许跳过 KG 构建以加速测试

在 `.env` 中增加开关：
```
KG_ENABLED=false  # 测试环境可关闭 KG 构建加速解析
```
