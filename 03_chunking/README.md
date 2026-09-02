# Lab 03 — Chunking

> **Status:** planned. Builds on Lab 01–02.

## The problem
In Lab 01 the chunk that literally defined "hybrid retrieval" ranked **#2**,
because our naive fixed-size splitter cut the idea awkwardly and glued half of a
neighbouring topic to it. Chunking is the single most underrated lever in RAG:
the *unit* you embed decides what can ever be retrieved. Too big → one vector
blurs several ideas. Too small → the vector loses the context needed to match.

## What you'll build
A chunking playground (`compare.py`) that runs the **same corpus + same 12
questions + same embedder** through several strategies and **measures** each,
so the only variable is where the text gets cut:

- **Fixed-size** (`chunkers.fixed`) at three sizes — the Lab 01 baseline.
- **Recursive** (`chunkers.recursive`) — pack whole sentences up to a size budget.
- **Sentence** (`chunkers.sentence`) — N sentences per chunk, using a *naive*
  regex splitter (breaks on any `.`/`!`/`?` + space).
- **Sentence-pysbd** (`chunkers.sentence_pysbd`) — same grouping, but a **proper
  segmenter** (pysbd) that doesn't break on `Dr.`, `U.S.`, `e.g.`, or decimals.
  This is the real-pipeline upgrade over the naive splitter (spaCy/nltk do the
  same job; pysbd needs no model download).
- **Semantic** (`chunkers.semantic`) — start a new chunk where adjacent sentences
  become dissimilar (a topic shift), using the pipeline's embedder.

Metric: retrieve top-5 chunks per question; `hit@k` = answer phrase is in the
top-k, `MRR` = 1/(rank of the first chunk containing it).

> **Stretch:** *late chunking* (embed the whole doc, then pool per-chunk so each
> chunk keeps global context) needs token-level embeddings — a good extension
> once you've seen the basics here. See the reference below.

## Run it
Tunnel open (`./tunnel.sh`), then:
```bash
uv run python 03_chunking/compare.py                 # local CPU embedder
uv run python 03_chunking/compare.py --model tei     # GPU embedder (identical results)
```

### Or run it as a notebook (recommended for exploring)
A guided, visual version lives in [`lab03.ipynb`](lab03.ipynb) — it imports the
same modules (no duplicated logic), shows the naive-vs-pysbd segmentation
side-by-side, and **plots** the hit@k comparison.
```bash
uv sync --all-extras            # installs Jupyter + matplotlib (the `viz` extra)
uv run jupyter lab              # then open 03_chunking/lab03.ipynb (tunnel must be up)
```

## Reading the results
A sample run (MiniLM):

```
strategy       #chunks avg_words   hit@1   hit@3   hit@5    MRR
fixed-20/5          28      18.2    0.60    0.80    0.87   0.69
fixed-40/10         14      34.6    0.87    1.00    1.00   0.92
fixed-80/20          8      56.9    1.00    1.00    1.00   1.00
recursive-40        14      28.2    0.87    1.00    1.00   0.92
sentence-2          16      24.7    0.80    0.93    0.93   0.86
sentence-pysbd      15      26.3    0.87    1.00    1.00   0.92
semantic-0.5        26      15.2    0.60    0.80    0.87   0.70
```

What to notice:
- **Proper segmentation beats naive** (`sentence-pysbd` 0.87 vs `sentence-2` 0.80
  hit@1). The naive splitter breaks after `Dr.` and `approx.`, stranding
  `Dr. Ingrid Halvorsen` and `approx. every 6 months` across a chunk boundary;
  pysbd keeps them whole. This is *the* reason real pipelines use spaCy/nltk/pysbd.
- **Too-small chunks hurt** (`fixed-20`: hit@1 0.60). A 20-word window often
  splits the answer phrase or strands it from its context.
- **`recursive`/`sentence-pysbd` match `fixed-40` using fewer words** — respecting
  real sentence boundaries is more *efficient* per token stored.
- **⚠️ The tiny-corpus trap:** `fixed-80` looks "perfect" only because each doc
  here is short, so an 80-word chunk swallows the whole document — retrieval
  can't miss. That does **not** generalize: at real scale, oversized chunks blur
  multiple ideas into one vector and *lower* precision. This is exactly why we
  measure, and why Lab 06 builds a proper eval set.

## Key concepts
| Term | Meaning |
|------|---------|
| Chunk granularity | The size/shape of the retrieval unit. |
| Overlap | Shared tokens between neighbours so ideas aren't cut at boundaries. |
| Recursive splitting | Prefer natural boundaries; fall back to smaller ones. |
| Semantic chunking | Boundary placed where embedding similarity drops. |
| Late chunking | Contextualise tokens across the full doc *before* pooling into chunks. |
| Proposition indexing | Retrieve atomic factual statements instead of raw spans. |

## Experiments to try
- Same query set, each strategy → which gives highest recall@5?
- Does overlap help, or just inflate the index?
- Re-run with `--model tei` (GPU) so sweeping many configs is fast.

## References
- Chen et al. 2023, *Dense X Retrieval: What Retrieval Granularity Should We Use?* (propositions) — [arXiv:2312.06648](https://arxiv.org/abs/2312.06648)
- Günther et al. 2024, *Late Chunking: Contextual Chunk Embeddings* — [arXiv:2409.04701](https://arxiv.org/abs/2409.04701)
- Anthropic 2024, *Contextual Retrieval* (prepend context before embedding) — [anthropic.com](https://www.anthropic.com/news/contextual-retrieval)
- LangChain docs, *Text splitters* — [python.langchain.com](https://python.langchain.com/docs/concepts/text_splitters/)

### Recent (2025–2026)
- Qu et al. 2024, *Is Semantic Chunking Worth the Computational Cost?* (measures it — often not) — [arXiv:2410.13070](https://arxiv.org/abs/2410.13070)
- **Hierarchical / parent-child chunking** (small chunks to *find*, larger parents to *read*) is the dominant 2025–26 production pattern; late chunking's edge shrinks as embedding models gain long context.

## Next
**Lab 04 — Hybrid retrieval.** Even perfect chunks miss exact keywords; we add
BM25 alongside dense search.
