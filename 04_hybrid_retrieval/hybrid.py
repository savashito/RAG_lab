"""
Lab 04 — Hybrid Retrieval: BM25 + Dense + RRF.

Three retrievers on the same corpus:
  * BM25   — lexical. Hand-rolled here so the formula from the course notes is
             visible: idf * tf*(k1+1) / (tf + k1*(1 - b + b*dl/avgdl)).
  * Dense  — pgvector cosine search (Labs 01-03).
  * Hybrid — fuse the two ranked lists with Reciprocal Rank Fusion (RRF).

We score exact-token queries and semantic queries separately, because that's
where the story lives: BM25 wins the first group, Dense wins the second, and
Hybrid is strong on both.

Usage (tunnel open):
    uv run python 04_hybrid_retrieval/hybrid.py                # local CPU
    uv run python 04_hybrid_retrieval/hybrid.py --model tei    # GPU
    uv run python 04_hybrid_retrieval/hybrid.py --show         # print per-query rankings
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, ".")
from shared.db import connect
from shared.embedder import get_embedder

from queries import QUERIES  # noqa: E402

CORPUS_DIR = Path(__file__).parent / "corpus"
TABLE = "hybrid_lab"


def load_docs() -> list[tuple[str, str]]:
    return [(p.name, p.read_text().strip()) for p in sorted(CORPUS_DIR.glob("*.md"))]


def tokenize(text: str) -> list[str]:
    # \w keeps underscores/digits, so "err_4521" and "m8x40" stay single tokens.
    return re.findall(r"[a-z0-9_]+", text.lower())


# ── BM25 (Okapi), by hand ───────────────────────────────────────────────────────
class BM25:
    def __init__(self, docs_tokens: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs = docs_tokens
        self.N = len(docs_tokens)
        self.avgdl = sum(len(d) for d in docs_tokens) / self.N
        df: dict[str, int] = {}
        for d in docs_tokens:
            for t in set(d):
                df[t] = df.get(t, 0) + 1
        self.idf = {t: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for t, n in df.items()}
        self.tf = [{t: d.count(t) for t in set(d)} for d in docs_tokens]

    def scores(self, query_tokens: list[str]) -> list[float]:
        out = []
        for i, d in enumerate(self.docs):
            dl = len(d)
            s = 0.0
            for t in query_tokens:
                f = self.tf[i].get(t, 0)
                if not f:
                    continue
                s += self.idf.get(t, 0.0) * (f * (self.k1 + 1)) / (
                    f + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                )
            out.append(s)
        return out


# ── ranking helpers ─────────────────────────────────────────────────────────────
def rank_by_score(sources: list[str], scores: list[float]) -> list[str]:
    return [sources[i] for i in sorted(range(len(scores)), key=lambda i: -scores[i])]


def rrf(ranked_lists: list[list[str]], k: int = 60) -> list[str]:
    """Reciprocal Rank Fusion: sum 1/(k + rank) across lists. Rank scales ignored."""
    agg: dict[str, float] = {}
    for rl in ranked_lists:
        for rank, src in enumerate(rl):
            agg[src] = agg.get(src, 0.0) + 1.0 / (k + rank + 1)
    return sorted(agg, key=lambda s: -agg[s])


def first_rank(ranked: list[str], target: str) -> int | None:
    for i, s in enumerate(ranked):
        if s == target:
            return i + 1
    return None


# ── evaluation ───────────────────────────────────────────────────────────────────
def score_group(rankings: dict[str, list[str]], group: str):
    """rankings: query -> ranked source list, for queries in `group`. Returns metrics."""
    items = [(q, tgt) for q, tgt, g in QUERIES if g == group]
    hit1 = hit3 = 0
    rr = 0.0
    for q, tgt in items:
        r = first_rank(rankings[q], tgt)
        if r:
            rr += 1.0 / r
            hit1 += r <= 1
            hit3 += r <= 3
    n = len(items)
    return hit1 / n, hit3 / n, rr / n


def evaluate_all(embedder, rrf_k: int = 60):
    """Build/store the corpus, rank every query with bm25/dense/hybrid, and return
    (retrievers, rows):
      retrievers = {name: {query: [ranked sources]}}
      rows       = [{retriever, group, hit@1, hit@3, mrr}]  (for tables/plots)
    Importable so notebooks reuse the exact same pipeline.
    """
    docs = load_docs()
    sources = [s for s, _ in docs]
    texts = [t for _, t in docs]
    vecs = embedder.encode(texts)
    with connect() as conn, conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {TABLE}")
        cur.execute(f"CREATE TABLE {TABLE} (source text, text text, embedding vector({embedder.dim}))")
        cur.executemany(
            f"INSERT INTO {TABLE} (source, text, embedding) VALUES (%s,%s,%s)",
            list(zip(sources, texts, vecs)),
        )
        conn.commit()

        bm25 = BM25([tokenize(t) for t in texts])
        qvecs = embedder.encode([q for q, _, _ in QUERIES])
        dense_r: dict[str, list[str]] = {}
        bm25_r: dict[str, list[str]] = {}
        hybrid_r: dict[str, list[str]] = {}
        for (q, _, _), qv in zip(QUERIES, qvecs):
            cur.execute(
                f"SELECT source FROM {TABLE} ORDER BY embedding <=> %s LIMIT %s",
                (qv, len(docs)),
            )
            dense_r[q] = [r[0] for r in cur.fetchall()]
            bm25_r[q] = rank_by_score(sources, bm25.scores(tokenize(q)))
            hybrid_r[q] = rrf([dense_r[q], bm25_r[q]], k=rrf_k)

    retrievers = {"bm25": bm25_r, "dense": dense_r, "hybrid": hybrid_r}
    rows = []
    for name, rk in retrievers.items():
        for group in ("exact", "semantic"):
            h1, h3, mrr = score_group(rk, group)
            rows.append({"retriever": name, "group": group,
                         "hit@1": h1, "hit@3": h3, "mrr": mrr})
    return retrievers, rows


def main() -> None:
    ap = argparse.ArgumentParser(description="Lab 04 — hybrid retrieval")
    ap.add_argument("--model", default="tei")
    ap.add_argument("--rrf-k", type=int, default=60)
    ap.add_argument("--show", action="store_true", help="print per-query top-3 for each retriever")
    args = ap.parse_args()

    embedder = get_embedder(args.model)
    print(f"embedder: {embedder.name} ({embedder.dim}d), {len(load_docs())} docs\n")
    retrievers, _ = evaluate_all(embedder, rrf_k=args.rrf_k)

    print(f"{'':<9}| {'exact-token queries':^22} | {'semantic queries':^22} |")
    print(f"{'retriever':<9}| {'hit@1':>6}{'hit@3':>7}{'MRR':>7} | {'hit@1':>6}{'hit@3':>7}{'MRR':>7} |")
    print("-" * 56)
    for name, rk in retrievers.items():
        e = score_group(rk, "exact")
        s = score_group(rk, "semantic")
        print(f"{name:<9}| {e[0]:>6.2f}{e[1]:>7.2f}{e[2]:>7.2f} | {s[0]:>6.2f}{s[1]:>7.2f}{s[2]:>7.2f} |")

    print("\nBM25 owns exact tokens (codes/part numbers); Dense owns paraphrases;")
    print("Hybrid (RRF) stays strong on both — the reliable default.")

    if args.show:
        print("\n── per-query top-3 ──")
        for q, tgt, g in QUERIES:
            print(f"\n[{g}] {q}\n   target: {tgt}")
            for name, rk in retrievers.items():
                print(f"   {name:<6}: {rk[q][:3]}")


if __name__ == "__main__":
    main()
