"""OCR scanned PDFs in ingestion/pdfs/CAG -> markdown, via Docling + macOS Vision (ocrmac).

Usage:
    python ingestion/ocr_cag.py                # convert all PDFs in the CAG folder
    python ingestion/ocr_cag.py "Índice CAG.pdf"   # convert one file by name

Output markdown lands in ingestion/markdown/CAG/<same-name>.md
"""

import sys
import time
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.pipeline_options import PdfPipelineOptions, OcrMacOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

BASE = Path(__file__).resolve().parent
SRC_DIR = BASE / "pdfs" / "CAG"
OUT_DIR = BASE / "markdown" / "CAG"


def build_converter() -> DocumentConverter:
    opts = PdfPipelineOptions()
    # Force CPU: the Docling layout model hits an MPS float64 bug on Apple Silicon.
    opts.accelerator_options = AcceleratorOptions(device=AcceleratorDevice.CPU)
    opts.do_ocr = True
    opts.do_table_structure = True
    # macOS Vision OCR, tuned for Spanish (falls back gracefully if unavailable)
    opts.ocr_options = OcrMacOptions(lang=["es-ES"], force_full_page_ocr=True)
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    files = sys.argv[1:] or [p.name for p in sorted(SRC_DIR.glob("*.pdf"))]
    converter = build_converter()

    for name in files:
        src = SRC_DIR / name
        if not src.exists():
            print(f"SKIP (not found): {src}")
            continue
        out = OUT_DIR / (src.stem + ".md")
        print(f"OCR -> {src.name} ...", flush=True)
        t0 = time.time()
        result = converter.convert(src)
        md = result.document.export_to_markdown()
        out.write_text(md, encoding="utf-8")
        print(f"  done in {time.time() - t0:.0f}s | {len(md):,} chars -> {out}")


if __name__ == "__main__":
    main()
