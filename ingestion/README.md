# Companion Lab — PDF → Markdown ingestion

> **Status:** built & runnable. A *companion* module, not a numbered step — do it
> whenever you want the labs to retrieve over **your own documents** instead of
> the toy corpora.

## Why this matters
RAG retrieves over **text**, never the PDF. So conversion is unavoidable — and
it's where a huge share of real-world RAG quality is won or lost. Two rules:

1. **Target Markdown, not raw text.** Markdown keeps *structure* (headings, lists,
   tables). That structure is exactly what the recursive/semantic chunkers in
   [Lab 03](../03_chunking/) use for good boundaries, and it gives the LLM cleaner
   context. A `##` heading is a meaningful chunk break; a raw-text blob throws
   that away.
2. **The tool matters more than the format.** Extraction quality — not the `.md`
   extension — determines everything downstream.

## Pick the tool for your documents
| Your PDFs are… | Use | Notes |
|---|---|---|
| Digital, mostly text, single column | **`pymupdf4llm`** (this lab) | Markdown out of the box, fast, one call. |
| Complex layout — columns, many tables | **Docling** (IBM) / **Marker** | Layout-aware, far better tables. Heavier. |
| Scanned / image-only | OCR (**Tesseract**) or a **VLM** | No text layer exists; must recognize it. Your rtx5090 can run a vision model. |
| Heavily visual (forms, figures) | skip text → **multimodal RAG** | Retrieve over page *images* (ColPali/ColQwen) — see [Lab 10](../10_multimodal_rag/). |

## Run it
```bash
uv sync --all-extras                           # installs everything (parse + embed)
# (use --all-extras, not just --extra parse — a bare --extra REPLACES the set
#  and would uninstall the embedding deps the other labs need)

uv run python ingestion/make_sample.py         # creates a sample PDF to try
uv run python ingestion/convert.py             # ingestion/pdfs/*.pdf -> ingestion/out/*.md
```
Then **open `ingestion/out/sample.md` and read it.** That eyeball check — did
headings survive? did tables become garbage? — is the single highest-ROI step in
a RAG pipeline.

Point it at your own files, and optionally push the Markdown to MinIO (the
"filing cabinet" from the main README):
```bash
uv run python ingestion/convert.py --in ~/my_pdfs --out ingestion/out
uv run python ingestion/convert.py --minio-prefix rag_lab/markdown
```

## How it fits the architecture
```
   PDFs ──convert.py──► Markdown ──chunk+embed──► pgvector (search)
    │                      │
    └──────► MinIO ◄───────┘   (raw PDF + extracted .md kept together)
```
Convert **once, ahead of time**; store both the original PDF and the `.md` in
MinIO so it's reproducible and inspectable. Then any lab can chunk the `.md` and
retrieve over it — e.g. drop the `.md` files into a lab's `corpus/` folder.

## Automatizado: ingerir documentos legales nuevos (incremental)

`convert.py` sólo hace PDF→Markdown. Para el flujo **completo y automatizado** de
un documento legal nuevo — convertir, **limpiar**, **chunkear con la estrategia
correcta**, **embeber** e **insertar** — usa el pipeline reutilizable:

```
PDF ─► Markdown ─► limpieza (guarda el .md limpio) ─► chunking por estructura
    ─► embeddings (TEI, rtx5090) ─► upsert por documento en pgvector
```

Toda la lógica vive en [`pipeline.py`](pipeline.py) (funciones de una sola
responsabilidad, sin CLI ni HTTP): reutiliza la limpieza y el chunking validados
en `shared/legal_chunking.py`, donde **la estrategia se elige sola por documento**
(`article` para leyes/códigos, `heading` para doctrina, `paragraph` para prosa).
El CLI y el tab web del app son cáscaras delgadas encima.

### CLI

```bash
uv sync --all-extras                                    # necesita el extra `parse`

# uno o varios PDFs (crea la tabla si falta; cada doc reemplaza sólo SUS filas)
uv run python ingestion/ingest_documents.py "ruta/al/Documento.pdf" otro.pdf
uv run python ingestion/ingest_documents.py --in "ingestion/pdfs/Nuevos"

# sólo ver qué estrategia elige y por qué, SIN tocar la BD
uv run python ingestion/ingest_documents.py doc.pdf --dry-run
```

Imprime, por documento, **qué estrategias se probaron y cuál ganó** (con su
evidencia: densidad de artículos, nº de encabezados), qué se limpió, y cuántos
chunks quedaron — el mismo razonamiento de las secciones 2–5 del notebook
`exploracion_datos/exploracion_chunking_corpus.ipynb`, ahora por documento.

### Incremental vs. reconstrucción

- `ingest_documents.py` (y el tab del app) hacen **upsert por documento**: la tabla
  se crea si no existe (nunca se borra) y cada `source` reemplaza sólo sus propias
  filas. El corpus **crece** sin re-embeber todo.
- `legal_rag.py ingest` **reconstruye** toda la tabla desde el corpus en disco
  (`DROP` + recrear). Útil para un rebuild limpio; no para agregar un solo doc.

Ambos comparten el mismo esquema e inserción (`pipeline.ensure_schema` /
`pipeline.copy_rows`), así que las tablas quedan idénticas por cualquiera de las dos
vías. El `source` canónico de un PDF es `<nombre>.md` (misma convención que el
corpus ya ingestado), para que reconvertir un documento lo reemplace bien.

> **Guarda de dimensión:** insertar en una tabla existente exige que TEI sirva el
> **mismo embedder** con que se creó (misma dimensión de vector). Si no coincide,
> el pipeline falla con un mensaje claro en vez de corromper la búsqueda.

## Experiment: RAG on real papers (Root Apical Meristem)

`ram_rag.py` runs the full pipeline over a real corpus (10 plant-biology PDFs +
20 research questions from a `.docx`) and measures two fixes with an ablation:

```bash
uv run python ingestion/ram_rag.py compare        # A/B/C ablation
uv run python ingestion/ram_rag.py askall --model bge-small --k 3
```

| config | #chunks | avg top-1 dist | ref-noise@3 |
|---|---|---|---|
| minilm (raw) | 653 | 0.420 | **15%** |
| minilm + strip refs | 392 | 0.423 | **0%** |
| bge-small + strip refs | 392 | **0.199** | **0%** |

**Findings:** stripping bibliographies removed ~40% of chunks (all citation
noise) and killed reference-noise (15%→0%); a retrieval-tuned embedder
(`bge-small`, 512-token window) then tightened matches (dist 0.42→0.20). Coverage
gaps stay honest — *Casparian strip* questions retrieve weakly because no paper
covers it. Full walkthrough + plots: [`ram_experiment.ipynb`](ram_experiment.ipynb).

## Vector table naming convention

Each corpus you ingest gets its own vector table. To keep those names consistent
(and avoid the `penal_chunks` vs `penal_fixed` drift), **don't hand-write table
names** — build them with `ram_rag.table_name(corpus, model, chunker)`.

**The rule** — one table per `(corpus, model, chunker)` combination:

```
{corpus}__{model}__{chunker}
```

- **lowercase**; every run of non-alphanumeric chars (`-`, `/`, `:`, `.`, spaces,
  and `_`) collapses to a single `_` — because `-`/`/` would force double-quoting
  or be invalid in a Postgres identifier.
- axis separator is `__` (double underscore), so it's distinct from the single
  `_` that can appear *inside* a part (e.g. `bge_small`).
- pass a **short model alias** (`minilm`, `bge-small`, `qwen06`), not the full HF
  id — `table_name("penal", "tei:Qwen/Qwen3-Embedding-0.6B", …)` slugs into an
  unreadable mess.

```python
ram_rag.table_name("penal", "bge-small", "article")  # -> "penal__bge_small__article"
ram_rag.table_name("ram",   "qwen06")                # -> "ram__qwen06__fixed"
```

**Why the model is in the name (the hard constraint):** different embedders emit
different vector dimensions, and two dimensions can't share one `vector(N)`
column — so a different embedder *forces* a different table. Corpus and chunker
don't force it (they could be filter columns instead); they're in the name only
because we chose the simple **one-table-per-config** design for the labs. The
table name is just a readable handle — the exact model is also stored in each
row's `model` column (see `store_chunks`) as the source of truth. `CHUNK_TABLE`
(`"ram_chunks"`) is the legacy flat name for the original RAM lab; new work uses
`table_name()`.

## Concepts
| Term | Meaning |
|------|---------|
| Text extraction | Pulling the readable text out of a PDF's layout. |
| Layout analysis | Recovering reading order, columns, headings, tables. |
| OCR | Recognizing text from an image (scanned pages). |
| Structure-aware chunking | Splitting on Markdown headings/sections, not blind windows. |

## References
- PyMuPDF4LLM docs — [pymupdf.readthedocs.io](https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/)
- Docling (IBM) — [github.com/DS4SD/docling](https://github.com/DS4SD/docling)
- Marker — [github.com/VikParuchuri/marker](https://github.com/VikParuchuri/marker)
- Unstructured — [github.com/Unstructured-IO/unstructured](https://github.com/Unstructured-IO/unstructured)
- Faysse et al. 2024, *ColPali: Efficient Document Retrieval with Vision LMs* — [arXiv:2407.01449](https://arxiv.org/abs/2407.01449)
