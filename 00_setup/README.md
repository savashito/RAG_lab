# Lab 00 — Setup & Sanity

**Goal:** prove the whole chain works before building anything on it.

```
your laptop  ──ssh tunnel :5433──►  rag_lab (Postgres)  ──►  pgvector
```

## Run it

Terminal 1 (leave open):
```bash
./tunnel.sh
```

Terminal 2:
```bash
uv run python 00_setup/check.py
```

Expected output ends with `✓ Lab 00 passed`.

## What it teaches

`check.py` does a **vector round-trip** in plain SQL — the single operation
every vector database is built on:

```sql
SELECT name, embedding <=> '[1,0,0]' AS cosine_distance
FROM items
ORDER BY cosine_distance
LIMIT 3;
```

- `embedding` is a `vector(3)` column (pgvector's type).
- `<=>` is the **cosine-distance** operator: `0` = same direction, `2` = opposite.
- `ORDER BY ... LIMIT k` is **k-nearest-neighbour search**. That's it. Everything
  else in this course — chunking, hybrid search, reranking — is about making sure
  the *right* things end up near each other in this space.

pgvector also gives you `<->` (L2/Euclidean) and `<#>` (negative inner product).
We'll mostly use cosine, which is standard for text embeddings.

## Concepts introduced

| Term | Meaning |
|------|---------|
| **Embedding** | A list of numbers representing meaning; similar meaning → nearby vectors. |
| **Vector column** | `vector(N)` — a fixed-length embedding stored in Postgres. |
| **Cosine distance** | How different two vectors' *directions* are. Smaller = more similar. |
| **k-NN search** | "Give me the k closest rows to this query vector." |

Next: **Lab 01 — Naive RAG**, where the vectors stop being toy `[1,0,0]`s and
start being real sentence embeddings.
