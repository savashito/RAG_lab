"""
Companion lab — convert PDFs to Markdown for RAG.

Why Markdown (not raw text): it keeps document *structure* — headings, lists,
tables. That structure is exactly what the recursive/semantic chunkers in Lab 03
use to find good boundaries, and it gives the LLM cleaner context later.

This uses pymupdf4llm, which is fast and great for digital, text-based PDFs.
For complex layouts (multi-column, dense tables) or scanned/image PDFs, see the
tool table in the README — the conversion tool matters more than anything else.

Convert once, ahead of time, and EYEBALL the output — bad extraction silently
ruins every downstream step.

Usage (install deps first: `uv sync --extra parse`):
    uv run python ingestion/convert.py                       # pdfs/ -> out/
    uv run python ingestion/convert.py --in some/dir --out md/
    uv run python ingestion/convert.py --minio-prefix rag_lab/markdown
    uv run python ingestion/convert.py --in "ingestion/pdfs/Sistema Penal Acusatorio-Bibliografía" --out "ingestion/out/Sistema Penal Acusatorio"
"""

from __future__ import annotations

import argparse
import io
import os
import re
from pathlib import Path

import pymupdf4llm
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def stats(md: str) -> str:
    """A quick, eyeball-able quality summary of the extracted Markdown."""
    headings = len(re.findall(r"^#{1,6}\s", md, flags=re.M))
    table_rows = len(re.findall(r"^\s*\|.*\|\s*$", md, flags=re.M))
    words = len(md.split())
    return f"{words:>6} words | {headings:>2} headings | {table_rows:>3} table rows"


def upload_minio(key: str, md: str) -> None:
    from minio import Minio

    client = Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=os.environ.get("MINIO_SECURE", "true").lower() == "true",
    )
    raw = md.encode()
    client.put_object(
        os.environ["MINIO_BUCKET"], key, io.BytesIO(raw), len(raw),
        content_type="text/markdown; charset=utf-8",
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="PDF -> Markdown for RAG")
    ap.add_argument("--in", dest="src", default="ingestion/pdfs", help="folder of PDFs")
    ap.add_argument("--out", dest="dst", default="ingestion/out", help="folder for .md")
    ap.add_argument("--minio-prefix", default=None,
                    help="also upload each .md under this key prefix in the MinIO bucket")
    args = ap.parse_args()

    src, dst = Path(args.src), Path(args.dst)
    dst.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(src.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs in {src}/. Drop files there, or run: "
              f"uv run python ingestion/make_sample.py")
        return

    print(f"converting {len(pdfs)} PDF(s) from {src}/ -> {dst}/\n")
    for pdf in pdfs:
        md = pymupdf4llm.to_markdown(str(pdf))  # -> Markdown string
        out = dst / (pdf.stem + ".md")
        out.write_text(md)
        line = f"  {pdf.name:<28} -> {out.name:<28} {stats(md)}"
        if args.minio_prefix:
            key = f"{args.minio_prefix.rstrip('/')}/{out.name}"
            upload_minio(key, md)
            line += f"  ↑ minio:{key}"
        print(line)

    print(f"\n✓ done. Inspect the Markdown in {dst}/ before chunking it — "
          f"that eyeball check is the highest-ROI step in RAG.")


if __name__ == "__main__":
    main()
