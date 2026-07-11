# BUG-061: 多格式小文件上传后长期卡在「解析中」，仅 TXT/CSV/XML 正常

| 属性 | 值 |
|------|---|
| **严重级别** | 🔴 Critical |
| **影响模块** | 文档解析引擎（PDF / DOCX / PPTX / HTML / OCR 图片 / JSON） |
| **发现方式** | 本地 Windows Celery `--pool=solo` 运行时测试 |
| **状态** | ✅ Done — 2026-07-09 验收通过 |
| **发现日期** | 2026-07-09 |

---

## 实测数据

| 文件 | 大小 | 状态 | 原因 |
|------|------|:--:|------|
| TXT | 36 B | ✅ ready | 纯 Python I/O |
| CSV | 538 B | ✅ ready | 纯 Python csv |
| XML | 3.8 KB | ✅ ready | lxml 轻量文本提取 |
| JSON | **171 B** | ❌ processing | 自身秒级但被堵死 |
| HTML | 2.4 KB | ❌ processing | lxml C 扩展阻塞 |
| PPTX | 74.7 KB | ❌ processing | python-pptx→lxml 阻塞 |
| PNG | 174.4 KB | ❌ processing | OCR 依赖缺失空转 |
| JPG | 874.8 KB | ❌ processing | OCR 依赖缺失空转 |
| PDF | 386.6 KB | ❌ processing | PyMuPDF C 库 + OCR 回退 |

---

## 全部格式风险审计

| 格式 | 风险 | 依赖 | 分析 |
|------|:----:|------|------|
| TXT | ✅ SAFE | 无 | 纯 Python I/O + 字符串 split |
| MD | ✅ SAFE | 无 | 纯 Python I/O + 正则切分 |
| CSV | ✅ SAFE | csv 模块 | 纯 Python csv reader |
| XML | ✅ SAFE | lxml | lxml 但仅递归文本提取，极轻量 |
| XLSX | ⚠️ LOW | openpyxl | `read_only=True` 流式读取，正常快 |
| PDF | 🔴 HIGH | PyMuPDF (fitz) | **C 库同步调用** + 含 OCR 回退路径 |
| DOCX | 🔴 HIGH | python-docx→lxml | **lxml C 扩展**同步解析 XML |
| PPTX | 🔴 HIGH | python-pptx→lxml | 同 DOCX，lxml C 扩展 |
| HTML | 🔴 HIGH | BeautifulSoup→lxml | **lxml C 扩展**同步解析 HTML |
| JSON | ⚠️ QUEUE | 无 | 自身纯 Python 秒级，但 solo 下被堵死 |
| OCR | 🔴 HIGH | PaddleOCR/Tesseract | 同步 OCR 调用 + Windows 依赖缺失 |

**共同特征**：所有 🔴HIGH 的解析器全是 `async def parse()` 里面做**纯同步 C 扩展调用**，在 `asyncio.run()` 的事件循环里长时间阻塞。

## 各解析器卡住根因

### PPTX → `python-pptx` 同步阻塞
`Presentation()` 内部用 zipfile + lxml C 扩展解析 PPTX 结构，全程同步阻塞 event loop。

### HTML → `BeautifulSoup + lxml` 同步阻塞
`BeautifulSoup(html, "lxml")` 调用 lxml HTML parser (C 扩展)，同步阻塞。

### PNG / JPG (OCR) → PaddleOCR/Tesseract 未安装导致空转
`engine/parser/ocr.py:36-65` — `_lazy_load_ocr()` 尝试依次 import：
1. `from paddleocr import PaddleOCR` → Windows 大概率未安装 → `ImportError`
2. `import pytesseract` → pip 包可能存在，但 **系统级 Tesseract 二进制未安装** → `pytesseract.image_to_string()` 调用时**找不到 tesseract 可执行文件** → 抛异常或阻塞

本地 Windows 几乎不可能同时装好 PaddleOCR + Tesseract 中文语言包，OCR 解析器每次都会走一轮 import → 失败 → 回退的无效链路。

### JSON → 被前面任务堵死
JSON 解析器本身很快（纯 Python `json.load` + 递归），但在 `--pool=solo` 下，前面 PPTX/HTML/OCR 任务阻塞了整个 worker，JSON 任务根本没机会执行。

---

## 根因总结

### 因子 1：parse task 仍用旧的 `run_async_in_worker`

`tasks/parse.py:29-30`：
```python
def parse_document(self, doc_id: str):
    from tasks.celery_app import run_async_in_worker
    return run_async_in_worker(lambda: _async_parse(doc_id))
```

BUG-059/060 只修了 `embed.py` 和 `kg_build.py`，**parse 任务没有被同步修复**。在 solo/threads pool 下可能触发 event loop 冲突。

### 因子 2：PPTX/HTML 解析器同步阻塞 event loop

`engine/parser/pptx.py:17-62` 和 `engine/parser/html_xml.py:18-55`：

两个解析器的 `parse()` 方法标记为 `async def`，但**内部完全是同步阻塞操作**：

**PPTX**：
```python
async def parse(self, file_path, original_filename):
    prs = Presentation(file_path)       # zipfile + lxml 同步解析
    for slide in prs.slides:            # 遍历 PPT 结构
        for shape in slide.shapes:      # python-pptx 内部大量 XML 解析
```

**HTML**：
```python
async def parse(self, file_path, original_filename):
    soup = BeautifulSoup(html, "lxml")  # lxml HTML parser (C 扩展)
    for tag in soup(self.SKIP_TAGS):    # 遍历 DOM
```

两个解析器都重度依赖 **lxml (C 扩展)** 做同步 XML/HTML 解析。在 `asyncio.run()` 的事件循环线程中执行这些同步 C 扩展调用会**长时间阻塞事件循环**，Celery Worker 无法处理其他任务。

对比 CSV/XML 解析器（纯 Python 字符串处理，毫秒级完成），PPTX/HTML 的 lxml C 扩展调用在 Windows + solo pool 下可能触发死锁或极慢。

### 因子 3：solo pool + 无解析超时

`--pool=solo` 单线程串行。如果 PPTX 任务阻塞，**队列里所有后续任务全部排队等待**。

Celery 配置的 `task_soft_time_limit=600`（10 分钟），但解析器没有内部超时机制。即使 `python-pptx`/`lxml` 内部卡住，也要等 10 分钟才会被 Celery 强制终止。

---

## 验证方法

本地运行，上传一个 PPTX 文件，观察 Celery 日志：

```bash
celery -A tasks.celery_app worker --loglevel=info --pool=solo
```

预期看到：`开始解析: parser=pptx` 后长时间无后续日志。

---

## 修复建议

### P0-1：parse task 同步修复

```python
# tasks/parse.py
from tasks.embed import _run_async_safe

@celery_app.task(...)
def parse_document(self, doc_id: str):
    try:
        return _run_async_safe(_async_parse(doc_id))
    except Exception as exc:
        raise self.retry(exc=exc)
```

### P0-2：所有同步解析器用线程池跑

PPTX / HTML / OCR / JSON 解析器的 `async def parse()` 全是同步代码。统一改为线程池执行：

```python
# engine/parser/pptx.py
import concurrent.futures

async def parse(self, file_path, original_filename):
    loop = asyncio.get_running_loop()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return await loop.run_in_executor(pool, self._parse_sync, file_path, original_filename)

def _parse_sync(self, file_path, original_filename):
    # 原来的同步解析逻辑
    prs = Presentation(file_path)
    ...
```

**HTML / JSON / OCR 同理**。

### P0-3：OCR 解析器前置检测，跳过无效链路

```python
def _lazy_load_ocr(self):
    # ... existing import attempts ...
    
    if self._ocr_type == "tesseract":
        import shutil
        if not shutil.which("tesseract"):
            self._ocr_type = None  # Tesseract 未安装，直接标记不可用
            return
    
    if self._ocr_type is None:
        # 两者都不可用，后续 parse() 直接 return []
```

### P1：Windows 本地使用 `--pool=threads`

```bash
celery -A tasks.celery_app worker --loglevel=info --pool=threads --concurrency=2
```

### P2：解析器加超时

```python
chunks = await asyncio.wait_for(parser.parse(...), timeout=120)
```
