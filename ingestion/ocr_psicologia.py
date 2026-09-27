"""OCR de los PDFs ESCANEADOS de psicología → markdown, con Docling + macOS Vision.

Solo para los 5 escaneados que el pipeline de prod (sin OCR) no pudo ingerir.
Reusa la config de ocr_cag.py (CPU para esquivar el bug MPS float64, Vision en es-ES).

Salida: ingestion/markdown/psicologia_fix_vision/<mismo-nombre>.md
"""

import sys
import time
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.pipeline_options import PdfPipelineOptions, OcrMacOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

BASE = Path(__file__).resolve().parent
SRC_DIR = BASE / "pdfs" / "psicologia"
OUT_DIR = BASE / "markdown" / "psicologia_fix_vision"

SCANNED = [
    "1. La anorexia por actividad.pdf",
    "21. Terapia de conducta-Cap1.pdf",
    "27. Restructuración semántica.pdf",
    "39. El sujeto en el modificación de la conducta.pdf",
    "9. Cuando la adiccion aprende por reflejo.pdf",
]


def build_converter() -> DocumentConverter:
    opts = PdfPipelineOptions()
    opts.accelerator_options = AcceleratorOptions(device=AcceleratorDevice.CPU)
    opts.do_ocr = True
    opts.do_table_structure = True
    opts.ocr_options = OcrMacOptions(lang=["es-ES"], force_full_page_ocr=True)
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    files = sys.argv[1:] or SCANNED
    converter = build_converter()
    for name in files:
        src = SRC_DIR / name
        if not src.exists():
            print(f"SKIP (no existe): {src}")
            continue
        out = OUT_DIR / (src.stem + ".md")
        print(f"OCR -> {src.name} ...", flush=True)
        t0 = time.time()
        md = converter.convert(src).document.export_to_markdown()
        out.write_text(md, encoding="utf-8")
        print(f"  done in {time.time() - t0:.0f}s | {len(md):,} chars -> {out}")


if __name__ == "__main__":
    main()
