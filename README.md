# RAG Labs

A hands-on course in building a Retrieval-Augmented Generation system, from the
simplest possible loop to the current state of the art. Each lab is a folder you
can run and experiment with; each one builds on the last and is designed so you
can **measure** whether a change actually helped.

## The stack

| Piece | What it is | Role |
|-------|-----------|------|
| **Postgres 16 + pgvector** | `rag_lab` DB on the prod server (`srv1312754`) | Stores chunks **and** their embeddings + metadata. Nearest-neighbour search lives here. |
| **MinIO** | S3-compatible object store, bucket `llm-lab` | The "filing cabinet" — raw source documents (PDFs, text). |
| **TEI (GPU)** | HF Text Embeddings Inference on `rtx5090`, port 8085 | Turns text → vectors on the RTX 5090 (~10× the laptop). Optional: `--model tei`. |
| **SSH tunnels** | `:5433 → Postgres`, `:8085 → TEI` | How your laptop reaches both (neither is exposed publicly). `./tunnel.sh` opens both. |

> **Why pgvector and not the object store for vectors?** An object store has no
> "find nearest" operation — you'd load every vector and scan by hand. pgvector
> adds real indexed nearest-neighbour search *inside SQL*, so vectors sit right
> next to the text and metadata you filter on. See Lab 02.

## One-time setup

```bash
cd labs
uv sync                 # creates .venv and installs deps
```

## Every time you work

Open the tunnels in **one terminal** and leave them running:

```bash
./tunnel.sh             # :5433 -> Postgres,  :8085 -> TEI (GPU)
```

Then in another terminal, run a lab:

```bash
uv run python 00_setup/check.py
```

> Prefer to run *on the server* instead of tunnelling? Set `RAG_DB_HOST=localhost`
> and `RAG_DB_PORT=5432` in `.env`, and skip the tunnel.

## Embedding: laptop CPU vs GPU service

The embedder is swappable (`shared/embedder.py`). Every lab takes `--model`:

| `--model` | Where it runs | Notes |
|-----------|---------------|-------|
| `minilm` (default) | your laptop CPU | all-MiniLM-L6-v2, 384d. No GPU needed. |
| `mpnet`, `bge-small` | your laptop CPU | other local models to compare. |
| **`tei`** | **rtx5090 GPU** | same MiniLM via TEI, ~10× faster. Needs the `:8085` tunnel. Drop-in with `minilm` (identical vectors). |

`tei` reads `TEI_URL` from `.env` (default `http://localhost:8085`). Because it
serves the same normalised MiniLM, vectors are interchangeable with local
`minilm` — you can ingest with one and query with the other.

## Roadmap

| Lab | Title | You learn | Storage |
|-----|-------|-----------|---------|
| **00** | Setup & sanity | Connect end-to-end; nearest-neighbour in raw SQL (`<=>`) | ✅ built |
| **01** | Naive RAG | chunk → embed → store → retrieve | ✅ built |
| **02** | Indexing & scale | HNSW index, why brute-force breaks, recall vs speed | ✅ built |
| **03** | Chunking | fixed vs recursive vs semantic; measure the difference | pgvector |
| **04** | Hybrid retrieval | BM25 (Postgres full-text) + dense, fused with RRF | pgvector |
| **05** | Reranking | cross-encoder / late-interaction rerank | pgvector |
| **06** | Evaluation | faithfulness, context recall — so every later change is *measured* | pgvector |
| **07** | Corrective / adaptive RAG | grade retrieval, re-retrieve when weak | pgvector |
| **08+** | Graph / agentic / multimodal | the frontier | — |

## Isolation & safety

- Everything lives in its own database `rag_lab`, owned by role `rag`. Your other
  projects (`epihorizon`, `tlacua_db`) are untouched.
- Credentials are in `labs/.env` (gitignored). Never commit them.
- Pre-change backups of the other DBs are on the server at `/home/tlacua/backups/`.
