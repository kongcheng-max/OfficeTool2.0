"""LLM 工厂 — 根据配置创建对应 LLM 实例"""

from loguru import logger

from core.config import settings
from engine.llm.base import BaseLLM, Message


class LLMFactory:
    """LLM 工厂：按配置选择 LLM 提供商"""

    _instances = {}

    @classmethod
    def create(cls) -> BaseLLM:
        """根据 settings.LLM_PROVIDER 创建 LLM 实例（带缓存）"""
        provider = settings.LLM_PROVIDER

        if provider in cls._instances:
            return cls._instances[provider]

        if provider == "tongyi":
            from engine.llm.tongyi import TongyiLLM
            llm = TongyiLLM()
        elif provider == "deepseek":
            from engine.llm.deepseek import DeepSeekLLM
            llm = DeepSeekLLM()
        else:
            raise ValueError(f"不支持的 LLM 提供商: {provider}")

        cls._instances[provider] = llm
        logger.info(f"LLM 已初始化: {provider} ({llm.model_name})")
        return llm

    @classmethod
    async def generate_with_fallback(
        cls,
        messages: list,
        temperature: float = 0.7,
    ) -> str:
        """带故障切换的 LLM 生成

        主 LLM 不可用时自动切换到备用 LLM。
        """
        primary = settings.LLM_PROVIDER
        fallback_order = ["tongyi", "deepseek"]

        # 把主 provider 放在最前面
        if primary in fallback_order:
            fallback_order.remove(primary)
        providers = [primary] + fallback_order

        last_error = None
        for provider in providers:
            try:
                llm = cls._create_by_name(provider)
                msgs = [Message(role=m["role"], content=m["content"]) for m in messages]
                resp = await llm.chat(msgs, temperature=temperature)
                return resp.content
            except Exception as e:
                logger.warning(f"LLM ({provider}) 调用失败: {e}")
                last_error = e
                continue

        raise last_error or RuntimeError("所有 LLM 提供商均不可用")

    @classmethod
    def _create_by_name(cls, name: str) -> BaseLLM:
        if name in cls._instances:
            return cls._instances[name]
        if name == "tongyi":
            from engine.llm.tongyi import TongyiLLM
            return TongyiLLM()
        elif name == "deepseek":
            from engine.llm.deepseek import DeepSeekLLM
            return DeepSeekLLM()
        raise ValueError(f"不支持的 LLM: {name}")
