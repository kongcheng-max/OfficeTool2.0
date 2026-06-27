# BUG-014: TextParser 将整个文件作为单个 chunk

| 属性 | 值 |
|------|---|
| **严重级别** | 🟢 Low |
| **影响 AC** | AC01 |
| **发现方式** | 代码审查 |
| **状态** | Open |

## 现象
`TextParser` (处理 .txt) 将整个文件内容作为一个 chunk 返回，不进行任何分段。

## 根因
`app/engine/parser/text.py` 的 TextParser 实现：

```python
async def parse(self, file_path, original_filename):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    return [Chunk(content=content, metadata={...}, chunk_type="text")]
```

虽然后续 `TextSplitter` 会进一步分割，但相比 MarkdownParser（按 `##` 标题分段），txt 文件在解析阶段丢失了所有结构信息。

## 影响
- 长 TXT 文件的检索精度低于 MD 文件
- 后续 RAG 管道无法区分章节

## 修复建议
考虑在 TextParser 中按双换行分段，生成多个 chunk 以保留段落结构。
