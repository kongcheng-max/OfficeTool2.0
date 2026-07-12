# BUG-024: OCR 解析器缺少 pip 依赖 (paddleocr / pytesseract)

| 属性 | 值 |
|------|---|
| **严重级别** | 🟡 Medium |
| **影响 AC** | Week 5: 图片 OCR 解析 |
| **发现方式** | 代码审查 |
| **状态** | Open |

## 现象
`engine/parser/ocr.py` 中的 `OCRParser` 使用 lazy-load 模式优雅处理缺失依赖：
```python
try:
    from paddleocr import PaddleOCR
except ImportError:
    PaddleOCR = None
```

但 `pyproject.toml` 的 dependencies 和 Dockerfile 的 pip install 列表中均不包含 `paddleocr` 或 `pytesseract`。

## 影响
- OCRParser 在任何环境下都返回空结果（永远命中 ImportError fallback）
- 图片文件 (.jpg/.png/.tiff/.bmp) 上传后解析为空

## 修复
在 `pyproject.toml` 的 `[project.optional-dependencies]` 添加 OCR 可选组：
```toml
ocr = ["paddleocr>=2.7.0", "pytesseract>=0.3.0"]
```
或在文档中标注 OCR 需手动安装依赖。
