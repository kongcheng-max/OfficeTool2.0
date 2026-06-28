"""文本类解析器 — TXT / Markdown"""

from pathlib import Path
from typing import List

from engine.parser.base import BaseParser, Chunk


class TextParser(BaseParser):
    """TXT 纯文本解析器"""
    name = "txt"
    supported_extensions = [".txt", ".text"]
    supported_mime_types = ["text/plain"]

    async def parse(self, file_path: str, original_filename: str) -> List[Chunk]:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        if not content.strip():
            return []

        # Split by double newlines to preserve paragraph structure
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        if len(paragraphs) <= 1:
            return [Chunk(
                content=content,
                metadata={
                    "source": original_filename,
                    "parser_name": self.name,
                    "chunk_index": 0,
                },
                chunk_type="text",
            )]

        chunks = []
        for i, para in enumerate(paragraphs):
            chunks.append(Chunk(
                content=para,
                metadata={
                    "source": original_filename,
                    "parser_name": self.name,
                    "chunk_index": i,
                    "section": f"段落{i + 1}",
                },
                chunk_type="text",
            ))
        return chunks


class MarkdownParser(BaseParser):
    """Markdown 解析器 — 保留 Markdown 格式标记"""
    name = "markdown"
    supported_extensions = [".md", ".markdown", ".mdown"]
    supported_mime_types = ["text/markdown", "text/x-markdown"]

    async def parse(self, file_path: str, original_filename: str) -> List[Chunk]:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        if not content.strip():
            return []

        # 按 ## 标题分段
        chunks = self._split_by_heading(content, original_filename)

        if not chunks:
            chunks = [Chunk(
                content=content,
                metadata={
                    "source": original_filename,
                    "parser_name": self.name,
                    "chunk_index": 0,
                },
                chunk_type="text",
            )]

        return chunks

    def _split_by_heading(self, content: str, filename: str) -> List[Chunk]:
        """按 ## 标题切分段落"""
        import re
        # 匹配 Markdown 标题（# ~ ######）
        sections = re.split(r'\n(?=#{1,6}\s)', content)
        if len(sections) <= 1:
            return []

        chunks = []
        for i, section in enumerate(sections):
            if section.strip():
                # 提取标题作为 section 名
                heading_match = re.match(r'(#{1,6})\s+(.+)', section)
                section_name = heading_match.group(2).strip() if heading_match else "正文"
                chunks.append(Chunk(
                    content=section.strip(),
                    metadata={
                        "section": section_name,
                        "source": filename,
                        "parser_name": self.name,
                        "chunk_index": i,
                    },
                    chunk_type="text",
                ))
        return chunks
