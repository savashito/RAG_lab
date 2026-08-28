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

### Managing the TEI service (on rtx5090)

The service is a Docker container named `tei-embed`, started with
`--restart unless-stopped` (so it comes back on reboot — unless you explicitly
stop it). You manage it over SSH. Docker needs `sudo` there, and `sudo` needs a
terminal to read your password — so use **`ssh -t`** (the `-t` allocates a TTY;
without it you get `sudo: a terminal is required`). You'll be prompted for your
sudo password each time.

```bash
ssh -t rtx5090 'sudo docker ps --filter name=tei-embed'     # is it running?
```
```bash
ssh -t rtx5090 'sudo docker logs --tail 50 tei-embed'       # recent logs
```
```bash
ssh -t rtx5090 'sudo docker stop tei-embed'                 # stop (stays stopped across reboots)
```
```bash
ssh -t rtx5090 'sudo docker start tei-embed'                # start again
```
```bash
ssh -t rtx5090 'sudo docker restart tei-embed'              # restart
```

Quick health check from your laptop — no sudo needed (just the `:8085` tunnel):
```bash
curl -s localhost:8085/info | python3 -m json.tool
```

**Optional: drop `sudo` for good.** Add yourself to the `docker` group once, then
log out of *all* sessions on that box and back in:
```bash
ssh -t rtx5090 'sudo usermod -aG docker $USER'
```
After a fresh login, `ssh rtx5090 'docker ps'` works with **no `sudo` and no
`-t`**. (Until that full re-login, keep using `ssh -t ... sudo`.)

**To change the served model** (e.g. try BGE), recreate the container:
```bash
ssh -t rtx5090 'sudo docker rm -f tei-embed && sudo docker run -d --name tei-embed --restart unless-stopped --gpus all -p 127.0.0.1:8085:80 -v /home/ai-server/tei-data:/data ghcr.io/huggingface/text-embeddings-inference:120-1.9 --model-id BAAI/bge-small-en-v1.5'
```
> Changing the model changes the vectors (and maybe the dimension), so anything
> you embedded with the old model must be re-ingested.

## Roadmap

| Lab | Title | You learn | Storage |
|-----|-------|-----------|---------|
| **00** | Setup & sanity | Connect end-to-end; nearest-neighbour in raw SQL (`<=>`) | ✅ built |
| **01** | Naive RAG | chunk → embed → store → retrieve | ✅ built |
| **02** | Indexing & scale | HNSW index, why brute-force breaks, recall vs speed | ✅ built |
| 📎 *companion* | [Ingestion: PDF → Markdown](ingestion/) | turn your own PDFs into a corpus the labs can retrieve over | ✅ built |
| **03** | Chunking | fixed vs recursive vs semantic; measure the difference | ✅ built |
| **04** | Hybrid retrieval | BM25 + dense, fused with RRF; exact-vs-semantic queries | ✅ built |
| **05** | Reranking | cross-encoder / late-interaction rerank | 📄 planned |
| **06** | Evaluation | faithfulness, context recall — the keystone; every later change is *measured* | 📄 planned |
| **07** | Adaptive / Corrective RAG | grade retrieval, re-retrieve when weak, know when to abstain | 📄 planned |
| **08** | GraphRAG | knowledge-graph retrieval for multi-hop / global questions | 📄 planned |
| **09** | Agentic RAG | the model plans its own multi-step, multi-tool retrieval | 📄 planned |
| **10** | Multimodal RAG | retrieve over page images / tables; VLM answers (capstone) | 📄 planned |

Each planned lab already has a README with concepts and paper references — read
ahead. "✅ built" labs have runnable code.

## Foundational reading

- Lewis et al. 2020, *Retrieval-Augmented Generation for Knowledge-Intensive NLP* (the original RAG paper) — [arXiv:2005.11401](https://arxiv.org/abs/2005.11401)
- Gao et al. 2023, *Retrieval-Augmented Generation for LLMs: A Survey* — [arXiv:2312.10997](https://arxiv.org/abs/2312.10997)
- Malkov & Yashunin 2016, *HNSW* (the index behind Lab 02) — [arXiv:1603.09320](https://arxiv.org/abs/1603.09320)
- pgvector — [github.com/pgvector/pgvector](https://github.com/pgvector/pgvector)

## Isolation & safety

- Everything lives in its own database `rag_lab`, owned by role `rag`. Your other
  projects (`epihorizon`, `tlacua_db`) are untouched.
- Credentials are in `labs/.env` (gitignored). Never commit them.
- Pre-change backups of the other DBs are on the server at `/home/tlacua/backups/`.
