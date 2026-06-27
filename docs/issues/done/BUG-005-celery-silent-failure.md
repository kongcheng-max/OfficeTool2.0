# BUG-005: Celery 不可用时文档解析静默失败

| 属性 | 值 |
|------|---|
| **严重级别** | 🟠 High |
| **影响 AC** | AC01, AC02 |
| **发现方式** | 代码审查 |
| **状态** | Open |

## 现象
上传文档后，如果 Celery Worker 未运行，文档状态永远停留在 `uploaded`，不会被解析或入库。前端轮询只能看到文档一直在等待处理。

## 根因
`app/services/document_service.py:96-103` 的 `_trigger_parse_task` 函数：

```python
def _trigger_parse_task(doc_id: str):
    try:
        from tasks.parse import parse_document
        parse_document.delay(doc_id)
    except Exception as e:
        logger.warning(f"Celery 不可用，解析任务未提交: {e}")
        # Celery 不可用时，解析将在后续通过其他方式触发
```

注释声称"解析将在后续通过其他方式触发"，但实际上并没有任何重试或兜底机制。

## 影响
- 无 Celery 环境下用户无法正常使用系统
- 前端无明确提示告知用户文档处理失败

## 修复建议
1. 增加同步解析兜底（非生产环境）
2. 在 API 响应中明确告知用户 Celery 状态
3. 添加定时任务扫描处于 `uploaded` 状态的文档并重试
