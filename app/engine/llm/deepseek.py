"""DeepSeek LLM 适配器"""

import json
from typing import AsyncIterator, List, Optional

import httpx
from loguru import logger

from core.config import settings
from engine.llm.base import BaseLLM, ChatResponse, Message


class DeepSeekLLM(BaseLLM):
    """DeepSeek API 适配器"""

    BASE_URL = "https://api.deepseek.com/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self._api_key = api_key or settings.LLM_DEEPSEEK_API_KEY
        self._model = model or settings.LLM_DEEPSEEK_MODEL
        # W9.8: 连接池配置支持 50 QPS 并发
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
        )

    @property
    def model_name(self) -> str:
        return self._model

    async def chat(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> ChatResponse:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            resp = await self._client.post(
                f"{self.BASE_URL}/chat/completions",
                headers=headers,
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]
            return ChatResponse(
                content=choice["message"]["content"],
                usage=data.get("usage", {}),
            )
        except Exception as e:
            logger.error(f"DeepSeek 调用失败: {e}")
            raise

    async def chat_stream(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        try:
            async with self._client.stream(
                "POST",
                f"{self.BASE_URL}/chat/completions",
                headers=headers,
                json=body,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except (json.JSONDecodeError, KeyError):
                            continue
        except Exception as e:
            logger.error(f"DeepSeek 流式调用失败: {e}")
            raise
