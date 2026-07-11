# BUG-063: Docker 容器内 OCR 引擎未安装，图片文件解析后文本块为 0

| 属性 | 值 |
|------|---|
| **严重级别** | 🟠 High |
| **影响模块** | OCR 图片解析 |
| **发现方式** | Docker 全量环境运行时测试 |
| **状态** | Open |
| **发现日期** | 2026-07-11 |

---

## 现象

上传图片文件（PNG/JPG）后：
- JPG：状态可走到 `ready`，但 **chunk_count = 0**，无文本被提取
- PNG：偶发卡在 `uploaded`（Celery 任务调度问题，见 BUG-062），即使走到 ready 也是 0 chunks

用户以为 JPG "正常"是因为状态变绿了，实际上图片内的文字**完全没有被识别**。

---

## 根因

Celery 日志：
```
parse_document: 开始解析: parser=ocr, file=扫描图片.jpg
DEBUG: PaddleOCR 未安装
DEBUG: pytesseract 或 Pillow 未安装
parse_document: 解析完成: chunks=0
```

`engine/parser/ocr.py` 的 `_lazy_load_ocr()` 依次尝试：
1. `from paddleocr import PaddleOCR` → `ImportError`（Dockerfile 未安装 paddleocr pip 包）
2. `import pytesseract` → `ImportError`（Dockerfile 安装了 pytesseract 但 Pillow 导入失败）

Docker 构建时 `apt-get install tesseract-ocr` 因为 Debian 源连不上而失败（之前修复了国内镜像但仍可能有问题）。而且 `Pillow` 作为图像处理库，也可能因为缺少系统级 libjpeg 等依赖而部分功能异常。

结果：两个 OCR 引擎都不可用，`parse()` 直接 `return []`，文档变成 ready + 0 chunks。

---

## 影响

- 🟠 所有图片文件（PNG/JPG/BMP/TIFF）上传后无法提取文字
- 🟠 扫描版 PDF 的 OCR 回退路径同样失效
- 🟠 用户上传图片后虽然显示"就绪"，但问答完全无法检索图片中的文字

---

## 修复建议

### P0：确保 Dockerfile 构建时 OCR 依赖安装成功

```dockerfile
# Dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    tesseract-ocr-eng \
    libjpeg-dev zlib1g-dev \   # Pillow 系统依赖
    && rm -rf /var/lib/apt/lists/*

RUN pip install pytesseract Pillow paddleocr
```

### P1：OCR 不可用时给文档标记错误信息

```python
# engine/parser/ocr.py
async def parse(self, file_path, original_filename):
    self._lazy_load_ocr()
    if self._ocr_type is None:
        raise RuntimeError("OCR 引擎不可用：PaddleOCR 和 Tesseract 均未安装")
    ...
```

这样解析失败时 status="failed" + error_message，用户可以明确知道问题，而不是看到假的"就绪"。
