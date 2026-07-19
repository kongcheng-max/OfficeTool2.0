import pytest

from engine.rag.embedder import DummyEmbedder, HuggingFaceEmbedder, create_embedder


@pytest.mark.asyncio
async def test_dummy_embedder_returns_full_dimension_vectors():
    embedder = DummyEmbedder()

    vectors = await embedder.embed(["hello", "world"])

    assert len(vectors) == 2
    assert all(len(vector) == embedder.dimension for vector in vectors)


def test_create_embedder_falls_back_when_model_cannot_load(monkeypatch):
    def fail_lazy_load(self):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(HuggingFaceEmbedder, "_lazy_load", fail_lazy_load)

    embedder = create_embedder(use_dummy_fallback=True)

    assert isinstance(embedder, DummyEmbedder)
