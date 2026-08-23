# Lab 01 — Naive RAG (retrieval-only)

The simplest end-to-end pipeline. No index, no reranking, no LLM yet — just:

```
documents → chunk → embed → store (pgvector) → search
```

We stop at **retrieval** and print the chunks, because retrieval quality is what
makes or breaks a RAG system. Generation comes later (eval lab).

## Run it

Terminal 1: `./tunnel.sh`

Terminal 2:
```bash
# one-time: install the embedding model deps (torch + sentence-transformers)
uv sync --extra embed

# chunk + embed + store the sample corpus
uv run python 01_naive_rag/naive_rag.py ingest

# ask questions — you get the top-k most similar chunks
uv run python 01_naive_rag/naive_rag.py ask "how does hybrid retrieval work?"
uv run python 01_naive_rag/naive_rag.py ask "why is RAG energy efficient?" --k 5
```

## The swappable embedder (your experiment)

The embedder is a pluggable component (`shared/embedder.py`). Swap it in one flag:

```bash
uv run python 01_naive_rag/naive_rag.py ingest --model mpnet
uv run python 01_naive_rag/naive_rag.py ask "what is BM25?" --model mpnet
```

Built-in aliases: `minilm` (384d, default), `mpnet` (768d, stronger/slower),
`bge-small` (384d). Or pass any Hugging Face model id.

> ⚠️ Different models produce different vector dimensions, so `ingest` drops and
> recreates the table. **Always re-ingest after changing `--model`**, and use the
> *same* model for `ask` that you used for `ingest`.

### Things to try
- Ask the same question with `minilm` vs `mpnet` — do the ranked results change?
- Change `chunk_text(size=..., overlap=...)` in `naive_rag.py` and re-ingest.
  Bigger chunks = more context per hit but blurrier vectors. This previews Lab 03.
- Ask something the corpus does *not* cover (e.g. "what is the capital of France?").
  Notice retrieval still returns its "closest" chunks with high distance — naive
  RAG has no notion of "I don't know." That gap motivates Labs 06–07.

## What's naive about it (and what later labs fix)

| Limitation here | Fixed in |
|-----------------|----------|
| Brute-force scan (fine for 8 chunks, dies at 1M) | Lab 02 — HNSW index |
| Crude fixed-size chunking | Lab 03 — chunking strategies |
| Pure vector search misses exact keywords | Lab 04 — hybrid + BM25 |
| First-stage ranking is imperfect | Lab 05 — reranking |
| No way to measure "did this help?" | Lab 06 — evaluation |
| Returns junk confidently for unanswerable Qs | Lab 07 — corrective RAG |

## Concepts introduced

| Term | Meaning |
|------|---------|
| **Chunk** | A passage of a document, the unit that gets embedded and retrieved. |
| **Overlap** | Shared words between adjacent chunks so ideas aren't cut at boundaries. |
| **Ingestion** | The offline pass: chunk → embed → store. |
| **Top-k retrieval** | Return the k nearest chunks to the query vector. |
| **Brute-force / flat search** | Compare the query to *every* stored vector. Simple, exact, slow at scale. |
