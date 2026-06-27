"""文本分块器 — 基于 LangChain RecursiveCharacterTextSplitter"""

from typing import List

from langchain_text_splitters import RecursiveCharacterTextSplitter


class TextSplitter:
    """中文语义分块器

    使用 LangChain 的递归字符分割器，支持中文标点优先切分。
    """

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        self.separators = [
            "\n\n",   # 段落
            "\n",     # 换行
            "。",     # 中文句号
            "！",     # 感叹号
            "？",     # 问号
            "；",     # 分号
            "，",     # 逗号
            ".",      # 英文句号
            "!",      # 英文感叹号
            "?",      # 英文问号
            ";",      # 英文分号
            " ",      # 空格
            "",       # 最小切分（逐字）
        ]
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=self.separators,
            keep_separator=True,
            is_separator_regex=False,
        )

    def split_text(self, text: str) -> List[str]:
        """将文本切分为块"""
        if not text.strip():
            return []
        return self._splitter.split_text(text)

    def split_documents(self, chunks: list) -> list:
        """批量切分 Chunk 列表

        每个输入 Chunk 可能被切分成多个小块。
        返回包含 content 和 metadata 的 dict 列表。
        """
        result = []
        for chunk in chunks:
            texts = self.split_text(chunk.content)
            for i, text in enumerate(texts):
                meta = {**chunk.metadata}
                meta["chunk_index"] = len(result)
                meta["sub_chunk_index"] = i
                result.append({
                    "content": text,
                    "metadata": meta,
                    "chunk_type": chunk.chunk_type,
                })
        return result


# 默认单例
text_splitter = TextSplitter(chunk_size=500, chunk_overlap=50)
