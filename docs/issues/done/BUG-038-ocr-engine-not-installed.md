# BUG-038: 上传 jpg/png 图片后块数为 0

| 属性 | 值 |
|------|-----|
| 发现日期 | 2026-06-28 |
| 严重程度 | **严重** / Critical |
| 影响范围 | 图片上传功能完全无效 |
| 责任部门 | 后端开发组 / DevOps |
| 状态 | Open |

## 现象

1. 上传 .jpg / .png 图片文件
2. 文档列表显示状态为「就绪」，但块数始终为 0
3. 无法对图片内容进行问答

## 根因

**Docker 容器中未安装任何 OCR 引擎。**

`E:\OfficeTool\app\engine\parser\ocr.py:36-65` 的 `_lazy_load_ocr()`：
```python
# 优先尝试 PaddleOCR
from paddleocr import PaddleOCR  # → ImportError（未安装）
# 降级 Tesseract
import pytesseract  # → ImportError（未安装）
# 结果
self._ocr_type = None  # parse() returns []
```

验证结果：
```
PaddleOCR: NOT INSTALLED
Tesseract: NOT INSTALLED
PyMuPDF: AVAILABLE
```

Celery 日志证实：
```
parse_document[...] succeeded: {'status': 'ready', 'chunks': 0, 'parser': 'ocr'}
```

## 修复方案

### 方案 A（推荐）：Dockerfile 安装 Tesseract + pytesseract

```dockerfile
# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    tesseract-ocr-chi-tra \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
RUN pip install pytesseract Pillow
```

### 方案 B：安装 PaddleOCR（中文识别更好但更重，镜像 +2GB）

```dockerfile
RUN pip install paddlepaddle paddleocr
```

推荐方案 A（Tesseract），轻量且对中文支持可接受。

## 影响

图片上传是完整的空操作——文件存了、status=ready，但内容不可检索。所有 `.jpg/.png/.bmp/.tiff/.webp` 上传都受影响。
