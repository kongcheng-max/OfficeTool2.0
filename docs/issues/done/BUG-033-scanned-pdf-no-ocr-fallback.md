# BUG-033: 扫描版 PDF 上传后无法被问答检索到

| 属性 | 值 |
|------|-----|
| 发现日期 | 2026-06-28 |
| 严重程度 | **严重** / Critical |
| 影响范围 | PDF 文档的问答功能 |
| 责任部门 | 后端开发组 + AI 引擎组 |
| 状态 | Open |

## 现象

1. 上传了一个 PDF 文件
2. 文档管理页面显示上传成功、解析完成
3. 但对这份 PDF 的内容提问时，系统回答「未能在知识库中找到相关信息」

## 根因

两层问题：

### 层级 1：扫描版 PDF 文本层为空

`E:\OfficeTool\app\engine\parser\pdf.py:21`：
```python
text = page.get_text("text")
```

PyMuPDF 的 `get_text("text")` 只提取 PDF 内嵌文本层。遇到以下情况时返回空字符串：
- 扫描件（图片型 PDF，无文本层）
- CJK 特殊字体编码
- 加密 PDF
- 损坏的 PDF

结果：解析器返回 0 个 chunk → `chunk_count = 0` → 文档虽然状态 "ready"，但 Milvus/ES 中无数据 → 问答完全不可见。

### 层级 2：无 OCR 回退机制

`E:\OfficeTool\app\services\document_service.py:89` 中，`ParserRegistry.find_for()` 根据文件扩展名 `.pdf` 始终匹配 `PDFParser`，永远不会尝试 `OCRParser`。

后端 OCR 解析器 (`ocr.py`) 已注册 `[".jpg", ".jpeg", ".png", ...]`，但没有代码将 PDF 解析失败 → OCR 回退串联起来。

## 修复方案

1. **PDF 解析器增加空文本检测**：解析完每个 page 后，如果 `text.strip() == ""`，记录警告日志并标记该页为「无文本层」
2. **OCR 回退机制**：对于扫描页（无文本层），调用 `OCRParser` 对页面截图为图片后做 OCR 提取
3. **解析报告**：文档解析完成后返回 `parse_warnings` 字段告知用户哪些页面需要 OCR 处理
4. **Docker 依赖**：确认 Dockerfile 中安装了 OCR 依赖（`pytesseract` + `tesseract-ocr` 系统包，或 `easyocr`）

## 复现步骤

1. 用扫描仪扫描一份纸质合同生成 PDF（或使用任意图片转 PDF 工具）
2. 上传到 OfficeTool
3. 等待解析完成
4. 对 PDF 内容提问 → 404 / 无结果

## 影响

严重影响 B2B 核心场景——大量企业文档（合同、发票、报告）都是扫描版 PDF。
