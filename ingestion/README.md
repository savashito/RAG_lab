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
