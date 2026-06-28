"""解析器注册表测试"""
import engine.parser  # noqa: F401 — 触发解析器自动注册
from engine.parser.base import ParserRegistry


def test_parser_registry_find_for_md():
    """.md 文件匹配 MarkdownParser"""
    parser = ParserRegistry.find_for("test.md")
    assert parser is not None


def test_parser_registry_find_for_pdf():
    """.pdf 文件匹配 PDFParser"""
    parser = ParserRegistry.find_for("test.pdf")
    assert parser is not None


def test_parser_registry_find_for_unknown():
    """未知扩展名返回 None"""
    parser = ParserRegistry.find_for("test.xyz")
    assert parser is None


def test_parser_registry_get_all():
    """至少注册了 5 个解析器"""
    parsers = ParserRegistry.get_all()
    assert len(parsers) >= 5
