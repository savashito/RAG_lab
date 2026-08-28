"""
Generate a small sample PDF so the ingestion lab is runnable without your own
files. Uses PyMuPDF (fitz), which comes with pymupdf4llm.

Headings are written at a larger font size on purpose — pymupdf4llm infers
Markdown heading levels from font size, so this shows real `#`/`##` output.

    uv run python ingestion/make_sample.py
    -> writes ingestion/pdfs/sample.pdf
"""

from pathlib import Path

import pymupdf as fitz  # PyMuPDF (the `fitz` name is deprecated)

OUT = Path(__file__).parent / "pdfs" / "sample.pdf"

SECTIONS = [
    ("h1", "Field Maintenance Guide"),
    ("p", "This guide describes routine maintenance for the coolant system and the "
          "handheld scanner. Follow each step in order and record the results."),
    ("h2", "Coolant Pump"),
    ("p", "The coolant pump circulates fluid to keep the unit within its safe "
          "temperature range. If the pump exceeds its safe temperature, the system "
          "triggers an automatic shutdown. Allow thirty minutes to cool before "
          "restarting."),
    ("h2", "Handheld Scanner"),
    ("p", "The QX-9 handheld scanner runs for up to eighteen hours on a single "
          "charge. Store it in the docking cradle when not in use so it is always "
          "ready for the next shift."),
]


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for kind, text in SECTIONS:
        size = {"h1": 22, "h2": 16, "p": 11}[kind]
        rect = fitz.Rect(72, y, 523, y + 400)
        # insert_textbox returns remaining height; we advance y by what it used
        used = page.insert_textbox(rect, text, fontsize=size, fontname="helv")
        y += (size + 6) if kind != "p" else (rect.height - used) + 10
        if y > 720:  # start a new page if we run low
            page = doc.new_page()
            y = 72
    doc.save(OUT)
    print(f"wrote {OUT}  ({OUT.stat().st_size} bytes, {doc.page_count} page(s))")


if __name__ == "__main__":
    main()
