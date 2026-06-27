# BUG-006: 缺少 sentence-transformers 依赖

| 属性 | 值 |
|------|---|
| **严重级别** | 🟠 High |
| **影响 AC** | AC03 |
| **发现方式** | 代码审查 |
| **状态** | Open |

## 现象
`HuggingFaceEmbedder` 类存在但无法使用，因为 `sentence-transformers` 包未包含在依赖中。

## 根因
`app/pyproject.toml` 的依赖列表中没有 `sentence-transformers`。`app/engine/rag/embedder.py:40` 使用懒加载：

```python
def _lazy_load(self):
    if self._model is None:
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(self._model_name, device=self._device)
```

运行时调用会抛出 `ImportError: No module named 'sentence_transformers'`。

## 影响
即使修复 BUG-001 将 Embedder 切换到 HuggingFaceEmbedder，系统仍无法正常运行。

## 修复建议
在 `pyproject.toml` 添加：
```toml
"sentence-transformers>=2.2.0",
```
