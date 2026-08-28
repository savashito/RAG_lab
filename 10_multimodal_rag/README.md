# Lab 10 — Multimodal RAG

> **Status:** planned. Frontier. Capstone.

## The problem
Real documents aren't clean text — they're PDFs full of tables, charts, diagrams,
and scanned pages. Text-only pipelines mangle them (brittle PDF parsing loses
layout, tables, and figures entirely). Multimodal RAG retrieves over the *visual*
document and reasons over images alongside text.

## What you'll build
- **ColPali-style page retrieval:** embed rendered *page images* directly with a
  vision model and retrieve over them — skipping fragile PDF text extraction.
- **Image + table embeddings:** store and search figures/tables next to text
  chunks in pgvector (multi-vector rows with a modality tag).
- **Vision-language generation:** feed retrieved page images to a VLM
  (e.g. `medgemma`/gemma-vision already on rtx5090, or Claude) to answer.
- Evaluate on questions whose answers live in a figure or table, where text-only
  RAG fails outright.

## Key concepts
| Term | Meaning |
|------|---------|
| Document-image retrieval | Retrieve over rendered pages, not extracted text. |
| Late interaction (ColPali) | Per-patch image vectors + MaxSim against the query. |
| Multi-vector store | Text/image/table vectors coexist with a modality column. |
| Cross-modal search | Text query → image/table results (and vice-versa). |
| VLM generation | Vision-language model answers from retrieved images. |

## Experiments to try
- ColPali page retrieval vs. text-extraction RAG on a table-heavy PDF.
- Can a text query retrieve the right *chart*? Measure it.
- Use the GPU's vision models (medgemma / gemma) for the answer step.

## References
- Faysse et al. 2024, *ColPali: Efficient Document Retrieval with Vision LMs* — [arXiv:2407.01449](https://arxiv.org/abs/2407.01449)
- Yu et al. 2024, *VisRAG: Vision-based RAG over multi-modal documents* — [arXiv:2410.10594](https://arxiv.org/abs/2410.10594)
- Chen et al. 2022, *MuRAG: Multimodal Retrieval-Augmented Generation* — [arXiv:2210.02928](https://arxiv.org/abs/2210.02928)
- *Scaling Beyond Context: Survey of Multimodal RAG for Document Understanding* — [arXiv:2510.15253](https://arxiv.org/abs/2510.15253)

### Recent (2025–2026)
- **ColQwen2 / 2.5 / 3** — the ColPali recipe on Qwen-VL backbones; currently top the ViDoRe V2 leaderboard (stronger, multilingual).
- *MetaEmbed* (ICLR 2026), *SV-RAG* (ICLR 2025), *URaG* (AAAI 2026) — recent visual-document RAG advances.
- *Multimodal RAG Survey* (curated, maintained) — [github.com/llm-lab-org/multimodal-rag-survey](https://github.com/llm-lab-org/multimodal-rag-survey)

## You made it
By here you'll have built, and *measured*, a RAG system from a raw SQL cosine
distance up through hybrid retrieval, reranking, self-correction, graphs, agents,
and vision — on your own infrastructure. See the top-level `README.md` for the map.
