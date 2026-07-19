import pytest

from services import qa_service
from engine.rag.embedder import DummyEmbedder
from engine.rag import reranker
from engine.rag.retriever import Retriever


class _FakeHybridRetriever:
    async def retrieve(self, question, kb_id, top_k=10, use_kg=True):
        return {
            "hits": [
                {
                    "doc_id": "html-doc",
                    "chunk_text": "增肌要点包括循序渐进、热量盈余、蛋白质充足、充足睡眠。",
                    "metadata": {"source": "index.html"},
                    "rrf_score": 0.03,
                    "sources": ["bm25"],
                }
            ],
            "total_sources": {"vector": 0, "bm25": 1, "kg": 0},
        }


class _FakeBM25Retriever:
    async def retrieve(self, query, kb_id=None, top_k=10):
        return [
            {
                "doc_id": "noise-doc",
                "chunk_text": "无关但 BM25 原始分很高的片段",
                "metadata": {"source": "noise.txt"},
                "score": 12.5,
                "source": "bm25",
            }
        ]


class _FakeVectorStore:
    def __init__(self):
        self.called = False

    def search(self, query_vector, kb_id=None, top_k=10):
        self.called = True
        return [
            {
                "doc_id": "noise-doc",
                "chunk_text": "untrusted dummy vector hit",
                "metadata_json": "{}",
                "score": 0.99,
            }
        ]


@pytest.mark.asyncio
async def test_vector_retriever_skips_search_when_embedder_is_dummy():
    store = _FakeVectorStore()

    hits = await Retriever(DummyEmbedder(), store).retrieve("html recall query", kb_id="kb-1", top_k=5)

    assert hits == []
    assert store.called is False


@pytest.mark.asyncio
async def test_retrieve_does_not_treat_variant_bm25_score_as_rrf(monkeypatch):
    captured_hits = []

    async def fake_rewrite(question, max_variants=2):
        return [question, "改写后的问题"]

    async def fake_rerank(question, hits, top_k=10):
        captured_hits.extend(hits)
        return hits[:top_k]

    monkeypatch.setattr(qa_service, "_get_hybrid_retriever", lambda: _FakeHybridRetriever())
    monkeypatch.setattr("engine.rag.query_rewriter.query_rewriter.rewrite", fake_rewrite)
    monkeypatch.setattr("engine.rag.retriever.BM25Retriever", _FakeBM25Retriever)
    monkeypatch.setattr("engine.rag.reranker.cross_encoder_rerank", fake_rerank)

    await qa_service._retrieve("增肌要点包括哪四项？", "kb-1", top_k=10, use_kg=True)

    variant_hit = next(hit for hit in captured_hits if hit["doc_id"] == "noise-doc")
    assert variant_hit["rrf_score"] < 1


@pytest.mark.asyncio
async def test_rerank_keeps_rrf_order_when_only_dummy_embedder_is_available(monkeypatch):
    monkeypatch.setattr(reranker, "_get_cross_encoder", lambda: None)
    monkeypatch.setattr("engine.rag.embedder.create_embedder", lambda use_dummy_fallback=True: DummyEmbedder())

    hits = [
        {"doc_id": "html-doc", "chunk_text": "增肌要点包括循序渐进、热量盈余、蛋白质充足、充足睡眠。", "rrf_score": 0.03},
        {"doc_id": "noise-doc", "chunk_text": "白嘉轩和族规的无关片段", "rrf_score": 0.02},
    ]

    result = await reranker.cross_encoder_rerank("增肌要点包括哪四项？", hits, top_k=2)

    assert [hit["doc_id"] for hit in result] == ["html-doc", "noise-doc"]
    assert "_cosine_sim" not in result[0]
