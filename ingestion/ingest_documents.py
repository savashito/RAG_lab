"""
ingestion/ingest_documents.py — CLI para ingerir documentos legales NUEVOS.

Automatiza, para uno o varios PDFs, el mismo camino validado en los notebooks:

    PDF → Markdown → limpieza (se guarda el .md limpio) → chunking por estructura
        → embeddings (TEI, rtx5090) → upsert por documento en pgvector

A diferencia de `legal_rag.py ingest` (que RECONSTRUYE toda la tabla), este agrega
incrementalmente: la tabla se crea si falta y cada documento reemplaza sólo sus
propias filas (`source`), así el corpus crece sin re-embeber todo.

Requisitos: túnel a Postgres arriba y TEI sirviendo el MISMO embedder que creó la
tabla (ver README). Instala el extra de conversión: `uv sync --extra parse`.

Uso:
    # uno o varios PDFs sueltos
    uv run python ingestion/ingest_documents.py "ruta/al/Documento.pdf" otro.pdf

    # todos los PDFs de una carpeta
    uv run python ingestion/ingest_documents.py --in "ingestion/pdfs/Nuevos"

    # sólo ver el reporte de estrategia, sin tocar la BD
    uv run python ingestion/ingest_documents.py doc.pdf --dry-run

Opciones:
    --table TABLE      tabla destino (default: la del corpus penal)
    --clean-dir DIR    dónde guardar los .md limpios (default: ingestion/out_clean/…)
    --dry-run          convierte, limpia, analiza y chunkea, pero NO inserta
    --no-cache         no cachear embeddings en disco (por defecto sí, resumible)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, ".")
from ingestion.legal_rag import table_name
from ingestion.pipeline import ingest_pdf
from shared.db import connect
from shared.tei_client import TEIClient

LAB_DIR = Path(__file__).parent
DEFAULT_CLEAN_DIR = LAB_DIR / "out_clean" / "Sistema Penal Acusatorio"
CACHE_DIR = LAB_DIR.parent / "exploracion_datos" / ".embed_cache"


def collect_pdfs(paths: list[str], in_dir: str | None) -> list[Path]:
    """Reúne los PDFs a ingerir desde rutas sueltas y/o una carpeta."""
    pdfs: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            pdfs.extend(sorted(p.glob("*.pdf")))
        elif p.suffix.lower() == ".pdf":
            pdfs.append(p)
        else:
            print(f"  ⚠ ignorado (no es PDF ni carpeta): {raw}")
    if in_dir:
        pdfs.extend(sorted(Path(in_dir).glob("*.pdf")))
    # de-dup preservando orden
    seen, unique = set(), []
    for p in pdfs:
        if p.resolve() not in seen:
            seen.add(p.resolve())
            unique.append(p)
    return unique


def print_report(result) -> None:
    """Imprime el reporte 'qué se probó / qué ganó' de un documento, estilo notebook."""
    r = result.report
    print(f"\n── {result.pdf_name}  →  source '{result.source}'")
    if result.error:
        print(f"   ✗ ERROR: {result.error}")
        return
    print(f"   estrategia elegida: {r['strategy'].upper()}  ({r['strategy_reason']})")
    print(f"   probadas:")
    for c in r["candidates"]:
        mark = "✓" if c["qualifies"] else "·"
        winner = "  ← elegida" if c["strategy"] == r["strategy"] else ""
        print(f"       [{mark}] {c['strategy']:<10} {c['evidence']}{winner}")
    removed = r.get("removed_by_reason") or {}
    if removed:
        print(f"   limpieza: " + ", ".join(f"{k}={v}" for k, v in removed.items()))
    print(f"   unidades: {r['n_units']} (p50={r['unit_words_p50']}w · p90={r['unit_words_p90']}w · "
          f"max={r['unit_words_max']}w · {r['oversized_units']} sobre-dimensionadas)")
    print(f"   chunks: {r.get('n_chunks', result.n_chunks)}"
          + (f" (media {r['chunk_words_mean']}w · max {r['chunk_words_max']}w)" if 'chunk_words_mean' in r else ""))
    if result.clean_path:
        print(f"   md limpio: {result.clean_path}")
    if result.inserted:
        verb = "reemplazado" if result.replaced_existing else "insertado"
        print(f"   ✓ {verb} en la tabla ({result.n_chunks} chunks, modelo {result.model})")
    elif not result.error:
        print(f"   (dry-run: no se insertó)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingesta incremental de documentos legales a pgvector")
    ap.add_argument("pdfs", nargs="*", help="PDFs sueltos o carpetas con PDFs")
    ap.add_argument("--in", dest="in_dir", default=None, help="carpeta de PDFs")
    ap.add_argument("--table", default=None, help="tabla destino (default: corpus penal)")
    ap.add_argument("--clean-dir", default=str(DEFAULT_CLEAN_DIR), help="dónde guardar los .md limpios")
    ap.add_argument("--dry-run", action="store_true", help="no insertar; sólo reportar")
    ap.add_argument("--no-cache", action="store_true", help="no cachear embeddings en disco")
    args = ap.parse_args()

    pdfs = collect_pdfs(args.pdfs, args.in_dir)
    if not pdfs:
        ap.error("no diste PDFs. Pasa rutas de .pdf o usa --in CARPETA.")

    table = args.table or table_name()
    tei = TEIClient(cache_dir=None if args.no_cache else CACHE_DIR)
    print(f"ingiriendo {len(pdfs)} documento(s) → tabla '{table}'"
          + (" [DRY-RUN]" if args.dry_run else "") + "\n")

    results = []
    for pdf in pdfs:
        result = ingest_pdf(
            pdf, table=table, tei=tei, connect_fn=connect,
            clean_dir=args.clean_dir, dry_run=args.dry_run,
            progress=lambda stage, msg: print(f"   … {msg}"),
        )
        print_report(result)
        results.append(result)

    ok = sum(1 for r in results if r.inserted or (args.dry_run and not r.error))
    failed = [r for r in results if r.error]
    print(f"\n{'─'*60}\n✓ {ok}/{len(results)} documento(s) procesados"
          + (f" · {len(failed)} con error" if failed else ""))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
