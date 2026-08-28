# Lab 07 — Adaptive & Corrective RAG

> **Status:** planned. Builds on Lab 06 (needs the eval harness).

## The problem
Naive RAG always retrieves, always trusts what it got, and never says "I don't
know" — remember Lab 01 confidently returning junk for an unanswerable question.
Adaptive methods make retrieval a *decision*: retrieve only when useful, judge
whether the evidence is good enough, and fetch more (or refuse) when it isn't.

## What you'll build
- **Self-RAG** — the model emits reflection tokens deciding *whether* to retrieve
  and *whether* its answer is supported by context.
- **Corrective RAG (CRAG)** — a lightweight retrieval **evaluator** grades the
  retrieved passages; if they're weak, trigger a corrective action (re-query,
  web/second-source search, or decompose the question).
- **Adaptive-RAG** — route easy questions to no/1-step retrieval and hard ones to
  multi-step, based on predicted complexity.
- **FLARE** — retrieve *during* generation whenever the model gets uncertain.
- Score every variant on the Lab 06 harness, especially **faithfulness** and
  behaviour on unanswerable questions.

## Key concepts
| Term | Meaning |
|------|---------|
| Retrieve-or-not gating | Skip retrieval when the model already knows. |
| Retrieval evaluator | A grader that scores evidence quality (CRAG). |
| Reflection / self-critique | Model checks its own answer against context (Self-RAG). |
| Active retrieval | Retrieve mid-generation on uncertainty (FLARE). |
| Query rewriting / decomposition | Reshape a bad query into better sub-queries. |
| Abstention | Correctly saying "not enough evidence." |

## Experiments to try
- Does CRAG cut hallucinations on your unanswerable set?
- Measure the accuracy gain vs. the extra LLM calls (cost/latency).
- Query rewriting alone — how far does it get you before full CRAG?

## References
- Asai et al. 2023, *Self-RAG* — [arXiv:2310.11511](https://arxiv.org/abs/2310.11511)
- Yan et al. 2024, *Corrective RAG (CRAG)* — [arXiv:2401.15884](https://arxiv.org/abs/2401.15884)
- Jiang et al. 2023, *FLARE: Active Retrieval-Augmented Generation* — [arXiv:2305.06983](https://arxiv.org/abs/2305.06983)
- Jeong et al. 2024, *Adaptive-RAG* — [arXiv:2403.14403](https://arxiv.org/abs/2403.14403)

## Next
**Lab 08 — GraphRAG.** For multi-hop questions, flat retrieval isn't enough — we
retrieve over a knowledge graph.
