"""PDF 解析器 — 基于 PyMuPDF"""

from typing import List

import fitz  # PyMuPDF

from engine.parser.base import BaseParser, Chunk


class PDFParser(BaseParser):
    name = "pdf"
    supported_extensions = [".pdf"]
    supported_mime_types = ["application/pdf"]

    async def parse(self, file_path: str, original_filename: str) -> List[Chunk]:
        chunks: List[Chunk] = []
        doc = fitz.open(file_path)

        for page_num, page in enumerate(doc, 1):
            # 提取文字
            text = page.get_text("text")
            if text.strip():
                chunks.append(Chunk(
                    content=text.strip(),
                    metadata={
                        "page": page_num,
                        "source": original_filename,
                        "parser_name": self.name,
                        "chunk_index": len(chunks),
                    },
                    chunk_type="text",
                ))

            # 表格检测与提取
            tables = page.find_tables()
            for tb in tables:
                markdown_table = self._table_to_markdown(tb)
                if markdown_table.strip():
                    chunks.append(Chunk(
                        content=markdown_table,
                        metadata={
                            "page": page_num,
                            "source": original_filename,
                            "is_table": True,
                            "parser_name": self.name,
                            "chunk_index": len(chunks),
                        },
                        chunk_type="table",
                    ))

        doc.close()
        return chunks

    @staticmethod
    def _table_to_markdown(table) -> str:
        """将 PyMuPDF 表格转为 Markdown 格式"""
        try:
            data = table.extract()
            if not data:
                return ""
            lines = []
            # 表头
            header = data[0]
            lines.append("| " + " | ".join(str(c) if c else "" for c in header) + " |")
            lines.append("|" + "|".join("---" for _ in header) + "|")
            # 数据行
            for row in data[1:]:
                lines.append("| " + " | ".join(str(c) if c else "" for c in row) + " |")
            return "\n".join(lines)
        except Exception:
            return str(table)
