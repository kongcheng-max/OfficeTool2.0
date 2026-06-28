"""解析引擎 — 自动注册所有解析器（懒加载，缺失依赖不阻断启动）"""

import logging
from engine.parser.base import BaseParser, Chunk, ParserRegistry

_log = logging.getLogger(__name__)


def _safe_register(module_path: str, class_name: str):
    """安全导入并注册解析器，依赖缺失时仅 warning"""
    try:
        import importlib
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        ParserRegistry.register(cls())
    except ImportError as e:
        _log.warning(f"解析器 {class_name} 不可用（缺少依赖）: {e}")
    except Exception as e:
        _log.error(f"解析器 {class_name} 注册失败: {e}")


# Phase 1 解析器（核心依赖，应始终可用）
_safe_register("engine.parser.pdf", "PDFParser")
_safe_register("engine.parser.docx", "DOCXParser")
_safe_register("engine.parser.xlsx", "XLSXParser")
_safe_register("engine.parser.text", "TextParser")
_safe_register("engine.parser.text", "MarkdownParser")

# Phase 2 解析器（可选依赖）
_safe_register("engine.parser.pptx", "PPTXParser")
_safe_register("engine.parser.csv_json", "CSVParser")
_safe_register("engine.parser.csv_json", "JSONParser")
_safe_register("engine.parser.html_xml", "HTMLParser")
_safe_register("engine.parser.html_xml", "XMLParser")
# OCR requires `pip install officetool-backend[ocr]` or `pip install paddleocr pytesseract`
_safe_register("engine.parser.ocr", "OCRParser")
