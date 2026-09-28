"""
ingestion/pdf_triage.py — ¿este PDF necesita OCR? Decide ANTES de convertir.

La mayoría de los PDFs son digitales: `pymupdf4llm` los convierte en el VPS en
segundos. Sólo los escaneados (o con la capa de texto rota) se mandan al servicio OCR
de la Mac mini. Esta revisión es barata (lee la estructura del PDF, no hace OCR) y
se hace por página:

  * escaneada   — casi sin texto extraíble y cubierta por una imagen (foto/escáner).
  * texto roto  — tiene texto, pero una fracción alta son caracteres inválidos
                  (U+FFFD, uso privado, controles, letras de alfabetos ajenos): la
                  fuente trae mal su tabla ToUnicode y extraer da basura.

Si la fracción de páginas con contenido que necesitan OCR pasa `DOC_THRESHOLD`, el
documento entero va a OCR. Si son pocas (p. ej. un anexo escaneado), se convierte en el
VPS y el reporte avisa qué páginas quedaron fuera.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

MIN_TEXT_CHARS = 50        # menos que esto en una página = "sin texto"
MIN_IMAGE_COVER = 0.15     # fracción mínima tapada por imágenes para que "sin texto" = foto
                           # (hay escaneos chicos sobre una hoja grande: 27–48% en uno real)
MAX_BAD_RATIO = 0.05       # >5% de caracteres inválidos = capa de texto rota
DOC_THRESHOLD = 0.2        # >20% de las páginas con contenido → OCR del documento

# Alfabetos esperables en el corpus (español/inglés + citas griegas). Una letra de
# cualquier otro alfabeto en un texto de este corpus casi siempre es un glifo mal
# mapeado (p. ej. el cingalés que sale de la fuente rota del libro de sociología).
_OK_SCRIPTS = ("LATIN", "GREEK")


def _is_bad_char(ch: str) -> bool:
    if ch == "�":
        return True
    cat = unicodedata.category(ch)
    if cat == "Co" or (cat == "Cc" and ch not in "\n\r\t"):
        return True
    if cat.startswith("L"):
        name = unicodedata.name(ch, "")
        return not name.startswith(_OK_SCRIPTS)
    return False


def bad_char_ratio(text: str) -> float:
    """Fracción de caracteres no-blancos que son inválidos para este corpus."""
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return 0.0
    return sum(_is_bad_char(c) for c in chars) / len(chars)


def _image_cover(page) -> float:
    """Fracción aproximada del área de la página tapada por imágenes (tope 1.0)."""
    area = abs(page.rect)
    if not area:
        return 0.0
    covered = 0.0
    for info in page.get_image_info():
        bbox = page.rect & info["bbox"]          # recorta a la página
        covered += abs(bbox) if not bbox.is_empty else 0.0
    return min(covered / area, 1.0)


def classify_page(page) -> str:
    """'text' | 'scanned' | 'broken_text' | 'blank' para UNA página de PyMuPDF."""
    text = page.get_text()
    n_chars = sum(1 for c in text if not c.isspace())
    if n_chars < MIN_TEXT_CHARS:
        return "scanned" if _image_cover(page) >= MIN_IMAGE_COVER else "blank"
    return "broken_text" if bad_char_ratio(text) > MAX_BAD_RATIO else "text"


def triage_pdf(source) -> dict:
    """Revisa un PDF (ruta, bytes o documento PyMuPDF abierto) y decide si necesita OCR.

    Devuelve {pages, scanned_pages, broken_pages, blank_pages, ocr_ratio, needs_ocr,
    reason}. Las listas de páginas son 1-based, como las ve un humano."""
    import pymupdf

    own = not isinstance(source, pymupdf.Document)
    doc = (pymupdf.open(stream=source, filetype="pdf") if isinstance(source, (bytes, bytearray))
           else pymupdf.open(Path(source)) if own else source)
    try:
        kinds = [classify_page(p) for p in doc]
    finally:
        if own:
            doc.close()

    scanned = [i + 1 for i, k in enumerate(kinds) if k == "scanned"]
    broken = [i + 1 for i, k in enumerate(kinds) if k == "broken_text"]
    blank = [i + 1 for i, k in enumerate(kinds) if k == "blank"]
    with_content = len(kinds) - len(blank)
    ratio = (len(scanned) + len(broken)) / with_content if with_content else 0.0
    needs_ocr = ratio > DOC_THRESHOLD

    if not kinds:
        reason = "PDF sin páginas."
    elif needs_ocr:
        parts = []
        if scanned:
            parts.append(f"{len(scanned)} página(s) escaneada(s) sin texto")
        if broken:
            parts.append(f"{len(broken)} con la capa de texto rota")
        reason = f"{' y '.join(parts)} de {with_content} con contenido ({ratio:.0%})."
    elif scanned or broken:
        reason = (f"Digital, salvo {len(scanned) + len(broken)} página(s) sin texto útil "
                  f"({ratio:.0%}, bajo el umbral de {DOC_THRESHOLD:.0%}).")
    else:
        reason = "PDF digital: todas las páginas tienen texto extraíble."
    return {"pages": len(kinds), "scanned_pages": scanned, "broken_pages": broken,
            "blank_pages": blank, "ocr_ratio": round(ratio, 3), "needs_ocr": needs_ocr,
            "reason": reason}
