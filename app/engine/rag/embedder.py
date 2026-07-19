"""Embedding abstraction and factory."""

from abc import ABC, abstractmethod
from typing import List


class BaseEmbedder(ABC):
    """Base interface for text embedding models."""

    @abstractmethod
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of texts."""
        ...

    @abstractmethod
    async def embed_query(self, text: str) -> List[float]:
        """Embed one query string."""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Embedding vector dimension."""
        ...


class HuggingFaceEmbedder(BaseEmbedder):
    """Local HuggingFace embedding model wrapper."""

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
    """Deterministic fallback embedder for development and degraded indexing."""

    @property
    def dimension(self) -> int:
        return 768

    async def embed(self, texts: List[str]) -> List[List[float]]:
        import hashlib

        dim = self.dimension
        results = []
        for text in texts:
            vec = []
            seed = text.encode()
            counter = 0
            while len(vec) < dim:
                h = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
                vec.extend(
                    (int.from_bytes(h[i:i + 4], "big") % 200 - 100) / 100.0
                    for i in range(0, len(h), 4)
                )
                counter += 1

            vec = vec[:dim]
            norm = sum(v * v for v in vec) ** 0.5
            vec = [v / (norm + 1e-10) for v in vec]
            results.append(vec)
        return results

    async def embed_query(self, text: str) -> List[float]:
        embeddings = await self.embed([text])
        return embeddings[0]


def create_embedder(
    model_name: str = "shibing624/text2vec-base-chinese",
    device: str = "cpu",
    use_dummy_fallback: bool = True,
) -> BaseEmbedder:
    """Create an embedder and optionally fall back when the real model is unavailable."""
    from loguru import logger

    try:
        embedder = HuggingFaceEmbedder(model_name=model_name, device=device)
        _ = embedder.dimension
        logger.info(f"Using real embedding model: {model_name}")
        return embedder
    except Exception as e:
        if use_dummy_fallback:
            logger.warning(
                f"Embedding model ({model_name}) is unavailable; falling back to DummyEmbedder: {e}"
            )
            return DummyEmbedder()
        raise RuntimeError(f"Cannot load embedding model ({model_name}): {e}") from e
