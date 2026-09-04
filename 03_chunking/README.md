# Lab 03 — Chunking

> **Status:** built & runnable. Builds on Lab 01–02.

## The problem
Chunking is the single most underrated lever in RAG: the *unit* you embed decides
what can ever be retrieved. Too big → one vector blurs several ideas. Too small →
the vector loses the context needed to match. And a blind fixed-size window
ignores the document's real structure — in a legal code it slices an **article**
in half, so the article you asked about is split across two chunks and neither one
retrieves cleanly.

## The corpus
The two Mexican penal codes — **CNPP** (Código Nacional de Procedimientos Penales)
and **Código Penal Federal** — converted to Markdown under
`ingestion/out/Sistema Penal Acusatorio/`. They're where article structure exists,
so they're where the chunking strategy actually changes the outcome. Questions and
the expected article come from [`ingestion/penal_qa.json`](../ingestion/penal_qa.json).

> The corpus is **Spanish**, so the embedder must be multilingual. Use `--model tei`
> (a multilingual TEI model such as Qwen3-Embedding or bge-m3). English-only models
> (`minilm`, `bge-small-en`) retrieve poorly here.

## What you'll build
A chunking playground (`compare.py`) that runs the **same corpus + same questions +
same embedder** through several strategies and **measures** each, so the only
variable is where the text gets cut:

- **Fixed-size** (`chunkers.fixed`) at two sizes — the blind-window baseline.
- **Recursive** (`chunkers.recursive`) — pack whole sentences up to a size budget.
- **By-article** (`chunkers.by_article`) — **structure-aware**: cut on `Artículo N`
  boundaries so each chunk is one article (long articles are sub-split; prose with
  no articles falls back to fixed). This is the strategy that fits legal text.

Metric: retrieve the top-5 chunks per question and check whether the expected
article appears in them.
  * `art_hit@k` = fraction of questions whose article is in the top-k chunks
  * `MRR` = 1/(rank of the first chunk containing the article)

> The `sentence` / `sentence_pysbd` / `semantic` strategies in `chunkers.py` are
> English-tuned (pysbd `language="en"`). Porting them to Spanish
> (`language="es"`) and adding them to `strategies()` is a good exercise.

## Run it
Tunnel open (`./tunnel.sh`), then:
```bash
uv run python 03_chunking/compare.py --model tei     # GPU, multilingual embedder
```

### Or run it as a notebook (recommended for exploring)
A guided, visual version lives in [`lab03.ipynb`](lab03.ipynb) — it imports the
same modules (no duplicated logic), shows a concrete `Artículo 261` split
**fixed-window vs by-article**, and **plots** the `art_hit@k` comparison.
```bash
uv sync --all-extras            # installs Jupyter + matplotlib (the `viz` extra)
uv run jupyter lab              # then open 03_chunking/lab03.ipynb (tunnel must be up)
```

## Reading the results
`compare.py` prints one row per strategy:

```
strategy       #chunks avg_words   art@1   art@3   art@5    MRR
fixed-150/25      ...      ...       ...     ...     ...     ...
fixed-400/40      ...      ...       ...     ...     ...     ...
recursive-150     ...      ...       ...     ...     ...     ...
by-article        ...      ...       ...     ...     ...     ...
```

What to look for (run it to fill in the numbers — they depend on your embedder):
- **`by-article` should win `art_hit@k`.** When each chunk *is* an article, the
  vector is about one coherent legal unit, so the query for that article matches it
  cleanly instead of matching a window that straddles two articles.
- **Fixed vs. article count:** `by-article` produces fewer, more meaningful chunks
  than a tight fixed window — same content, boundaries that mean something.
- **Oversized fixed chunks blur ideas.** Unlike a toy corpus, these codes are large
  and dense, so a 400-word window genuinely mixes multiple articles into one vector
  and can *lower* precision. This is exactly why we measure.

## Key concepts
| Term | Meaning |
|------|---------|
| Chunk granularity | The size/shape of the retrieval unit. |
| Overlap | Shared tokens between neighbours so ideas aren't cut at boundaries. |
| Recursive splitting | Prefer natural boundaries; fall back to smaller ones. |
| Structure-aware chunking | Cut on the document's real units (headings, articles), not blind windows. |
| Semantic chunking | Boundary placed where embedding similarity drops. |
| Late chunking | Contextualise tokens across the full doc *before* pooling into chunks. |

## Experiments to try
- Sweep `by_article(max_words=...)` (150 / 250 / 400) — where's the sweet spot?
- Does overlap help fixed windows here, or just inflate the index?
- Add a Spanish semantic chunker (pysbd `language="es"`) and compare it.

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
