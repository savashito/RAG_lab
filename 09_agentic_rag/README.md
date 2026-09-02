# Lab 09 — Agentic RAG

> **Status:** planned. Frontier. Builds on Lab 07–08.

## The problem
Everything so far runs a **fixed pipeline**: retrieve → (rerank) → generate.
Agentic RAG hands control to the model: it decides *what* to search, *when* it has
enough, whether to search *again* with a refined query, which *tool* or *source*
to use, and when to stop. Recent benchmarks show agentic search closes much of the
gap to GraphRAG on multi-hop tasks — by iterating rather than pre-structuring.

## What you'll build
- A **retrieval agent loop** (ReAct-style: reason → act → observe → repeat) with
  the retriever exposed as a tool.
- **Query planning & decomposition:** break a complex question into sub-questions,
  retrieve for each, synthesise.
- **Multi-tool routing:** vector search, BM25, graph lookup (Lab 08), and the
  Gemma/Claude generator as callable tools.
- **Stopping criteria & budgets:** avoid infinite loops; cap retrieval steps.
- Evaluate on multi-hop questions vs. Lab 07/08 — accuracy *and* cost (LLM calls).

## Key concepts
| Term | Meaning |
|------|---------|
| ReAct | Interleave reasoning traces with tool actions. |
| Tool use / function calling | Retriever/graph exposed as callable tools. |
| Query decomposition | Split hard questions into retrievable sub-questions. |
| Iterative retrieval | Search, read, refine, search again. |
| Agent budget | Step/cost caps so the loop terminates. |

## Experiments to try
- Agentic iterative retrieval vs. one-shot hybrid — accuracy vs. #LLM-calls.
- Does decomposition beat a single well-phrased query?
- Give the agent both vector and graph tools — which does it choose, and when?

## References
- Yao et al. 2022, *ReAct: Synergizing Reasoning and Acting* — [arXiv:2210.03629](https://arxiv.org/abs/2210.03629)
- Press et al. 2022, *Self-Ask* (compositional multi-hop) — [arXiv:2210.03350](https://arxiv.org/abs/2210.03350)
- Schick et al. 2023, *Toolformer* — [arXiv:2302.04761](https://arxiv.org/abs/2302.04761)
- Anthropic 2024, *Building Effective Agents* — [anthropic.com](https://www.anthropic.com/research/building-effective-agents)
- *Do We Still Need GraphRAG?* (agentic vs graph benchmark) — [arXiv:2604.09666](https://arxiv.org/abs/2604.09666)

### Recent (2025–2026)
- 2025, *Search-R1* (LLM search agents trained with RL to learn *when* and *what* to retrieve) — [arXiv:2503.09516](https://arxiv.org/abs/2503.09516)
- 2026, *GRASP: Graph Agentic Search over Propositions* (multi-hop QA) — [arXiv:2605.16598](https://arxiv.org/abs/2605.16598)
- 2025, *RAGCap-Bench* (the capabilities agentic RAG systems actually need) — [arXiv:2510.13910](https://arxiv.org/abs/2510.13910)

## Next
**Lab 10 — Multimodal RAG.** Retrieve over images, tables, and document pages.
