# Self-hosted embedders for TEI

TEI serves **one** model at a time (whatever is loaded). Swap it with:

```bash
./serve.sh <hf-model-id>     # recreates the container; downloads on the server
```

Then check it, and **re-ingest** any lab (the vector dimension may change):

```bash
curl -s localhost:8085/info | python3 -m json.tool   # (tunnel up)
```

All models below are verified [TEI-supported](https://huggingface.co/docs/text-embeddings-inference/en/supported_models)
and fit the RTX 5090 (32 GB). Pick by **use case**, not just leaderboard rank.

## Recommended

| Use case | Model id | dim | ctx | size | Command |
|---|---|---|---|---|---|
| **Fast default** (concept labs, lab02 scale) | `BAAI/bge-small-en-v1.5` | 384 | 512 | 33M | `./serve.sh BAAI/bge-small-en-v1.5` |
| Even lighter | `sentence-transformers/all-MiniLM-L6-v2` | 384 | 256 | 22M | `./serve.sh sentence-transformers/all-MiniLM-L6-v2` |
| **Balanced** | `BAAI/bge-base-en-v1.5` | 768 | 512 | 109M | `./serve.sh BAAI/bge-base-en-v1.5` |
| Balanced, long ctx | `nomic-ai/nomic-embed-text-v1.5` | 768 | 8192 | 137M | `./serve.sh nomic-ai/nomic-embed-text-v1.5` |
| **Long-context** (papers) | `Alibaba-NLP/gte-large-en-v1.5` | 1024 | 8192 | 434M | `./serve.sh Alibaba-NLP/gte-large-en-v1.5` |
| Multilingual, long ctx | `BAAI/bge-m3` | 1024 | 8192 | 568M | `./serve.sh BAAI/bge-m3` |
| **Top retrieval** (bake-off) | `Qwen/Qwen3-Embedding-0.6B` | 1024 | 32K | 0.6B | `./serve.sh Qwen/Qwen3-Embedding-0.6B` |
| Max quality (slower) | `Qwen/Qwen3-Embedding-4B` | 2560 | 32K | 4B | `./serve.sh Qwen/Qwen3-Embedding-4B` |

## Guidance
- **Concept labs (01–04) want a *light* model.** Embedding thousands of vectors
  (lab02) through a heavy model over the SSH tunnel is slow and can drop the
  connection. Serve `bge-small` for day-to-day lab work.
- **Reserve heavy models (Qwen3, gte-large, bge-m3) for the Lab 06 bake-off**,
  where quality is the point and you embed once.
- **Higher `dim` costs storage + index size** in pgvector; **longer `ctx`** avoids
  truncating long passages (good for papers).
- The leaderboard is a shortlist — the Lab 06 bake-off on *your* corpus is the answer.
