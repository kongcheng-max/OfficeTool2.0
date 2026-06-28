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

from typing import Dict, List


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
            text_snippet = hit.get("chunk_text", "")[:100]
            key = f"{doc_id}|{text_snippet}"

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


async def cross_encoder_rerank(
    query: str,
    hits: List[Dict],
    top_k: int = 5,
) -> List[Dict]:
    """Cross-encoder 精排（Phase 3 完整实现）

    当前版本: 基于已有分数排序返回 Top-K（占位）
    Phase 3 将集成 bge-reranker-large 做真正的 Cross-encoder 重排序。

    Args:
        query: 用户查询文本
        hits: RRF 融合后的候选列表
        top_k: 精排后返回数量

    Returns:
        按 rerank_score 排序的 Top-K 列表
    """
    # TODO Phase 3: 集成 bge-reranker-large
    # from FlagEmbedding import FlagReranker
    # reranker = FlagReranker('BAAI/bge-reranker-large', use_fp16=True)
    # pairs = [[query, hit['chunk_text']] for hit in hits]
    # scores = reranker.compute_score(pairs)
    # for hit, score in zip(hits, scores):
    #     hit['rerank_score'] = round(float(score), 4)

    # 当前降级: 按 RRF 分 + 原始分加权排序
    for hit in hits:
        rrf = hit.get("rrf_score", 0)
        orig = hit.get("score", 0)
        hit["rerank_score"] = round(rrf * 0.6 + orig * 0.4, 4)

    sorted_hits = sorted(hits, key=lambda h: h.get("rerank_score", 0), reverse=True)
    return sorted_hits[:top_k]
