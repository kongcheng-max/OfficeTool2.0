"""解析器注册（已废弃）

⚠️ 解析器注册已迁移到 engine/parser/__init__.py，在包导入时自动完成。
ParserRegistry.register() 是幂等的，重复调用不会产生副作用。

此文件保留仅为向后兼容，请勿新增调用 register_all_parsers()。
"""

from loguru import logger

from engine.parser.base import ParserRegistry
from engine.parser.pdf import PDFParser
from engine.parser.docx import DOCXParser
from engine.parser.xlsx import XLSXParser
from engine.parser.text import TextParser, MarkdownParser


def register_all_parsers():
    """[已废弃] 注册所有解析器到 ParserRegistry

    解析器已在 engine/parser 包导入时自动注册。
    此函数仍可安全调用（ParserRegistry.register 是幂等的），但不再必要。
    """
    logger.debug("register_all_parsers() 被调用，但解析器已自动注册（幂等，跳过重复项）")
    ParserRegistry.register(PDFParser())
    ParserRegistry.register(DOCXParser())
    ParserRegistry.register(XLSXParser())
    ParserRegistry.register(TextParser())
    ParserRegistry.register(MarkdownParser())
