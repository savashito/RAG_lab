"""
06_evaluation/metrics.py — the standard retrieval metrics, by hand.

Given, for one query, a RANKED list of candidate ids and the ONE relevant id,
compute:
  * recall@k / hit@k — is the relevant id in the top-k? (binary, single-gold)
  * reciprocal rank  — 1 / (rank of the relevant id)
  * nDCG@k           — for a single relevant id, 1/log2(rank+1) when rank ≤ k

For a whole eval set we average each across queries (MRR = mean reciprocal rank).
Kept deliberately simple and readable — this is the "what does 'better' even
mean" lab.
"""

from __future__ import annotations

import math


def rank_of(ranked: list[str], gold: str) -> int | None:
    """1-based rank of gold in the ranked list, or None if absent."""
    for i, x in enumerate(ranked):
        if x == gold:
            return i + 1
    return None


def hit_at_k(ranked: list[str], gold: str, k: int) -> float:
    r = rank_of(ranked, gold)
    return 1.0 if (r is not None and r <= k) else 0.0


def reciprocal_rank(ranked: list[str], gold: str) -> float:
    r = rank_of(ranked, gold)
    return 1.0 / r if r else 0.0


def ndcg_at_k(ranked: list[str], gold: str, k: int) -> float:
    # single relevant item → ideal DCG is 1 (gold at rank 1); DCG is 1/log2(rank+1)
    r = rank_of(ranked, gold)
    return 1.0 / math.log2(r + 1) if (r is not None and r <= k) else 0.0


def aggregate(rankings: list[tuple[list[str], str]], ks=(1, 3, 5)) -> dict:
    """rankings: list of (ranked_ids, gold). Returns averaged metrics."""
    n = len(rankings)
    out: dict[str, float] = {}
    for k in ks:
        out[f"recall@{k}"] = sum(hit_at_k(r, g, k) for r, g in rankings) / n
    out["mrr"] = sum(reciprocal_rank(r, g) for r, g in rankings) / n
    out[f"ndcg@{max(ks)}"] = sum(ndcg_at_k(r, g, max(ks)) for r, g in rankings) / n
    return out
