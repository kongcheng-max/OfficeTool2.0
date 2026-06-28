"""HTML / XML 解析器 — 标签剥离 + 正文提取"""

from typing import List

from bs4 import BeautifulSoup

from engine.parser.base import BaseParser, Chunk


class HTMLParser(BaseParser):
    name = "html"
    supported_extensions = [".html", ".htm"]
    supported_mime_types = ["text/html", "application/xhtml+xml"]

    # 非正文标签
    SKIP_TAGS = {"script", "style", "nav", "footer", "header", "iframe", "noscript"}

    async def parse(self, file_path: str, original_filename: str) -> List[Chunk]:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            html = f.read()

        soup = BeautifulSoup(html, "lxml")

        # 标题
        title = ""
        if soup.title:
            title = soup.title.get_text(strip=True)

        # 移除不需要的标签
        for tag in soup(self.SKIP_TAGS):
            tag.decompose()

        # 提取正文
        body = soup.body if soup.body else soup
        text = body.get_text(separator="\n", strip=True)

        # 精简空行
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        content = "\n".join(lines)

        if title:
            content = f"# {title}\n\n{content}"

        if not content.strip():
            return []

        return [Chunk(
            content=content,
            metadata={
                "source": original_filename,
                "parser_name": self.name,
                "chunk_index": 0,
            },
            chunk_type="text",
        )]


class XMLParser(BaseParser):
    name = "xml"
    supported_extensions = [".xml"]
    supported_mime_types = ["application/xml", "text/xml"]

    async def parse(self, file_path: str, original_filename: str) -> List[Chunk]:
        from lxml import etree

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            xml_text = f.read()

        try:
            tree = etree.fromstring(xml_text.encode("utf-8"))
        except etree.XMLSyntaxError:
            # 尝试作为 HTML 解析
            parser = etree.HTMLParser()
            tree = etree.fromstring(xml_text.encode("utf-8"), parser)

        # 递归提取所有文本节点
        texts = []
        for elem in tree.iter():
            if elem.text and elem.text.strip():
                texts.append(elem.text.strip())
            if elem.tail and elem.tail.strip():
                texts.append(elem.tail.strip())

        content = "\n".join(texts)
        if not content.strip():
            return []

        return [Chunk(
            content=content,
            metadata={
                "source": original_filename,
                "parser_name": self.name,
                "chunk_index": 0,
            },
            chunk_type="text",
        )]
