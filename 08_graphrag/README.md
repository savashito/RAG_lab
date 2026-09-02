# Lab 08 — GraphRAG

> **Status:** planned. Frontier. Builds on Lab 06–07.

## The problem
Flat retrieval answers "what does the doc say about X?" well, but struggles with
**multi-hop** and **global** questions: "how are A and C connected?" or "what are
the main themes across the whole corpus?" — where the answer is spread across many
documents and requires following relationships. GraphRAG builds an explicit
structure so the system can *traverse* instead of just match.

## What you'll build
- **Knowledge-graph construction:** use an LLM to extract entities + relations
  from chunks into nodes/edges (stored in Postgres — no new DB needed).
- **Community detection + summaries** (the Microsoft GraphRAG pattern): cluster
  the graph and pre-summarise clusters for global "sense-making" queries.
- **Graph-aware retrieval:** start from matched entities, walk N hops, gather the
  connected subgraph as context.
- Compare against Lab 04 hybrid on a **multi-hop** query set — and honestly note
  the **build cost**, which is GraphRAG's real tradeoff.

## Key concepts
| Term | Meaning |
|------|---------|
| Knowledge graph | Entities (nodes) + relations (edges) extracted from text. |
| Multi-hop reasoning | Answer requires chaining several facts/relations. |
| Local vs global queries | Specific-entity lookup vs. whole-corpus themes. |
| Community summarisation | Pre-summarise graph clusters for global questions. |
| Build-cost amortisation | Expensive to build; pays off across many queries. |

## Experiments to try
- Multi-hop questions: GraphRAG vs. hybrid — where does the graph actually help?
- How much does entity-extraction quality (model choice) affect results?
- Measure graph build time/cost vs. the query-quality gain.

## References
- Edge et al. 2024, *From Local to Global: GraphRAG for Query-Focused Summarization* (Microsoft) — [arXiv:2404.16130](https://arxiv.org/abs/2404.16130)
- Gutiérrez et al. 2024, *HippoRAG* (neurobiologically-inspired long-term memory) — [arXiv:2405.14831](https://arxiv.org/abs/2405.14831)
- Guo et al. 2024, *LightRAG* (simple, fast graph RAG) — [arXiv:2410.05779](https://arxiv.org/abs/2410.05779)
- Microsoft GraphRAG (open-source implementation) — [github.com/microsoft/graphrag](https://github.com/microsoft/graphrag)

### Recent (2025–2026)
- 2025, *Think-on-Graph 3.0* (adaptive multi-agent reasoning over heterogeneous graphs) — [arXiv:2509.21710](https://arxiv.org/abs/2509.21710)
- 2025, *Graph-R1* (agentic GraphRAG trained end-to-end with reinforcement learning) — [arXiv:2507.21892](https://arxiv.org/abs/2507.21892)
- 2025, *GraphRAG-R1* (process-constrained RL for graph RAG) — [arXiv:2507.23581](https://arxiv.org/abs/2507.23581)
- *A Survey of Agentic GraphRAG* (2026) — the shift from graph retrieval to graph-native agents.

## Next
**Lab 09 — Agentic RAG.** Let the model plan its own multi-step retrieval.
