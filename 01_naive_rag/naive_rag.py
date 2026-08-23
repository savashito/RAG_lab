"""
Lab 01 — Naive RAG (retrieval-only).

The simplest end-to-end retrieval pipeline:

    documents  ->  chunk  ->  embed  ->  store (pgvector)  ->  search

There is deliberately NO index (brute-force scan) and NO generation step yet.
We print the retrieved chunks so you can judge retrieval quality on its own —
that is the 80% that determines whether a RAG system is any good.

Usage (SSH tunnel must be open — see labs/README.md):

    uv run python 01_naive_rag/naive_rag.py ingest
    uv run python 01_naive_rag/naive_rag.py ask "how does hybrid retrieval work?"
    uv run python 01_naive_rag/naive_rag.py ask "..." --model mpnet --k 5

Swap the embedder with --model (minilm | mpnet | bge-small | any HF id).
Changing the model changes the vector dimension, so `ingest` re-creates the
table to match. Always re-ingest after switching models.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, ".")
from shared.db import connect
from shared.embedder import get_embedder

CORPUS_DIR = Path(__file__).parent / "corpus"
TABLE = "chunks"


# ── 1. Chunking ────────────────────────────────────────────────────────────────
def chunk_text(text: str, size: int = 60, overlap: int = 15) -> list[str]:
    """
    Naive fixed-size word chunker with overlap.
    `size` words per chunk, sliding forward by (size - overlap) each step so
    neighbouring chunks share context. Lab 03 explores smarter strategies.
    """
    words = text.split()
    step = size - overlap
    chunks = []
    for start in range(0, len(words), step):
        piece = words[start : start + size]
        if piece:
            chunks.append(" ".join(piece))
        if start + size >= len(words):
            break
    return chunks


def load_chunks() -> list[tuple[str, int, str]]:
    """Return (source_filename, chunk_index, chunk_text) for the whole corpus."""
    out = []
    for path in sorted(CORPUS_DIR.glob("*.md")):
        for i, ch in enumerate(chunk_text(path.read_text())):
            out.append((path.name, i, ch))
    return out


# ── 2. Ingest: chunk → embed → store ───────────────────────────────────────────
def ingest(model: str) -> None:
    embedder = get_embedder(model)
    rows = load_chunks()
    texts = [r[2] for r in rows]
    print(f"embedding {len(texts)} chunks with '{embedder.name}' ({embedder.dim}d)...")
    vectors = embedder.encode(texts)

    with connect() as conn, conn.cursor() as cur:
        # Recreate the table to match this embedder's dimension.
        cur.execute(f"DROP TABLE IF EXISTS {TABLE}")
        cur.execute(
            f"""
            CREATE TABLE {TABLE} (
                id           bigserial PRIMARY KEY,
                source       text,
                chunk_index  int,
                text         text,
                model        text,
                embedding    vector({embedder.dim})
            )
            """
        )
        cur.executemany(
            f"INSERT INTO {TABLE} (source, chunk_index, text, model, embedding) "
            f"VALUES (%s, %s, %s, %s, %s)",
            [
                (src, idx, txt, embedder.name, vec)
                for (src, idx, txt), vec in zip(rows, vectors)
            ],
        )
        conn.commit()
    print(f"✓ stored {len(rows)} chunks in '{TABLE}'.")


# ── 3. Search: embed query → nearest neighbours ────────────────────────────────
def ask(question: str, model: str, k: int) -> None:
    embedder = get_embedder(model)
    qvec = embedder.encode([question])[0]

    with connect() as conn, conn.cursor() as cur:
        # `<=>` = cosine distance. ORDER BY it, take the k closest. That's kNN.
        cur.execute(
            f"""
            SELECT source, chunk_index, text, embedding <=> %s AS distance
            FROM {TABLE}
            ORDER BY distance
            LIMIT %s
            """,
            (qvec, k),
        )
        results = cur.fetchall()

    print(f"\nQ: {question}\n")
    for rank, (src, idx, text, dist) in enumerate(results, 1):
        snippet = text if len(text) < 240 else text[:237] + "..."
        print(f"[{rank}] dist={dist:.4f}  ({src}#{idx})")
        print(f"    {snippet}\n")


# ── CLI ─────────────────────────────────────────────────────────────────────────
def main() -> None:
    p = argparse.ArgumentParser(description="Lab 01 — Naive RAG (retrieval-only)")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("ingest", help="chunk + embed + store the corpus")
    pi.add_argument("--model", default="minilm")

    pa = sub.add_parser("ask", help="retrieve the top-k chunks for a question")
    pa.add_argument("question")
    pa.add_argument("--model", default="minilm")
    pa.add_argument("--k", type=int, default=3)

    args = p.parse_args()
    if args.cmd == "ingest":
        ingest(args.model)
    else:
        ask(args.question, args.model, args.k)


if __name__ == "__main__":
    main()
