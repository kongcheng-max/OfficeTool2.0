# BUG-072: 布局分析 footer 边界传参错误，导致所有正文被误判为页脚

| 属性 | 值 |
|------|---|
| **严重级别** | 🟠 High |
| **影响模块** | PDF 解析 → 布局分析 |
| **发现方式** | BUG-070 第二轮验收测试 |
| **状态** | 🔴 待修复 |
| **发现日期** | 2026-07-11 |

---

## 现象

`layout.py:analyze_page()` 第 119 行将 footer 边界参数传反：

```python
# layout.py:113-119 (BUG-070 修复后代码)
header_y = page_height * self.HEADER_RATIO        # 800 * 0.10 = 80
footer_y = page_height * (1 - self.FOOTER_RATIO)  # 800 * 0.90 = 720 ✅

header_candidates, footer_candidates = self._find_repeating_regions(
    blocks, global_page_texts, header_y, page_height - footer_y  # ❌ 800-720=80
)
```

`_find_repeating_regions` 接收的 footer 边界是 `80`（页面顶部），而非 `720`（页面底部）。导致所有 `y0 > 80` 的文本块被误判为页脚，body_blocks 全空。

实测结果（真实 A4 坐标）：
```
Headers: 1 ✅ (正确)
Footers: 7 ❌ (应=1，实际包含全部正文)
Body blocks: 0 ❌ (应=6)
Columns: 0 ❌ (应=2)
```

**修复**：

```python
# 将 page_height - footer_y 改为 footer_y
header_candidates, footer_candidates = self._find_repeating_regions(
    blocks, global_page_texts, header_y, footer_y  # ← 直接传 footer_y
)
```

## 影响

- 🟠 BUG-070 修复后 PDF 解析的布局分析完全不可用
- 🟠 正文被清空，chunk 输出为空

## 备注

此 Bug 由 BUG-070 的修复引入，属于修复代码的 regression。建议在 `_find_repeating_regions` 参数名上明确含义（如 `footer_start_y`）避免混淆。
