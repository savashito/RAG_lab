# Lab 04 — Hybrid Retrieval (BM25 + Dense + RRF)

> **Status:** built & runnable. Builds on Lab 02–03.

## The problem
Dense vector search matches *meaning* — it finds "automobile" when you ask about
"cars". But it's weak exactly where keywords must match: product codes, error
strings, rare names, acronyms. BM25 (lexical) is the mirror image: unbeatable on
exact tokens, blind to synonyms. The most reliable, cheapest win in modern RAG is
to **run both and fuse the results**.

## What you'll build (`hybrid.py`)
- **BM25**, hand-rolled (`class BM25`) so the formula from the course notes is
  visible — no black box. (In production you'd push this into Postgres via
  ParadeDB/`pg_search`, or approximate it with `tsvector`/`ts_rank_cd`.)
- **Dense** search from pgvector (Labs 01–03).
- **Reciprocal Rank Fusion (RRF)** to merge the two ranked lists:
  `score = Σ 1/(k + rank_i)`. Rank-based, so it ignores the two retrievers'
  incompatible score scales.
- A benchmark that scores **exact-token** vs **semantic** queries *separately*,
  over a corpus with near-duplicate documents distinguished only by a code —
  the situation where dense search breaks.

## Run it
Tunnel open (`./tunnel.sh`), then:
```bash
uv run python 04_hybrid_retrieval/hybrid.py                 # local CPU
uv run python 04_hybrid_retrieval/hybrid.py --model tei      # GPU
uv run python 04_hybrid_retrieval/hybrid.py --show           # per-query top-3
```

## Reading the results
```
         |  exact-token queries   |    semantic queries    |
retriever|  hit@1  hit@3    MRR |  hit@1  hit@3    MRR |
bm25     |   1.00   1.00   1.00 |   0.75   0.75   0.78 |
dense    |   0.75   1.00   0.88 |   1.00   1.00   1.00 |
hybrid   |   1.00   1.00   1.00 |   0.75   1.00   0.83 |
```
- **Dense fails on exact tokens** (0.75): asked about `ERR_4521`, it ranks the
  near-identical sibling `err_4522` *first* — the embedding can't tell the codes
  apart. This gets **worse** as your corpus grows more near-duplicates.
- **BM25 fails on paraphrases** (0.75): "lower our electricity spending" shares no
  rare tokens with the *savings* doc, so it retrieves junk.
- **Hybrid removes the blind spots:** perfect on exact tokens (RRF recovers the
  code match dense missed) and perfect `hit@3` everywhere. No catastrophic
  failure mode — which is why hybrid is the reliable default.

> **Honest nuance:** on this tiny corpus dense's *average* MRR is still high
> because it only stumbles on exact codes. And notice hybrid's semantic `hit@1`
> (0.75) sits *below* dense (1.00): equal-weight RRF let BM25's bad ranking dilute
> a query dense had right. RRF is robust, not magic — **weighting** and a
> **reranker** (Lab 05) recover that top-1 precision.

## Key concepts
| Term | Meaning |
|------|---------|
| Lexical retrieval | Keyword matching (BM25). Exact terms, no semantics. |
| Dense retrieval | Embedding similarity. Semantics, weak on exact tokens. |
| Sparse vs. dense vectors | BM25 = sparse term weights; embeddings = dense. |
| RRF | Rank-based fusion; robust because it ignores raw score scales. |
| Fusion alternatives | Weighted score fusion, learned fusion, ColBERT (Lab 05). |

## Experiments to try
- Build two query sets — one paraphrased, one full of exact IDs — and watch each
  method win its home turf, and hybrid win both.
- Tune RRF's `k` (typically 60). How sensitive is it?
- Compare RRF vs. naive weighted-sum fusion.

## References
- Robertson & Zaragoza 2009, *The Probabilistic Relevance Framework: BM25 and Beyond* — [PDF](https://www.staff.city.ac.uk/~sbrp622/papers/foundations_bm25_review.pdf)
- Karpukhin et al. 2020, *Dense Passage Retrieval (DPR)* — [arXiv:2004.04906](https://arxiv.org/abs/2004.04906)
- Cormack et al. 2009, *Reciprocal Rank Fusion outperforms Condorcet…* — [PDF](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf)
- Gao et al. 2022, *Precise Zero-Shot Dense Retrieval (HyDE)* — [arXiv:2212.10496](https://arxiv.org/abs/2212.10496)
- Thakur et al. 2021, *BEIR* (retrieval benchmark where hybrid shines) — [arXiv:2104.08663](https://arxiv.org/abs/2104.08663)

## Next
**Lab 05 — Reranking.** Retrieval casts a wide net cheaply; a reranker precisely
reorders the top of it.
