"""解析引擎核心 — BaseParser 抽象类 + Chunk 数据结构 + ParserRegistry"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class Chunk:
    """统一的文档块输出格式

    所有解析器输出此结构，供下游 RAG 管道消费。
    """
    content: str  # 文本内容（供 Embedding 使用）
    metadata: dict  # {source, page, section, sheet, slide, is_table, chunk_index, parser_name, ...}
    chunk_type: str = "text"  # "text" | "table" | "image_caption"

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "metadata": self.metadata,
            "chunk_type": self.chunk_type,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Chunk":
        return cls(
            content=data["content"],
            metadata=data.get("metadata", {}),
            chunk_type=data.get("chunk_type", "text"),
        )


class BaseParser(ABC):
    """所有文档解析器的抽象基类

    新增格式只需：继承 → 实现 parse() → 注册到 ParserRegistry
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """解析器名称，如 'pdf', 'docx'"""
        ...

    @property
    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """支持的文件扩展名，如 ['.pdf']"""
        ...

    @property
    @abstractmethod
    def supported_mime_types(self) -> List[str]:
        """支持的 MIME 类型，如 ['application/pdf']"""
        ...

    @abstractmethod
    async def parse(self, file_path: str, original_filename: str) -> List[Chunk]:
        """解析文档，返回统一 Chunk 列表

        Args:
            file_path: 本地临时文件路径
            original_filename: 原始文件名（用于 metadata.source）

        Returns:
            解析后的 Chunk 列表
        """
        ...

    def supports(self, filename: str, mime_type: Optional[str] = None) -> bool:
        """判断是否能处理该文件"""
        ext = Path(filename).suffix.lower()
        if ext in self.supported_extensions:
            return True
        if mime_type and mime_type in self.supported_mime_types:
            return True
        return False


class ParserRegistry:
    """解析器注册中心（单例模式）

    启动时注册所有解析器，运行时按扩展名/MIME 匹配。
    """

    _parsers: List[BaseParser] = []

    @classmethod
    def register(cls, parser: BaseParser):
        """注册一个解析器（幂等：同名解析器只注册一次）"""
        # 检查是否已注册同名解析器
        for existing in cls._parsers:
            if existing.name == parser.name:
                return  # 已注册，跳过
        cls._parsers.append(parser)

    @classmethod
    def find_for(cls, filename: str, mime_type: Optional[str] = None) -> Optional[BaseParser]:
        """根据文件名/MIME 查找匹配的解析器"""
        for p in cls._parsers:
            if p.supports(filename, mime_type):
                return p
        return None

    @classmethod
    def get_all(cls) -> List[BaseParser]:
        """获取所有已注册解析器"""
        return cls._parsers
