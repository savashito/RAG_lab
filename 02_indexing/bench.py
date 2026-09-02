"""
Lab 02 — Indexing & scale.

Naive RAG (Lab 01) uses BRUTE-FORCE search: every query is compared against
every stored vector. Exact, but O(N) per query — fine for 10 chunks, hopeless
for a million. Approximate Nearest Neighbour (ANN) indexes trade a tiny bit of
accuracy for enormous speed.

This lab uses pgvector's **HNSW** index and MEASURES the tradeoff:
  * recall@k  — did the fast index find the same neighbours as exact search?
  * latency   — how much faster is it?
  * ef_search — the query-time knob that moves you along that tradeoff curve.

Two steps (tunnel must be open — see labs/README.md):

    # 1. generate a big corpus, embed it, store it, build the HNSW index
    uv run python 02_indexing/bench.py build --n 5000

    # 2. benchmark exact vs HNSW across ef_search values, on held-out queries
    uv run python 02_indexing/bench.py run --queries 100 --k 10
"""

from __future__ import annotations

import argparse
import random
import sys
import time

import numpy as np

sys.path.insert(0, ".")
from shared.db import connect
from shared.embedder import get_embedder

TABLE = "bench_items"

# ── Synthetic corpus: many distinct, embeddable sentences ───────────────────────
SUBJECTS = ["the biologist", "a young engineer", "the old sailor", "my neighbour",
            "the astronomer", "a curious student", "the chef", "an arctic fox",
            "the violinist", "a retired teacher", "the geologist", "a street vendor",
            "the archivist", "a marathon runner", "the beekeeper", "a night guard"]
VERBS = ["studied", "repaired", "sketched", "measured", "photographed",
         "described", "collected", "compared", "restored", "counted"]
OBJECTS = ["the coral reef", "an ancient manuscript", "the migrating birds",
           "a rusty steam engine", "the desert stars", "some volcanic rocks",
           "the harbour lights", "a colony of ants", "the glacier's edge",
           "a field of sunflowers", "the abandoned lighthouse", "the river delta"]
PLACES = ["in early spring", "before the storm", "near the mountain pass",
          "during the festival", "at low tide", "under a full moon",
          "on the last day of summer", "far from the city", "after the harvest",
          "in the quiet morning"]


def make_sentences(n: int, seed: int = 0) -> list[str]:
    """Generate n distinct sentences by sampling slot combinations."""
    rng = random.Random(seed)
    seen: set[str] = set()
    out: list[str] = []
    while len(out) < n:
        s = f"{rng.choice(SUBJECTS)} {rng.choice(VERBS)} {rng.choice(OBJECTS)} {rng.choice(PLACES)}"
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


# ── build: generate → embed → store → index ─────────────────────────────────────
def build(n: int, m: int, ef_construction: int, model: str) -> None:
    embedder = get_embedder(model)
    print(f"generating {n} sentences...")
    sentences = make_sentences(n)
    print(f"embedding with {embedder.name} ({embedder.dim}d)... (this is the slow part)")
    t0 = time.perf_counter()
    vecs = embedder.encode(sentences)
    print(f"  embedded in {time.perf_counter() - t0:.1f}s")

    with connect() as conn, conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {TABLE}")
        cur.execute(
            f"CREATE TABLE {TABLE} (id bigserial PRIMARY KEY, text text, "
            f"embedding vector({embedder.dim}))"
        )
        # bulk load first, THEN build the index — building on a full table is
        # much faster than maintaining the graph on every insert.
        # COPY streams all rows in ONE round-trip. (executemany would do one
        # network round-trip per row — deadly slow, and fragile over an SSH
        # tunnel. This is a real lesson: batch your ingestion.)
        with cur.copy(f"COPY {TABLE} (text, embedding) FROM STDIN") as copy:
            for text, vec in zip(sentences, vecs):
                copy.write_row((text, vec))
        conn.commit()
        print(f"✓ stored {n} rows. building HNSW index (m={m}, ef_construction={ef_construction})...")

        t0 = time.perf_counter()
        # vector_cosine_ops → the index is built for the cosine operator `<=>`.
        cur.execute(
            f"CREATE INDEX ON {TABLE} USING hnsw (embedding vector_cosine_ops) "
            f"WITH (m = {m}, ef_construction = {ef_construction})"
        )
        conn.commit()
        print(f"✓ index built in {time.perf_counter() - t0:.1f}s")


# ── run: benchmark exact vs HNSW ────────────────────────────────────────────────
# Key trick: we push ALL queries into ONE SQL statement with a LATERAL join, so
# each configuration costs just 2 round-trips (one for the neighbour ids, one for
# EXPLAIN ANALYZE timing) instead of one per query. Over an SSH tunnel that's the
# difference between ~12 round-trips and ~1200 — much faster and far more robust.


def _neighbours(cur, k: int) -> dict[int, set[int]]:
    """Top-k ids for every query in temp table `q`, as {qid: {ids}}."""
    cur.execute(
        f"""
        SELECT q.qid, nn.id
        FROM q
        CROSS JOIN LATERAL (
            SELECT id FROM {TABLE} ORDER BY embedding <=> q.embedding LIMIT {k}
        ) nn
        """
    )
    out: dict[int, set[int]] = {}
    for qid, nid in cur.fetchall():
        out.setdefault(qid, set()).add(nid)
    return out


def _total_ms(cur, k: int) -> float:
    """Server-side execution time for the whole batch (excludes tunnel)."""
    cur.execute(
        f"""
        EXPLAIN (ANALYZE, TIMING ON, FORMAT JSON)
        SELECT q.qid, nn.id
        FROM q
        CROSS JOIN LATERAL (
            SELECT id FROM {TABLE} ORDER BY embedding <=> q.embedding LIMIT {k}
        ) nn
        """
    )
    return cur.fetchone()[0][0]["Execution Time"]


def collect(n_queries: int, k: int, ef_values: list[int], model: str) -> list[dict]:
    """Benchmark exact vs HNSW and RETURN the rows (so notebooks can plot them).
    Each row: {method, ef, recall, ms_per_query, total_ms}."""
    embedder = get_embedder(model)
    # Held-out queries: NEW sentences the index has never seen (seed differs).
    qvecs = embedder.encode(make_sentences(n_queries, seed=999))
    rows: list[dict] = []
    with connect() as conn, conn.cursor() as cur:
        # Stage the query vectors server-side, once, via COPY.
        cur.execute(f"CREATE TEMP TABLE q (qid int, embedding vector({embedder.dim}))")
        with cur.copy("COPY q (qid, embedding) FROM STDIN") as copy:
            for i, v in enumerate(qvecs):
                copy.write_row((i, v))

        # 1) EXACT ground truth — force a full scan by disabling index scans.
        cur.execute("SET enable_indexscan = off")
        cur.execute("SET enable_bitmapscan = off")
        exact = _neighbours(cur, k)
        exact_ms = _total_ms(cur, k)
        rows.append({"method": "flat", "ef": None, "recall": 1.0,
                     "ms_per_query": exact_ms / n_queries, "total_ms": exact_ms})

        # 2) HNSW at each ef_search — let the planner use the index again.
        cur.execute("SET enable_indexscan = on")
        cur.execute("SET enable_bitmapscan = on")
        for ef in ef_values:
            cur.execute(f"SET hnsw.ef_search = {ef}")
            approx = _neighbours(cur, k)
            total_ms = _total_ms(cur, k)
            recall = float(np.mean([len(exact[q] & approx[q]) / k for q in exact]))
            rows.append({"method": "hnsw", "ef": ef, "recall": recall,
                         "ms_per_query": total_ms / n_queries, "total_ms": total_ms})
    return rows


def run(n_queries: int, k: int, ef_values: list[int], model: str) -> None:
    rows = collect(n_queries, k, ef_values, model)
    print(f"benchmarking {n_queries} queries, k={k}\n")
    print(f"{'method':<14}{'ef_search':>10}{'recall@'+str(k):>12}{'ms/query':>10}{'total_ms':>10}")
    print("-" * 56)
    for r in rows:
        ef = "-" if r["ef"] is None else r["ef"]
        label = "flat (exact)" if r["method"] == "flat" else "hnsw"
        print(f"{label:<14}{ef:>10}{r['recall']:>12.3f}{r['ms_per_query']:>10.3f}{r['total_ms']:>10.1f}")
    print("\nTimes are SERVER-side (EXPLAIN ANALYZE) for the whole batch, so they reflect")
    print("the index, not the SSH tunnel. Higher ef_search → higher recall, slower queries.")
    print("The win vs flat grows with corpus size — try `build --n 50000` and re-run.")


def main() -> None:
    p = argparse.ArgumentParser(description="Lab 02 — Indexing & scale")
    sub = p.add_subparsers(dest="cmd", required=True)

    pb = sub.add_parser("build", help="generate + embed + store + index")
    pb.add_argument("--n", type=int, default=5000)
    pb.add_argument("--m", type=int, default=16, help="HNSW: max edges per node")
    pb.add_argument("--ef-construction", type=int, default=64, help="HNSW: build-time search width")
    pb.add_argument("--model", default="tei", help="embedder: minilm (CPU) | tei (GPU) | mpnet | ...")

    pr = sub.add_parser("run", help="benchmark exact vs HNSW")
    pr.add_argument("--queries", type=int, default=100)
    pr.add_argument("--k", type=int, default=10)
    pr.add_argument("--ef", type=int, nargs="+", default=[10, 20, 40, 100, 200],
                    help="hnsw.ef_search values to sweep")
    pr.add_argument("--model", default="tei", help="must match what you built with")

    args = p.parse_args()
    if args.cmd == "build":
        build(args.n, args.m, args.ef_construction, args.model)
    else:
        run(args.queries, args.k, args.ef, args.model)


if __name__ == "__main__":
    main()
