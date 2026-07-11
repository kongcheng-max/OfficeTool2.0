# BUG-070: 文档布局分析模块已实现但未接入 PDF 解析管线

| 属性 | 值 |
|------|---|
| **严重级别** | 🟠 High |
| **影响模块** | PDF 解析 → 文档结构化 |
| **发现方式** | Week 9 代码审查 |
| **状态** | 🔴 待修复 |
| **发现日期** | 2026-07-11 |

---

## 现象

`engine/parser/layout.py` 已实现完整的 `LayoutAnalyzer` 类（多栏识别、页眉页脚过滤、表格定位），但模块级单例 `layout_analyzer` 在整个项目中**从未被导入或调用**。

```
$ grep -rn "layout_analyzer\|LayoutAnalyzer" app/
app/engine/parser/layout.py:36:class LayoutAnalyzer:
app/engine/parser/layout.py:275:layout_analyzer = LayoutAnalyzer()
```

仅在自身文件中出现，`pdf.py` 的 `_parse_page()` 方法未使用布局分析结果。

## 根因

`pdf.py` 的 `_parse_page()` 直接调用 `page.get_text("text")` 提取全文，未先通过 `LayoutAnalyzer` 过滤页眉页脚、识别多栏阅读顺序、定位表格区域。

## 影响

- 🟠 PDF 解析产出中可能混入页眉页脚重复文本
- 🟠 多栏 PDF 的文本阅读顺序可能不正确
- 🟠 表格区域未做特殊标记，chunk 内容可能丢失表格结构

## 修复建议

在 `pdf.py` 的 `_parse_page()` 或 `parse_stream()` 中集成布局分析：

```python
from engine.parser.layout import layout_analyzer

# 在解析每页时
blocks = layout_analyzer.extract_blocks_from_fitz(page)
layout = layout_analyzer.analyze_page(page_num, blocks, page_width, page_height,
                                       global_page_texts=all_page_texts)

# 仅用 body_blocks（过滤页眉页脚）
body_text = "\n".join(b.text for b in layout.body_blocks)

# 多栏页面按列排序
if len(layout.columns) > 1:
    # 按列组织文本
    ...
```
