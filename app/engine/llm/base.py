"""LLM 网关抽象基类"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Dict, List, Optional


@dataclass
class Message:
    """对话消息"""
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class ChatResponse:
    """LLM 响应"""
    content: str
    usage: dict = field(default_factory=dict)  # {prompt_tokens, completion_tokens}


class BaseLLM(ABC):
    """LLM 抽象基类

    支持通义千问、DeepSeek 等通过统一接口接入。
    """

    @abstractmethod
    async def chat(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> ChatResponse:
        """非流式对话"""
        ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        """流式对话，逐 token 返回"""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """模型名称"""
        ...
