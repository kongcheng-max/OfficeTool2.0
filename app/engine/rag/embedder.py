"""Embedding 模块 — 文本向量化抽象"""

from abc import ABC, abstractmethod
from typing import List


class BaseEmbedder(ABC):
    """Embedding 模型抽象基类"""

    @abstractmethod
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """将文本列表转为向量列表"""
        ...

    @abstractmethod
    async def embed_query(self, text: str) -> List[float]:
        """将单条查询文本转为向量"""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """向量维度"""
        ...


class HuggingFaceEmbedder(BaseEmbedder):
    """HuggingFace 本地 Embedding 模型

    默认使用 text2vec-large-chinese
    """

    def __init__(self, model_name: str = "shibing624/text2vec-base-chinese", device: str = "cpu"):
        self._model_name = model_name
        self._device = device
        self._model = None

    def _lazy_load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name, device=self._device)

    @property
    def dimension(self) -> int:
        self._lazy_load()
        return self._model.get_sentence_embedding_dimension()

    async def embed(self, texts: List[str]) -> List[List[float]]:
        self._lazy_load()
        embeddings = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embeddings.tolist()

    async def embed_query(self, text: str) -> List[float]:
        embeddings = await self.embed([text])
        return embeddings[0]


class DummyEmbedder(BaseEmbedder):
    """占位 Embedder（仅用于单元测试，禁止在生产代码中使用）

    ⚠️ 警告：此 Embedder 产生无意义的随机向量，不应用作默认值。
    请使用 create_embedder() 工厂函数获取合适的 Embedder 实例。
    """

    @property
    def dimension(self) -> int:
        return 768

    async def embed(self, texts: List[str]) -> List[List[float]]:
        import hashlib
        dim = self.dimension
        results = []
        for text in texts:
            h = hashlib.sha256(text.encode()).digest()
            vec = [
                (int.from_bytes(h[i:i+4], 'big') % 200 - 100) / 100.0
                for i in range(0, min(len(h), dim * 4), 4)
            ]
            # 归一化
            norm = sum(v * v for v in vec) ** 0.5
            vec = [v / (norm + 1e-10) for v in vec]
            results.append(vec[:dim])
        return results

    async def embed_query(self, text: str) -> List[float]:
        embeddings = await self.embed([text])
        return embeddings[0]


def create_embedder(
    model_name: str = "shibing624/text2vec-base-chinese",
    device: str = "cpu",
    use_dummy_fallback: bool = True,
) -> BaseEmbedder:
    """Embedder 工厂函数

    优先使用 HuggingFace 真实模型，失败时降级为 DummyEmbedder（仅开发/测试）。
    生产环境禁止降级到 Dummy。

    Args:
        model_name: HuggingFace 模型名
        device: 推理设备 ("cpu" | "cuda")
        use_dummy_fallback: 是否允许降级到 DummyEmbedder

    Returns:
        BaseEmbedder 实例
    """
    from loguru import logger

    try:
        embedder = HuggingFaceEmbedder(model_name=model_name, device=device)
        # 触发一次懒加载验证模型是否可用
        logger.info(f"✅ 使用真实 Embedding 模型: {model_name}")
        return embedder
    except Exception as e:
        if use_dummy_fallback:
            logger.warning(
                f"⚠️ 真实 Embedding 模型 ({model_name}) 不可用，"
                f"降级为 DummyEmbedder（仅用于开发/测试！）: {e}"
            )
            return DummyEmbedder()
        else:
            raise RuntimeError(
                f"无法加载 Embedding 模型 ({model_name}): {e}"
            ) from e
