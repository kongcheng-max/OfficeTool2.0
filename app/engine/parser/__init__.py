"""解析引擎 — 自动注册所有解析器"""

from engine.parser.base import BaseParser, Chunk, ParserRegistry
from engine.parser.pdf import PDFParser
from engine.parser.docx import DOCXParser
from engine.parser.xlsx import XLSXParser
from engine.parser.text import TextParser, MarkdownParser

# 模块加载时自动注册
ParserRegistry.register(PDFParser())
ParserRegistry.register(DOCXParser())
ParserRegistry.register(XLSXParser())
ParserRegistry.register(TextParser())
ParserRegistry.register(MarkdownParser())
