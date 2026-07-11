"""CSV / JSON 解析器 — 结构化数据扁平化为文本"""

import csv
import io
import json as _json
from typing import List

from engine.parser.base import BaseParser, Chunk


class CSVParser(BaseParser):
    name = "csv"
    supported_extensions = [".csv"]
    supported_mime_types = ["text/csv", "application/csv"]

    async def parse(self, file_path: str, original_filename: str) -> List[Chunk]:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            rows = list(reader)

        if not rows:
            return []

        # 转为 Markdown 表格
        lines = []
        header = rows[0]
        lines.append("| " + " | ".join(str(c) for c in header) + " |")
        lines.append("|" + "|".join("---" for _ in header) + "|")

        for row in rows[1:501]:  # 最多 500 行
            cells = [str(c) for c in row]
            # 补齐列数
            while len(cells) < len(header):
                cells.append("")
            lines.append("| " + " | ".join(cells[:len(header)]) + " |")

        if len(rows) > 501:
            lines.append(f"\n*（共 {len(rows)} 行，已截断）*")

        content = "\n".join(lines)
        return [Chunk(
            content=content,
            metadata={
                "source": original_filename,
                "parser_name": self.name,
                "chunk_index": 0,
                "row_count": len(rows),
            },
            chunk_type="table",
        )]


class JSONParser(BaseParser):
    name = "json"
    supported_extensions = [".json"]
    supported_mime_types = ["application/json"]

    async def parse(self, file_path: str, original_filename: str) -> List[Chunk]:
        """JSON 解析 — 大文件递归扁平化可能较慢，用线程池隔离"""
        return await self._run_sync_in_thread(self._parse_sync, file_path, original_filename)

    def _parse_sync(self, file_path: str, original_filename: str) -> List[Chunk]:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            data = _json.load(f)

        # 递归扁平化为文本
        text = self._flatten_json(data)

        if not text.strip():
            return []

        return [Chunk(
            content=text,
            metadata={
                "source": original_filename,
                "parser_name": self.name,
                "chunk_index": 0,
            },
            chunk_type="text",
        )]

    def _flatten_json(self, data, prefix: str = "", depth: int = 0) -> str:
        """递归扁平化 JSON 为键值对格式"""
        if depth > 10:
            return str(data)

        lines = []
        if isinstance(data, dict):
            for key, value in data.items():
                path = f"{prefix}.{key}" if prefix else key
                if isinstance(value, (dict, list)):
                    lines.append(f"{path}:")
                    lines.append(self._flatten_json(value, path, depth + 1))
                else:
                    lines.append(f"  {path}: {value}")
        elif isinstance(data, list):
            for i, item in enumerate(data):
                path = f"{prefix}[{i}]"
                if isinstance(item, (dict, list)):
                    lines.append(f"{path}:")
                    lines.append(self._flatten_json(item, path, depth + 1))
                else:
                    lines.append(f"  {path}: {item}")
        else:
            return f"  {prefix}: {data}"

        return "\n".join(lines)
