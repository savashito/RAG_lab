# Lab 06 — Evaluation

> **Status:** planned. The keystone lab — everything after this is measured.

## The problem
Up to now we've eyeballed results. That doesn't scale and it lies. To improve a
RAG system you must **separate retrieval quality from generation quality** and put
numbers on both — otherwise you can't tell whether a change helped or just felt
better on the three queries you happened to try.

## What you'll build
- A small **gold eval set**: questions + reference answers + the passages that
  should be retrieved (over our own corpus).
- **Retrieval metrics:** Recall@k, MRR, nDCG, Hit@k.
- **Generation metrics (RAGAS-style, LLM-as-judge):** *faithfulness* (is the
  answer grounded in retrieved context?), *answer relevance*, *context precision
  / recall*. This is where we finally add the **generation step** — calling the
  Gemma `llama-server` on rtx5090 (or Claude) to write answers from context.
- A **harness** that runs any pipeline config end-to-end and prints a scorecard,
  so Labs 03–05 and 07+ become A/B experiments instead of vibes.
- **Embedding-model bake-off:** the fresh-SOTA search you asked for — benchmark
  MiniLM vs BGE vs GTE vs a bigger model, all via the swappable embedder.

## Key concepts
| Term | Meaning |
|------|---------|
| Recall@k / MRR / nDCG | Did we retrieve the right passages, and how highly ranked? |
| Faithfulness | Answer claims are all supported by the retrieved context. |
| Answer relevance | Answer actually addresses the question. |
| Context precision/recall | Was retrieved context on-point and complete? |
| LLM-as-judge | Use an LLM to score faithfulness/relevance at scale. |

## Experiments to try
- Re-run Lab 03 chunking strategies through the harness — which *actually* wins?
- Does the Lab 05 reranker improve faithfulness, or just retrieval metrics?
- Swap embedding models and rank them on *your* data, not a leaderboard.

## References
- Es et al. 2023, *RAGAS: Automated Evaluation of RAG* — [arXiv:2309.15217](https://arxiv.org/abs/2309.15217)
- Saad-Falcon et al. 2023, *ARES: Automated RAG Evaluation* — [arXiv:2311.09476](https://arxiv.org/abs/2311.09476)
- Muennighoff et al. 2022, *MTEB: Massive Text Embedding Benchmark* — [arXiv:2210.07316](https://arxiv.org/abs/2210.07316)
- Thakur et al. 2021, *BEIR* — [arXiv:2104.08663](https://arxiv.org/abs/2104.08663)
- MTEB leaderboard (current embedding SOTA) — [huggingface.co/spaces/mteb/leaderboard](https://huggingface.co/spaces/mteb/leaderboard)

### Recent (2025–2026)
- 2025, *Benchmarking LLM Faithfulness in RAG with Evolving Leaderboards* (FaithJudge, EMNLP 2025) — [arXiv:2505.04847](https://arxiv.org/abs/2505.04847)
- *FaithBench* — hallucination benchmark for modern-LLM summarization (NAACL 2025).
- *LiveRAG 2025 Challenge* — live single- and multi-hop QA over DataMorgana pairs.

## Next
**Lab 07 — Adaptive / Corrective RAG.** Now that we can measure, we can safely add
self-correction.
