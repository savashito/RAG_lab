"""
ingestion/pipeline.py — pipeline reutilizable PDF → vectores en pgvector.

Orquesta, con funciones de responsabilidad única, el mismo camino que ya validaron
los notebooks de exploración, sin duplicar su lógica: importa la limpieza y el
chunking POR ESTRUCTURA de `shared.legal_chunking` (la estrategia se elige sola por
documento: `article` / `heading` / `paragraph`) y embebe con el mismo TEI de la
rtx5090 que usa el resto del repo.

    PDF ──pdf_to_markdown──▶ md crudo
        ──clean_markdown────▶ md limpio (+ razones de descarte)   [se guarda a disco]
        ──analyze_document──▶ reporte: estrategia elegida + evidencia (§2–5 notebook)
        ──chunk_document────▶ chunks (con su metadata estructural)
        ──embed_chunks──────▶ vectores (TEI, rtx5090)
        ──replace_document──▶ upsert por `source` en pgvector (NO hace DROP)

Diseño:
  * Cada etapa es una función pequeña y testeable; la orquestación (`ingest_pdf`)
    sólo las encadena y reporta progreso por un callback.
  * Ingesta INCREMENTAL: `ensure_schema` crea la tabla si falta (nunca la borra) y
    `replace_document` borra las filas previas de ESE documento antes de reinsertar,
    así re-subir un PDF lo reemplaza limpio sin tocar el resto del corpus.
  * El esquema de la tabla vive aquí (única fuente de verdad); `legal_rag.py` lo
    reutiliza para su ruta de reconstrucción completa.

Nada de esto es específico del app: el CLI (`ingest_documents.py`), el app
(`apps/rewrite_lab`) y los notebooks pueden importar estas funciones.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from shared.legal_chunking import (
    ARTICLE_RE,
    HEADING_RE,
    MAX_WORDS,
    article_density,
    article_label_issues,
    chunk_documents,
    clean_document,
    document_strategy,
    semantic_units,
    words,
)
from shared.tei_client import TEIClient

# ── Esquema de la tabla de vectores (única fuente de verdad) ──────────────────────
# La metadata estructural viaja en columnas propias para poder filtrar por artículo
# o sección; `text` guarda EXACTAMENTE lo que se embebió (prefijo Fuente:/Sección:).
META_COLS = ["title", "hierarchy", "unit_type", "position", "part", "words"]
COPY_COLS = ["source", *META_COLS, "text", "model", "embedding"]


def create_table_sql(table: str, dim: int) -> str:
    """DDL de la tabla de chunks+vectores. `table`/`dim` son de código, nunca entrada
    de usuario (un nombre de tabla no puede parametrizarse con %s)."""
    return (
        f"CREATE TABLE IF NOT EXISTS {table} ("
        f"id bigserial PRIMARY KEY, source text, title text, hierarchy text, "
        f"unit_type text, position int, part int, words int, "
        f"text text, model text, embedding vector({dim}))"
    )


def ensure_table(cursor, table: str, dim: int) -> None:
    """Crea la tabla (sin índice) si no existe. Idempotente y sin DROP."""
    cursor.execute(create_table_sql(table, dim))


def ensure_index(cursor, table: str) -> None:
    """Crea el índice ANN (HNSW, coseno) si no existe. Se separa de `ensure_table`
    a propósito: construir el HNSW DESPUÉS de un bulk COPY (tabla llena) es más rápido
    que insertar en una tabla ya indexada — el patrón recomendado por pgvector para
    una reconstrucción. En la ingesta incremental el índice ya existe, así que llamar
    a esto es un no-op barato."""
    cursor.execute(
        f"CREATE INDEX IF NOT EXISTS {table}_embedding_hnsw "
        f"ON {table} USING hnsw (embedding vector_cosine_ops)"
    )


def ensure_schema(cursor, table: str, dim: int) -> None:
    """Tabla + índice si no existen. Conveniencia para la ruta INCREMENTAL, donde la
    tabla suele existir ya (el índice es un no-op) y el volumen por documento es
    pequeño. Para una reconstrucción completa usa `ensure_table` → COPY → `ensure_index`
    y así el índice se construye una sola vez sobre la tabla llena."""
    ensure_table(cursor, table, dim)
    ensure_index(cursor, table)


def table_vector_dim(cursor, table: str) -> int | None:
    """Dimensión del vector de una tabla existente, o None si la tabla no existe.

    Sirve para GUARDAR compatibilidad: insertar vectores de otra dimensión (otro
    embedder) en una tabla existente corrompería la búsqueda. pgvector guarda la
    dimensión declarada directamente en `atttypmod` (a diferencia de varchar, que le
    suma 4); un valor -1 significa `vector` sin dimensión fija."""
    cursor.execute(
        "SELECT a.atttypmod FROM pg_attribute a "
        "JOIN pg_class c ON c.oid = a.attrelid "
        "WHERE c.relname = %s AND a.attname = 'embedding'",
        (table.split(".")[-1],),
    )
    row = cursor.fetchone()
    return int(row[0]) if row and row[0] and row[0] > 0 else None


def distinct_sources(cursor, table: str) -> set[str]:
    """Documentos (`source`) ya presentes en la tabla. Vacío si la tabla no existe."""
    cursor.execute(
        "SELECT to_regclass(%s)", (table,)
    )
    if cursor.fetchone()[0] is None:
        return set()
    cursor.execute(f"SELECT DISTINCT source FROM {table}")
    return {r[0] for r in cursor.fetchall()}


def copy_rows(cursor, table: str, chunks: pd.DataFrame, vectors: np.ndarray, model: str) -> None:
    """COPY de cada chunk + su metadata + su vector. Reutilizado por la ingesta
    incremental y por la reconstrucción completa de `legal_rag.py`."""
    with cursor.copy(f"COPY {table} ({', '.join(COPY_COLS)}) FROM STDIN") as copy:
        for row, vector in zip(chunks.itertuples(index=False), vectors):
            copy.write_row((
                row.source, row.title, row.hierarchy, row.unit_type,
                int(row.position), int(row.part), int(row.words),
                row.text_for_embedding, model, vector,
            ))


def replace_document(cursor, table: str, source: str,
                     chunks: pd.DataFrame, vectors: np.ndarray, model: str) -> None:
    """Upsert por documento: borra las filas previas de `source` y reinserta.

    Re-subir un PDF lo reemplaza limpio; los demás documentos quedan intactos. La
    tabla debe existir ya (`ensure_schema`)."""
    cursor.execute(f"DELETE FROM {table} WHERE source = %s", (source,))
    copy_rows(cursor, table, chunks, vectors, model)


# ── Etapas del pipeline (una responsabilidad cada una) ────────────────────────────
def pdf_to_markdown(pdf_path: str | Path) -> str:
    """PDF → Markdown con pymupdf4llm (mantiene encabezados/tablas, que el chunker
    usa para hallar fronteras). Import perezoso: sólo la conversión necesita el extra
    `parse`, no el resto del pipeline."""
    import pymupdf4llm

    return pymupdf4llm.to_markdown(str(pdf_path))


def url_to_markdown(url: str, *, timeout: float = 60.0) -> str:
    """Descarga una URL y la convierte a Markdown con el MISMO motor que los PDFs
    (PyMuPDF + pymupdf4llm). Sirve para páginas HTML y también para links directos a
    PDF (PyMuPDF abre ambos). Así todo lo de aguas abajo (limpieza, chunking, embeddings)
    es idéntico sea cual sea el formato de origen. Imports perezosos."""
    import httpx
    import pymupdf
    import pymupdf4llm

    headers = {"User-Agent": "Mozilla/5.0 (RAG-lab ingest)"}
    r = httpx.get(url, follow_redirects=True, timeout=timeout, headers=headers)
    r.raise_for_status()
    ctype = (r.headers.get("content-type") or "").lower()
    # PyMuPDF necesita saber el formato del stream. PDF por content-type o extensión;
    # cualquier otra cosa se trata como HTML (Gutenberg, doctrina en web, etc.).
    is_pdf = "application/pdf" in ctype or url.split("?")[0].lower().endswith(".pdf")
    filetype = "pdf" if is_pdf else "html"
    doc = pymupdf.open(stream=r.content, filetype=filetype)
    try:
        return pymupdf4llm.to_markdown(doc)
    finally:
        doc.close()


def clean_markdown(raw_md: str) -> dict:
    """Limpieza conservadora (paratexto editorial, folios, índices…). Devuelve
    {'clean_text', 'removed_by_reason'}. Envuelve `legal_chunking.clean_document`."""
    return clean_document(raw_md)


def analyze_document(source: str, clean_text: str) -> dict:
    """Reporte 'qué se probó y qué estrategia ganó' para UN documento ya limpio.

    Reproduce el razonamiento de las secciones 2–5 del notebook de exploración: qué
    estrategia de chunking eligió el clasificador y POR QUÉ (densidad de artículos,
    #encabezados), más la distribución de tamaños de las unidades. No re-implementa
    nada: llama a las mismas funciones que la ingesta real."""
    strategy = document_strategy(clean_text)
    n_articles = len(ARTICLE_RE.findall(clean_text))
    n_headings = len(HEADING_RE.findall(clean_text))
    density = round(article_density(clean_text), 2)

    units = list(semantic_units(source, clean_text))
    unit_words = sorted(u["words"] for u in units) or [0]
    unit_types: dict[str, int] = {}
    for u in units:
        unit_types[u["unit_type"]] = unit_types.get(u["unit_type"], 0) + 1

    def pct(p: float) -> int:
        return int(np.percentile(unit_words, p)) if unit_words else 0

    return {
        "source": source,
        "clean_words": words(clean_text),
        "strategy": strategy,
        "strategy_reason": _strategy_reason(strategy, n_articles, density, n_headings),
        "candidates": _candidate_scoreboard(n_articles, density, n_headings),
        "article_count": n_articles,
        "article_density": density,
        "heading_count": n_headings,
        "n_units": len(units),
        "unit_type_counts": unit_types,
        "unit_words_p50": pct(50),
        "unit_words_p90": pct(90),
        "unit_words_max": max(unit_words),
        "oversized_units": sum(1 for w in unit_words if w > MAX_WORDS),
        # Aviso de calidad del tagueo: etiquetas con OCR sin resolver o duplicados no
        # explicados por transitorios. Vacío = tagueo sano. La UI lo muestra al ingerir.
        "label_warnings": article_label_issues(units),
    }


def _strategy_reason(strategy: str, n_articles: int, density: float, n_headings: int) -> str:
    """Frase legible con la razón de la elección (misma regla que document_strategy)."""
    if strategy == "article":
        return (f"Es una ley/código: {n_articles} artículos con densidad {density}/1000 palabras "
                f"(≥10 artículos y densidad ≥2.0). Cada artículo es un chunk atómico.")
    if strategy == "heading":
        return (f"Doctrina estructurada: {n_headings} encabezados Markdown (≥3) y densidad de "
                f"artículos baja ({density}). Se parte por secciones/encabezados.")
    return (f"Prosa sin estructura fuerte: {n_headings} encabezados y {n_articles} artículos "
            f"(densidad {density}). Se parte por párrafos.")


def _candidate_scoreboard(n_articles: int, density: float, n_headings: int) -> list[dict]:
    """Las 3 estrategias 'probadas' y si cada una calificaba — para mostrar en la UI
    el 'qué se probó', no sólo la ganadora."""
    return [
        {"strategy": "article", "qualifies": n_articles >= 10 and density >= 2.0,
         "evidence": f"{n_articles} artículos · densidad {density} (umbral: ≥10 y ≥2.0)"},
        {"strategy": "heading", "qualifies": n_headings >= 3,
         "evidence": f"{n_headings} encabezados (umbral: ≥3)"},
        {"strategy": "paragraph", "qualifies": True,
         "evidence": "siempre aplica (respaldo por párrafos)"},
    ]


def chunk_document(source: str, clean_text: str) -> pd.DataFrame:
    """Texto limpio de UN documento → chunks con metadata. Envuelve el pipeline
    completo de `legal_chunking` (unidades → fusión → partición) sobre {source: texto}."""
    return chunk_documents({source: clean_text})


def embed_chunks(tei: TEIClient, chunks: pd.DataFrame) -> np.ndarray:
    """Vectores L2-normalizados de los chunks, con el modelo servido por TEI."""
    if chunks.empty:
        return np.empty((0, 0), dtype=np.float32)
    return tei.embed(chunks["text_for_embedding"].tolist(), use_cache=bool(tei.cache_dir))


# ── Orquestación por documento ────────────────────────────────────────────────────
Progress = Callable[[str, str], None]   # (stage, human_message) -> None


def _noop(_stage: str, _message: str) -> None:
    pass


@dataclass
class IngestResult:
    """Resultado de ingerir un PDF: el reporte del clasificador + números de la corrida."""
    source: str
    pdf_name: str
    clean_path: str | None = None
    n_chunks: int = 0
    inserted: bool = False
    replaced_existing: bool = False
    model: str | None = None
    report: dict = field(default_factory=dict)
    error: str | None = None


def source_name(pdf_path: str | Path) -> str:
    """`source` canónico de un PDF: `<stem>.md` — misma convención que el corpus ya
    ingestado (`read_markdown_dir` usa el nombre del .md), para que el upsert por
    `source` reemplace correctamente un documento reconvertido."""
    return Path(pdf_path).stem + ".md"


def source_name_from_url(url: str) -> str:
    """`source` canónico de una URL: el último segmento con sentido → `<stem>.md`. Así
    re-ingerir la misma URL reemplaza su versión previa (upsert por `source`). Si la URL
    no da un nombre útil, usa el host."""
    from urllib.parse import urlparse

    p = urlparse(url)
    stem = Path(p.path).stem or (p.netloc.replace(".", "_") if p.netloc else "documento")
    return stem + ".md"


def save_clean_markdown(clean_dir: str | Path, source: str, clean_text: str) -> Path:
    """Guarda el Markdown limpio para poder visualizarlo. Devuelve la ruta escrita."""
    clean_dir = Path(clean_dir)
    clean_dir.mkdir(parents=True, exist_ok=True)
    path = clean_dir / source
    path.write_text(clean_text, encoding="utf-8")
    return path


def assert_model_compatible(cursor, table: str, tei: TEIClient, vectors: np.ndarray) -> None:
    """Falla FUERTE si los vectores no caben en una tabla existente (otra dimensión =
    otro embedder). Evita corromper silenciosamente la búsqueda al mezclar modelos."""
    if vectors.size == 0:
        return
    existing = table_vector_dim(cursor, table)
    if existing is not None and existing != vectors.shape[1]:
        raise ValueError(
            f"La tabla '{table}' guarda vectores de dimensión {existing}, pero el "
            f"embedder actual ({tei.model_id}) produce {vectors.shape[1]}. Sirve el "
            f"mismo modelo con el que se creó la tabla, o ingesta a una tabla nueva."
        )


def _ingest_markdown(result: IngestResult, raw_md: str, *, table: str, tei: TEIClient,
                     connect_fn, clean_dir: str | Path, save_clean: bool,
                     dry_run: bool, progress: Progress) -> IngestResult:
    """Etapas comunes a cualquier origen (PDF, URL, …) a partir del Markdown crudo:
    limpieza → análisis → chunking → embeddings → upsert. `result` ya trae `source`."""
    source = result.source
    try:
        progress("clean", "Limpiando (folios, paratexto editorial, índices)…")
        cleaned = clean_markdown(raw_md)
        clean_text = cleaned["clean_text"]
        if save_clean:
            result.clean_path = str(save_clean_markdown(clean_dir, source, clean_text))

        progress("analyze", "Clasificando estrategia de chunking…")
        report = analyze_document(source, clean_text)
        report["removed_by_reason"] = cleaned["removed_by_reason"]
        result.report = report

        progress("chunk", f"Partiendo en chunks (estrategia: {report['strategy']})…")
        chunks = chunk_document(source, clean_text)
        result.n_chunks = len(chunks)
        report["n_chunks"] = len(chunks)
        if not chunks.empty:
            report["chunk_words_mean"] = int(chunks["words"].mean())
            report["chunk_words_max"] = int(chunks["words"].max())

        if dry_run or chunks.empty:
            progress("done", "Listo (dry-run: sin insertar)." if dry_run else "Sin chunks.")
            return result

        progress("embed", f"Embebiendo {len(chunks)} chunks con {tei.model_id} (rtx5090)…")
        vectors = embed_chunks(tei, chunks)
        result.model = tei.model_id

        progress("insert", f"Insertando en '{table}' (upsert por documento)…")
        with connect_fn() as conn, conn.cursor() as cur:
            existing = distinct_sources(cur, table)
            result.replaced_existing = source in existing
            assert_model_compatible(cur, table, tei, vectors)
            ensure_schema(cur, table, vectors.shape[1])
            replace_document(cur, table, source, chunks, vectors, tei.model_id)
            conn.commit()
        result.inserted = True
        progress("done", f"✓ {len(chunks)} chunks insertados"
                          + (" (reemplazó versión previa)" if result.replaced_existing else "") + ".")
    except Exception as exc:   # noqa: BLE001 — el reporte por-archivo captura el error para la UI/CLI
        result.error = f"{type(exc).__name__}: {exc}"
        progress("error", result.error)
    return result


def ingest_pdf(pdf_path: str | Path, *, table: str, tei: TEIClient, connect_fn,
               clean_dir: str | Path, save_clean: bool = True,
               dry_run: bool = False, progress: Progress = _noop) -> IngestResult:
    """Encadena todas las etapas para UN PDF, reportando progreso por `progress`.

    `connect_fn` es una fábrica de conexiones (p. ej. `shared.db.connect`) — se
    inyecta para poder testear y para que el app comparta su propia config. En
    `dry_run` se hace todo menos tocar la BD (útil para ver el reporte sin insertar)."""
    pdf_path = Path(pdf_path)
    result = IngestResult(source=source_name(pdf_path), pdf_name=pdf_path.name, model=None)
    try:
        progress("convert", f"Convirtiendo {pdf_path.name} a Markdown…")
        raw_md = pdf_to_markdown(pdf_path)
    except Exception as exc:   # noqa: BLE001
        result.error = f"{type(exc).__name__}: {exc}"
        progress("error", result.error)
        return result
    return _ingest_markdown(result, raw_md, table=table, tei=tei, connect_fn=connect_fn,
                            clean_dir=clean_dir, save_clean=save_clean, dry_run=dry_run,
                            progress=progress)


def ingest_md(md_path: str | Path, *, table: str, tei: TEIClient, connect_fn,
              clean_dir: str | Path, save_clean: bool = True,
              dry_run: bool = False, progress: Progress = _noop) -> IngestResult:
    """Igual que `ingest_pdf` pero desde un archivo Markdown ya existente: como el
    origen YA es Markdown, se salta la conversión y se lee tal cual, siguiendo el mismo
    camino aguas abajo (limpieza → chunking → embeddings → upsert). El `source` sale del
    nombre del archivo, así re-subir el mismo `.md` reemplaza su versión previa."""
    md_path = Path(md_path)
    result = IngestResult(source=source_name(md_path), pdf_name=md_path.name, model=None)
    try:
        progress("convert", f"Leyendo {md_path.name} (ya es Markdown)…")
        raw_md = md_path.read_text(encoding="utf-8")
    except Exception as exc:   # noqa: BLE001
        result.error = f"{type(exc).__name__}: {exc}"
        progress("error", result.error)
        return result
    return _ingest_markdown(result, raw_md, table=table, tei=tei, connect_fn=connect_fn,
                            clean_dir=clean_dir, save_clean=save_clean, dry_run=dry_run,
                            progress=progress)


def ingest_url(url: str, *, table: str, tei: TEIClient, connect_fn,
               clean_dir: str | Path, save_clean: bool = True,
               dry_run: bool = False, progress: Progress = _noop) -> IngestResult:
    """Igual que `ingest_pdf` pero desde una URL: descarga + convierte a Markdown
    (HTML o PDF) y sigue el mismo camino. El `source` sale del último segmento de la URL,
    así re-ingerir la misma URL reemplaza su versión previa."""
    result = IngestResult(source=source_name_from_url(url), pdf_name=url, model=None)
    try:
        progress("convert", f"Descargando y convirtiendo {url} …")
        raw_md = url_to_markdown(url)
    except Exception as exc:   # noqa: BLE001
        result.error = f"{type(exc).__name__}: {exc}"
        progress("error", result.error)
        return result
    return _ingest_markdown(result, raw_md, table=table, tei=tei, connect_fn=connect_fn,
                            clean_dir=clean_dir, save_clean=save_clean, dry_run=dry_run,
                            progress=progress)
