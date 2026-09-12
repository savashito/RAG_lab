"""
Pruebas de ingestion/pipeline.py — las etapas PURAS del pipeline de ingesta
(clasificación/reporte, chunking por documento, nombres y esquema). No tocan la BD
ni TEI: eso se valida por separado con los túneles arriba.

    uv run pytest tests/test_pipeline.py
"""

from __future__ import annotations

import sys
from pathlib import Path

LABS = Path(__file__).resolve().parents[1]
if str(LABS) not in sys.path:
    sys.path.insert(0, str(LABS))

from ingestion import pipeline as P

# Documento tipo LEY: muchos artículos, densos → estrategia 'article'.
LAW = "\n\n".join(
    f"**Artículo {i}o.** " + "palabra " * 40 for i in range(1, 16)
)
# Documento tipo DOCTRINA: encabezados Markdown, sin artículos → 'heading'.
DOCTRINE = "\n\n".join(
    f"## Sección {i}\n\n" + "texto " * 60 for i in range(1, 6)
)
# Prosa sin estructura → 'paragraph'.
PROSE = "\n\n".join("oración de relleno " * 30 for _ in range(4))


def test_analyze_picks_article_for_dense_law():
    r = P.analyze_document("ley.md", LAW)
    assert r["strategy"] == "article"
    assert r["article_count"] >= 10
    # El scoreboard reporta las tres estrategias probadas, y 'article' califica.
    strategies = {c["strategy"] for c in r["candidates"]}
    assert strategies == {"article", "heading", "paragraph"}
    assert next(c for c in r["candidates"] if c["strategy"] == "article")["qualifies"]


def test_analyze_picks_heading_for_doctrine():
    r = P.analyze_document("doc.md", DOCTRINE)
    assert r["strategy"] == "heading"
    assert r["heading_count"] >= 3
    assert not next(c for c in r["candidates"] if c["strategy"] == "article")["qualifies"]


def test_analyze_falls_back_to_paragraph():
    r = P.analyze_document("prosa.md", PROSE)
    assert r["strategy"] == "paragraph"
    # Siempre reporta la distribución de tamaños de las unidades.
    assert r["n_units"] >= 1
    assert r["unit_words_p50"] > 0


def test_chunk_document_columns_match_copy_schema():
    """Los chunks traen exactamente las columnas que el COPY escribe (menos el vector
    y el modelo, que se agregan al insertar). Protege el contrato con la BD."""
    chunks = P.chunk_document("ley.md", LAW)
    assert not chunks.empty
    expected = {"source", "title", "hierarchy", "unit_type", "position", "part", "words"}
    assert expected.issubset(set(chunks.columns))
    assert "text_for_embedding" in chunks.columns
    # Todas las columnas de metadata del esquema existen en el DataFrame.
    for col in P.META_COLS:
        assert col in chunks.columns


def test_source_name_uses_pdf_stem():
    assert P.source_name("/x/y/Código Penal Federal.pdf") == "Código Penal Federal.md"
    assert P.source_name("doc.PDF") == "doc.md"


def test_create_table_sql_is_idempotent_and_has_dim():
    sql = P.create_table_sql("mi_tabla", 1024)
    assert "CREATE TABLE IF NOT EXISTS mi_tabla" in sql
    assert "vector(1024)" in sql


def test_save_clean_markdown_roundtrip(tmp_path):
    path = P.save_clean_markdown(tmp_path, "doc.md", "texto limpio")
    assert path.read_text(encoding="utf-8") == "texto limpio"
    assert path.name == "doc.md"
