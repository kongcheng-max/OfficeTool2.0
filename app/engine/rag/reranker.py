"""RRF 融合排序 & Cross-encoder 精排 — AI 算法主责

接口约定:
  rrf_fusion(result_lists, k=60) → List[Dict]
    输入: 多路检索结果列表 [[{doc_id, chunk_text, score, source, metadata}, ...], ...]
    输出: RRF 融合+去重后的单列表，每条含 rrf_score + sources[] 来源标记

  cross_encoder_rerank(query, hits, top_k=5) → List[Dict]
    输入: 查询文本 + RRF 融合后的 hits 列表
    输出: rerank_score 精排后的 Top-K

BE 调用入口:
  from engine.rag.reranker import rrf_fusion, cross_encoder_rerank
"""

import hashlib
from typing import Dict, List

from loguru import logger


def rrf_fusion(
    result_lists: List[List[Dict]],
    k: int = 60,
) -> List[Dict]:
    """RRF (Reciprocal Rank Fusion) 融合多路检索结果

    算法:
      RRF_score(d) = Σ_{r ∈ R} 1 / (k + rank_r(d))
      其中 R 是所有检索通路集合, rank_r(d) 是文档 d 在通路 r 中的排名(1-based)

    Args:
        result_lists: 多路检索结果 [通路1结果, 通路2结果, ...]
                      每条结果需含 doc_id, chunk_text, score, source, metadata
        k: 平滑参数 (IEEE 推荐 60)

    Returns:
        按 RRF 分降序排列的结果列表，每条额外包含:
        - rrf_score: RRF 聚合分
        - sources: 命中的检索通路列表 ["vector", "bm25", "kg"]
    """
    scores: Dict[str, float] = {}
    chunks: Dict[str, Dict] = {}

    for hits in result_lists:
        if not hits:
            continue
        for rank, hit in enumerate(hits, 1):
            doc_id = hit.get("doc_id", "")
            chunk_text = hit.get("chunk_text", "")
            # BUG-064 P3: 用 MD5 做唯一 key，避免前 100 字符相同导致误合并
            text_hash = hashlib.md5(
                (chunk_text or "").encode("utf-8"), usedforsecurity=False
            ).hexdigest()[:16]
            key = f"{doc_id}|{text_hash}"

            rrf_score = 1.0 / (k + rank)
            scores[key] = scores.get(key, 0.0) + rrf_score

            if key not in chunks:
                chunks[key] = {**hit}
                chunks[key]["sources"] = [hit.get("source", "unknown")]
            else:
                existing = chunks[key].get("sources", [])
                src = hit.get("source", "unknown")
                if src not in existing:
                    existing.append(src)
                chunks[key]["sources"] = existing

    # 按 RRF 分数降序
    sorted_keys = sorted(scores, key=lambda x: scores[x], reverse=True)

    result = []
    for key in sorted_keys:
        item = chunks[key]
        item["rrf_score"] = round(scores[key], 6)
        result.append(item)

    return result


# W9.5: bge-reranker-large 懒加载
_reranker_model = None
_RERANKER_AVAILABLE = None  # None=未检测, True=可用, False=不可用


def _get_cross_encoder():
    """懒加载 bge-reranker-large — 首次调用时加载，后续复用"""
    global _reranker_model, _RERANKER_AVAILABLE
    if _RERANKER_AVAILABLE is None:
        try:
            from FlagEmbedding import FlagReranker
            _reranker_model = FlagReranker(
                'BAAI/bge-reranker-v2-m3',
                use_fp16=True,
                devices=["cpu"],  # 默认 CPU，GPU 可将 devices 改为 "cuda"
            )
            _RERANKER_AVAILABLE = True
            logger.info("Cross-encoder: bge-reranker-v2-m3 已就绪")
        except ImportError:
            logger.info("Cross-encoder: FlagEmbedding 未安装，降级为 bi-encoder")
            _RERANKER_AVAILABLE = False
        except Exception as e:
            logger.warning(f"Cross-encoder: 模型加载失败 ({e})，降级为 bi-encoder")
            _RERANKER_AVAILABLE = False
    return _reranker_model if _RERANKER_AVAILABLE else None


async def cross_encoder_rerank(
    query: str,
    hits: List[Dict],
    top_k: int = 5,
) -> List[Dict]:
    """Cross-encoder 语义精排 (Phase 3 W9.5)

    优先使用 bge-reranker-v2-m3（真正的 Cross-encoder），
    不可用时降级为 bi-encoder 余弦相似度重排序。

    bge-reranker-v2-m3 优势:
    - 同时编码 query + document 对，捕捉交互语义
    - 对 "微服务" vs "白鹿原" 这类语义区分能力远强于 bi-encoder
    - 支持多语言（中英文混合）

    Args:
        query: 用户查询文本
        hits: RRF 融合后的候选列表
        top_k: 精排后返回数量

    Returns:
        按 rerank_score 排序的 Top-K 列表
    """
    if not hits:
        return []

    reranker = _get_cross_encoder()

    if reranker is not None:
        # ── bge-reranker 真 Cross-encoder 路径 ──
        try:
            pairs = [[query, h.get("chunk_text", "")] for h in hits]
            scores = reranker.compute_score(pairs)

            for i, hit in enumerate(hits):
                score = float(scores[i]) if isinstance(scores, list) else float(scores)
                rrf = hit.get("rrf_score", 0)
                # Cross-encoder 为主导（权重 0.8），RRF 为辅助
                hit["rerank_score"] = round(score * 0.8 + rrf * 0.2, 4)
                hit["_ce_score"] = round(score, 4)

            logger.info(
                f"Cross-encoder (bge-reranker) 精排完成: "
                f"top_score={max(h.get('rerank_score', 0) for h in hits)}"
            )
        except Exception as e:
            logger.warning(f"bge-reranker 精排失败: {e}，降级为 bi-encoder")
            await _bi_encoder_rerank(query, hits)
    else:
        await _bi_encoder_rerank(query, hits)

    sorted_hits = sorted(hits, key=lambda h: h.get("rerank_score", 0), reverse=True)
    return sorted_hits[:top_k]


async def _bi_encoder_rerank(query: str, hits: List[Dict]) -> None:
    """Bi-encoder 重排序（降级方案）"""
    try:
        from engine.rag.embedder import create_embedder

        embedder = create_embedder(use_dummy_fallback=True)
        query_vec = await embedder.embed_query(query)
        texts = [h.get("chunk_text", "") for h in hits]
        chunk_vecs = await embedder.embed(texts)

        import math
        for i, hit in enumerate(hits):
            qv = query_vec
            cv = chunk_vecs[i]
            dot = sum(a * b for a, b in zip(qv, cv))
            q_norm = math.sqrt(sum(a * a for a in qv))
            c_norm = math.sqrt(sum(b * b for b in cv))
            cosine_sim = dot / (q_norm * c_norm) if q_norm > 0 and c_norm > 0 else 0.0
            rrf = hit.get("rrf_score", 0)
            hit["rerank_score"] = round(cosine_sim * 0.7 + rrf * 0.3, 4)
            hit["_cosine_sim"] = round(cosine_sim, 4)

        logger.info(
            f"Cross-encoder (bi-encoder) 精排完成: "
            f"top_score={max(h.get('rerank_score', 0) for h in hits)}"
        )
    except Exception as e:
        logger.warning(f"Bi-encoder 精排也失败: {e}，使用 RRF 裸分")
        for hit in hits:
            rrf = hit.get("rrf_score", 0)
            orig = hit.get("score", 0)
            hit["rerank_score"] = round(rrf * 0.6 + orig * 0.4, 4)
