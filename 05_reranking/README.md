# Lab 05 — Reranking

> **Status:** planned. Builds on Lab 04.

## The problem
First-stage retrieval (dense + BM25) is optimised for **recall at low cost** — get
the right passage *somewhere* in the top 50. But your generator only sees the top
3–5. A **reranker** is a slower, more accurate model that re-scores those
candidates so the best ones rise to the very top. On hard queries this adds
several points of accuracy for little extra latency (you only rerank ~50 items).

## What you'll build
- **Cross-encoder reranker** — feeds *(query, passage)* through a model together
  (full attention between them), unlike the bi-encoder that embeds them
  separately. Far more accurate, too slow for first-stage, perfect for reranking.
- **Late-interaction reranking (ColBERT)** — per-token vectors with MaxSim; a
  middle ground between bi-encoder speed and cross-encoder accuracy.
- Two-stage pipeline: retrieve top-50 (Lab 04) → rerank → keep top-5.
- Measure the accuracy lift and the latency cost of the extra stage.
- Optionally serve the reranker on the **GPU box** (rtx5090), like TEI.

## Key concepts
| Term | Meaning |
|------|---------|
| Bi-encoder | Encodes query and doc separately; fast; used for retrieval. |
| Cross-encoder | Encodes query+doc together; accurate; used for reranking. |
| Late interaction | Per-token vectors + MaxSim (ColBERT); accuracy≈cross-enc, faster. |
| Two-stage retrieval | Cheap wide recall → expensive precise reorder. |
| Hard negatives | Wrong-but-similar passages; training on them sharpens rerankers. |

## Experiments to try
- top-50 → rerank → top-5 vs. plain top-5. How much does MRR/nDCG move?
- Cross-encoder vs. ColBERT: accuracy vs. latency tradeoff.
- Vary the first-stage depth (rerank top-20 vs top-100).

## References
- Nogueira & Cho 2019, *Passage Re-ranking with BERT (monoBERT)* — [arXiv:1901.04085](https://arxiv.org/abs/1901.04085)
- Reimers & Gurevych 2019, *Sentence-BERT* (bi- vs cross-encoders) — [arXiv:1908.10084](https://arxiv.org/abs/1908.10084)
- Khattab & Zaharia 2020, *ColBERT* (late interaction) — [arXiv:2004.12832](https://arxiv.org/abs/2004.12832)
- Santhanam et al. 2021, *ColBERTv2* — [arXiv:2112.01488](https://arxiv.org/abs/2112.01488)
- Faysse et al. 2024, *ColPali* (late interaction over document images) — [arXiv:2407.01449](https://arxiv.org/abs/2407.01449)

### Recent (2025–2026)
- Sun et al. 2023, *Is ChatGPT Good at Search?* (a.k.a. **RankGPT** — listwise reranking with LLMs, the line the below build on) — [arXiv:2304.09542](https://arxiv.org/abs/2304.09542)
- 2025, *InsertRank* (inject the BM25 score into listwise LLM reranking) — [arXiv:2506.14086](https://arxiv.org/abs/2506.14086)
- 2025, *How Good are LLM-based Rerankers? An Empirical Analysis* — [arXiv:2508.16757](https://arxiv.org/abs/2508.16757)
- 2025, *GroupRank* (efficient groupwise passage reranking) — [arXiv:2511.11653](https://arxiv.org/abs/2511.11653)
- 2025, *LLM4Ranking* (easy-to-use reranking framework) — [arXiv:2504.07439](https://arxiv.org/abs/2504.07439)

## Next
**Lab 06 — Evaluation.** From here on, no change ships without a number behind it.
