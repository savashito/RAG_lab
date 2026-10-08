# Retrieval for Mexican Criminal Law RAG: lexical, dense, hybrid and query-expansion strategies on statute-grounded benchmarks

## Abstract

We study retrieval strategies for a retrieval-augmented generation (RAG) assistant over Mexican criminal law, where answers must cite the exact article of the correct code. The corpus comprises 46 documents (8,641 chunks, ~3.4 M words): seven codes — Federal Penal Code, the National Code of Criminal Procedure, and the penal codes of Mexico City, the State of Mexico, Morelos and Querétaro — plus general laws (kidnapping, extortion, organized crime, victims) and ~30 doctrinal books. Codes are chunked one article per chunk, with the law name and structural hierarchy (book › title › chapter › article) prepended to the embedded text. We evaluate on three expert-written benchmarks (163 questions, 254 gold articles), including a set of comparative questions that require articles from two jurisdictions at once. Measuring recall of the gold article in the top-10, hybrid retrieval (BM25 + Qwen3-Embedding-0.6B fused with RRF) outperforms BM25 (0.82 vs 0.63) and dense retrieval (0.77). HyDE and LLM-based query decomposition add further gains (0.88 combined). A lightweight, LLM-free *code routing* step — searching additionally inside each code named in the question — matches decomposition on comparative questions at less than half the latency. End-to-end, 74–91% of questions are answered fully correctly under an LLM judge.

## Setup

- **Retrievers.** BM25 (in-memory); dense (Qwen3-Embedding-0.6B via TEI, pgvector); hybrid = Reciprocal Rank Fusion of both.
- **Query-side additions.** *HyDE* (the LLM drafts a hypothetical statute passage that is embedded with the question); *decomposition* (the LLM splits comparative questions into one sub-query per entity; results are interleaved); *code routing* (no LLM: entity and code names detected in the question, accent- and typo-tolerant, trigger an extra search restricted to that code, interleaved with the unrestricted search).
- **Generator / judge.** Gemma 4 (26B-A4B MoE, 4-bit, llama.cpp).
- **Benchmarks** (written by a criminal-law expert; each question has *must / should / error* criteria):
  - **S1** — 50 general questions (sexual offences, general part, criminal procedure; 80 gold articles);
  - **S2** — 56 single-law questions (kidnapping and extortion general laws, penal codes; 56 gold articles);
  - **S3** — 57 comparative questions, Mexico City vs. Querétaro (118 gold articles).
- **Metric.** Gold articles are parsed from the *must* criteria; we report Recall@k of the gold article chunk in the ranking (before neighbour expansion) and MRR@50. This metric is judge-free.

## Retrieval results (Recall@10; Recall@20 in parentheses)

| Configuration | S1 general | S2 single-law | S3 comparative | Pooled (254) | s/query |
|---|---|---|---|---|---|
| BM25 | 0.55 (0.73) | 0.95 (0.95) | 0.54 (0.64) | 0.63 | 0.1 |
| Dense | 0.70 (0.81) | 0.96 (0.98) | 0.72 (0.86) | 0.77 | 0.3 |
| Hybrid (RRF) | 0.79 (0.90) | 0.96 (0.98) | 0.77 (0.90) | 0.82 | 0.4 |
| Hybrid + HyDE | 0.83 (0.90) | 0.96 (0.98) | 0.81 (0.91) | 0.85 | 1.1 |
| Hybrid + Decomposition | 0.81 (0.90) | 0.98 (1.00) | 0.81 (0.98) | 0.85 | 1.1–1.7 |
| Hybrid + Code routing | 0.78 (0.91) | 0.96 (0.98) | 0.82 (0.95) | 0.84 | 0.7–1.1 |
| Hybrid + HyDE + Decomposition | **0.86** (0.93) | 0.96 (0.98) | **0.86** (0.95) | **0.88** | 2.3–4.0 |
| Hybrid + HyDE + Code routing | 0.85 (**0.95**) | 0.96 (0.98) | **0.86** (**0.96**) | **0.88** | 1.4–1.8 |

MRR@50 follows the same ordering; it is highest for Hybrid + HyDE + Code routing on S1 (0.52) and S3 (0.50).

## End-to-end (LLM-judged answers)

| Benchmark | Configuration | Fully correct | Mean score | Gold article in context |
|---|---|---|---|---|
| S3 comparative | Hybrid + HyDE + Decomposition | 43/57 (75%) | 0.886 | 110/118 |
| S3 comparative | Hybrid + HyDE + Code routing | 43/57 (75%) | 0.879 | 112/118 |
| S1 general | Hybrid + HyDE + Decomposition | 37/50 (74%) | 0.894 | 72/80 |
| S2 single-law | Dense + HyDE | 51/56 (91%) | 0.944 | — |

Re-running an identical configuration changed the number of fully correct answers by 3/57, so differences of that size are within judge/generation noise; the judge-free recall metric is the more reliable signal.

## Findings

1. **Hybrid retrieval is the essential baseline.** On S1 and S3, fusing BM25 and dense retrieval adds +5 to +9 points of Recall@10 over dense and +23 over BM25. BM25 alone is competitive only when questions name the law and article (S2).
2. **Comparative questions are the hard case.** Articles of the same offence in other states (and neighbouring articles of the same code) crowd out the second jurisdiction. Decomposition and code routing both address this (S3 Recall@20: 0.90 → 0.98 / 0.95).
3. **Code routing is a cheap substitute for LLM decomposition.** Combined with HyDE it reaches the same pooled Recall@10 (0.88) with ~2.2–2.4× lower latency, and needs no extra LLM call. On top of decomposition it adds nothing.
4. **Chunking and metadata matter as much as the retriever.** Prepending the law's name to every chunk was decisive for codes whose name appeared only in page headers: the median dense rank of gold articles fell from 21 to 4. Recognising article labels such as "737 A", "Bis" and "Quáter" was needed for correct citations.
5. **Evaluation pitfalls.** Negatively phrased error criteria ("Do not omit…") inverted the judge's verdict and depressed the pass rate from 75% to 7–12%. Unrecognised historical names ("Distrito Federal" for Mexico City) mislabelled gold articles. Both were fixed before the results above.

## Limitations

- Single expert-authored benchmark per question type; gold articles derived from criteria text.
- One embedding model; generator and judge are the same LLM.
- Code routing depends on a curated list of code names and aliases.
