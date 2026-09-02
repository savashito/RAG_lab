"""
Lab 03 — Chunking, measured.

Runs the SAME corpus and the SAME questions through several chunking strategies
and scores each one on whether the retrieved context actually contains the
answer. Same embedder, same retrieval — only the chunk boundaries change — so
any difference in the score is caused by chunking alone.

Metric: for each question we retrieve the top-5 chunks (cosine) for a strategy
and check if the gold phrase appears in them.
  * hit@k  = fraction of questions whose answer is in the top-k chunks
  * MRR    = mean of 1/(rank of first chunk containing the answer)

Usage (tunnel open):
    uv run python 03_chunking/compare.py                 # local CPU embedder
    uv run python 03_chunking/compare.py --model tei     # GPU embedder
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, ".")
from shared.db import connect
from shared.embedder import get_embedder

import chunkers  # noqa: E402  (local module, added to path above)
from questions import QUESTIONS  # noqa: E402

CORPUS_DIR = Path(__file__).parent / "corpus"
TABLE = "chunk_lab"
TOPK = 5


def load_docs() -> list[tuple[str, str]]:
    return [(p.name, p.read_text()) for p in sorted(CORPUS_DIR.glob("*.md"))]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def strategies(embedder):
    """(name, function) pairs. Each maps a document's text -> list[chunk]."""
    return [
        ("fixed-20/5",   lambda t: chunkers.fixed(t, size=20, overlap=5)),
        ("fixed-40/10",  lambda t: chunkers.fixed(t, size=40, overlap=10)),
        ("fixed-80/20",  lambda t: chunkers.fixed(t, size=80, overlap=20)),
        ("recursive-40",   lambda t: chunkers.recursive(t, size=40)),
        ("sentence-2",     lambda t: chunkers.sentence(t, per_chunk=2)),
        ("sentence-pysbd", lambda t: chunkers.sentence_pysbd(t, per_chunk=2)),
        ("semantic-0.5",   lambda t: chunkers.semantic(t, embedder, threshold=0.5)),
    ]


def build(embedder) -> None:
    """Chunk the corpus every which way and store all chunks in one table."""
    docs = load_docs()
    rows: list[tuple[str, str, str]] = []  # (strategy, source, text)
    for name, fn in strategies(embedder):
        for source, text in docs:
            for ch in fn(text):
                rows.append((name, source, ch))

    texts = [r[2] for r in rows]
    vecs = embedder.encode(texts)

    with connect() as conn, conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {TABLE}")
        cur.execute(
            f"CREATE TABLE {TABLE} (id bigserial PRIMARY KEY, strategy text, "
            f"source text, text text, embedding vector({embedder.dim}))"
        )
        cur.executemany(
            f"INSERT INTO {TABLE} (strategy, source, text, embedding) VALUES (%s,%s,%s,%s)",
            [(s, src, txt, v) for (s, src, txt), v in zip(rows, vecs)],
        )
        conn.commit()


def collect_metrics(embedder) -> list[dict]:
    """Score every strategy and RETURN the numbers (so notebooks can plot them)."""
    qvecs = embedder.encode([q for q, _ in QUESTIONS])
    nq = len(QUESTIONS)
    rows: list[dict] = []
    with connect() as conn, conn.cursor() as cur:
        for name, _ in strategies(embedder):
            cur.execute(f"SELECT count(*), avg(array_length(string_to_array(text,' '),1)) "
                        f"FROM {TABLE} WHERE strategy=%s", (name,))
            n_chunks, avg_words = cur.fetchone()

            hits = {1: 0, 3: 0, 5: 0}
            rr_sum = 0.0
            for (q, gold), qv in zip(QUESTIONS, qvecs):
                cur.execute(
                    f"SELECT text FROM {TABLE} WHERE strategy=%s "
                    f"ORDER BY embedding <=> %s LIMIT {TOPK}",
                    (name, qv),
                )
                retrieved = [norm(r[0]) for r in cur.fetchall()]
                g = norm(gold)
                rank = next((i + 1 for i, t in enumerate(retrieved) if g in t), None)
                if rank:
                    rr_sum += 1.0 / rank
                    for k in (1, 3, 5):
                        if rank <= k:
                            hits[k] += 1
            rows.append({
                "strategy": name, "n_chunks": n_chunks, "avg_words": float(avg_words),
                "hit@1": hits[1] / nq, "hit@3": hits[3] / nq, "hit@5": hits[5] / nq,
                "mrr": rr_sum / nq,
            })
    return rows


def evaluate(embedder) -> None:
    rows = collect_metrics(embedder)
    print(f"\n{'strategy':<14}{'#chunks':>8}{'avg_words':>10}"
          f"{'hit@1':>8}{'hit@3':>8}{'hit@5':>8}{'MRR':>7}")
    print("-" * 63)
    for r in rows:
        print(f"{r['strategy']:<14}{r['n_chunks']:>8}{r['avg_words']:>10.1f}"
              f"{r['hit@1']:>8.2f}{r['hit@3']:>8.2f}{r['hit@5']:>8.2f}{r['mrr']:>7.2f}")
    print("\nSame corpus, same questions, same embedder — only the chunking changed.")
    print("Higher hit@k / MRR = the answer landed in retrievable chunks more often.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Lab 03 — compare chunking strategies")
    ap.add_argument("--model", default="tei", help="minilm (CPU) | tei (GPU) | mpnet | ...")
    args = ap.parse_args()

    embedder = get_embedder(args.model)
    print(f"embedder: {embedder.name} ({embedder.dim}d)")
    build(embedder)
    evaluate(embedder)


if __name__ == "__main__":
    main()
