"""
Ingesta del corpus jurídico (Sistema Penal Acusatorio) a pgvector.

Gemelo de `ram_rag.py`, pero para leyes/doctrina: en vez de limpieza de papers +
chunking de tamaño fijo, usa el chunking POR ESTRUCTURA validado en el notebook de
exploración y extraído a `shared.legal_chunking` (probado en `tests/`):

    Markdown → clean_corpus → chunk_documents → embed → pgvector → retrieve

A diferencia de `ram_rag.py`, guarda la metadata estructural de cada chunk
(`title`, `hierarchy`, `unit_type`, `position`, `part`) en columnas propias, para
poder filtrar/mostrar por artículo o sección.

Embeddings: por defecto el modelo servido por TEI (Qwen3-Embedding). Reutiliza la
misma caché en disco que los notebooks (`exploracion_datos/.embed_cache`), así que si
ya embediste esos chunks ahí, la ingesta es instantánea y no vuelve a tocar el túnel.

Uso (túnel a Postgres arriba; TEI arriba para embeber/consultar):
    uv run python ingestion/legal_rag.py ingest
    uv run python ingestion/legal_rag.py ask "¿Qué tipos de medidas cautelares hay?" --k 5
    uv run python ingestion/legal_rag.py count
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, ".")
from ingestion.pipeline import copy_rows, ensure_index, ensure_table
from shared.db import connect
from shared.legal_chunking import chunk_documents, clean_corpus, read_markdown_dir
from shared.lexical import BM25, rank_indices_by_score, rrf, tokenize
from shared.llm_client import LlamaClient
from shared.tei_client import TEIClient

LAB_DIR = Path(__file__).parent
CORPUS_DIR = LAB_DIR / "out" / "Sistema Penal Acusatorio"
CACHE_DIR = LAB_DIR.parent / "exploracion_datos" / ".embed_cache"

CORPUS = "sistema_penal"
MODEL_ALIAS = "qwen06"   # alias corto para el nombre de tabla; el id real va en la columna `model`
CHUNKER = "legal"

# Qwen3-Embedding rinde mejor con una instrucción en la consulta (no en los documentos).
Q_INSTRUCT = "Instruct: Recupera el pasaje del código o la doctrina que responde la pregunta.\nQuery: "


def table_name(corpus: str = CORPUS, model: str = MODEL_ALIAS, chunker: str = CHUNKER) -> str:
    """Convención de nombres de tabla del repo: {corpus}__{model}__{chunker},
    cada tramo normalizado a un identificador seguro de Postgres (minúsculas,
    no-alfanuméricos → '_'). Ver ram_rag.table_name para el porqué."""
    def slug(part: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", part.lower()).strip("_")
    return f"{slug(corpus)}__{slug(model)}__{slug(chunker)}"


# ── pipeline: chunk → embed → store ──────────────────────────────────────────────
def build_chunks():
    """Corpus Markdown → DataFrame de chunks por estructura (con su metadata)."""
    documents = clean_corpus(read_markdown_dir(CORPUS_DIR))
    return chunk_documents(documents)


def store_chunks(chunks, vectors, dim: int, model: str, table: str) -> None:
    """Recrea `table` y hace COPY de cada chunk + su vector + su metadata.

    `text` guarda el `text_for_embedding` (con el prefijo Fuente:/Sección:), que es
    EXACTAMENTE lo que se embebió, para que la recuperación sea consistente. La
    metadata estructural va en columnas propias para poder filtrar por artículo.

    `table` se interpola directo en el SQL (un nombre de tabla no puede ir como
    parámetro %s), así que debe ser un nombre de código, nunca entrada de usuario.
    """
    # Reconstrucción completa: se borra la tabla y se recrea desde cero. El esquema,
    # el índice ANN y el COPY viven en `ingestion.pipeline` (única fuente de verdad),
    # compartidos con la ingesta incremental del app/CLI. Orden deliberado —tabla →
    # COPY → índice— para construir el HNSW una sola vez sobre la tabla ya llena.
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
        ensure_table(cursor, table, dim)
        copy_rows(cursor, table, chunks, vectors, model)
        ensure_index(cursor, table)
        connection.commit()


def ingest(table: str | None = None) -> int:
    """chunk → embed → store. Devuelve cuántos chunks se guardaron."""
    table = table or table_name()
    tei = TEIClient(cache_dir=CACHE_DIR)
    chunks = build_chunks()
    print(f"chunks: {len(chunks)} · embediendo con {tei.model_id} (usa caché si existe)...")
    vectors = tei.embed(chunks["text_for_embedding"].tolist())
    store_chunks(chunks, vectors, vectors.shape[1], tei.model_id, table)
    return len(chunks)


# ── retrieve ─────────────────────────────────────────────────────────────────────
def retrieve(question: str, k: int, table: str, tei: TEIClient) -> list[tuple]:
    """k chunks más cercanos (coseno) → (source, title, hierarchy, text, dist)."""
    qvec = tei.embed([Q_INSTRUCT + question], use_cache=False)[0]
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            f"SELECT source, title, hierarchy, text, embedding <=> %s AS dist "
            f"FROM {table} ORDER BY dist LIMIT %s", (qvec, k))
        return cursor.fetchall()


def retrieve_hybrid(question: str, k: int, table: str, tei: TEIClient,
                    n_dense: int = 100, rrf_k: int = 60) -> list[tuple]:
    """Denso (pgvector) + BM25 (léxico, en memoria) fusionados con RRF.

    El denso resuelve paráfrasis; BM25 rescata las preguntas que comparten términos
    jurídicos con la respuesta aunque no la frase exacta. RRF combina ambos rankings
    sin normalizar escalas. Devuelve (source, title, hierarchy, text, tag), donde tag
    indica qué recuperador(es) trajeron el chunk: 'D' denso, 'L' léxico, 'DL' ambos.

    BM25 se arma al vuelo sobre los textos de la tabla (~3.6k chunks, <1s). Para un
    servicio de alto tráfico convendría persistir el índice; aquí prioriza claridad.
    """
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(f"SELECT id, source, title, hierarchy, text FROM {table}")
        rows = cursor.fetchall()
    ids = [r[0] for r in rows]
    texts = [r[4] for r in rows]
    meta = {r[0]: r for r in rows}

    # Denso: top-N por distancia coseno en pgvector.
    qvec = tei.embed([Q_INSTRUCT + question], use_cache=False)[0]
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            f"SELECT id FROM {table} ORDER BY embedding <=> %s LIMIT %s", (qvec, n_dense))
        dense_ids = [r[0] for r in cursor.fetchall()]

    # Léxico: BM25 sobre la pregunta cruda (sin la instrucción de Qwen).
    bm25 = BM25([tokenize(t) for t in texts])
    lexical_ids = [ids[i] for i in rank_indices_by_score(bm25.scores(tokenize(question)))[:n_dense]]

    fused = rrf([dense_ids, lexical_ids], k=rrf_k)[:k]
    dense_set, lexical_set = set(dense_ids), set(lexical_ids)
    out = []
    for cid in fused:
        _, source, title, hierarchy, text = meta[cid]
        tag = ("D" if cid in dense_set else "") + ("L" if cid in lexical_set else "")
        out.append((source, title, hierarchy, text, tag))
    return out


def retrieve_rerank(question: str, k: int, table: str, tei: TEIClient,
                    candidates: int = 50) -> list[tuple]:
    """BM25 genera candidatos (léxico, local) y un cross-encoder los reordena vía
    /rerank. Sirve cuando TEI tiene servido el RERANKER (no el embedder), así que no
    necesita vector de consulta. Devuelve (source, title, hierarchy, text, score)."""
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(f"SELECT source, title, hierarchy, text FROM {table}")
        rows = cursor.fetchall()
    texts = [r[3] for r in rows]
    bm25 = BM25([tokenize(t) for t in texts])
    cand_idx = rank_indices_by_score(bm25.scores(tokenize(question)))[:candidates]
    cand = [rows[i] for i in cand_idx]
    ranked = tei.rerank(question, [c[3] for c in cand])[:k]
    return [(*cand[i][:4], f"{score:.2f}") for i, score in ranked]


def _dense_ids(question: str, table: str, tei: TEIClient, n: int, cursor) -> list[int]:
    qvec = tei.embed([Q_INSTRUCT + question], use_cache=False)[0]
    cursor.execute(f"SELECT id FROM {table} ORDER BY embedding <=> %s LIMIT %s", (qvec, n))
    return [r[0] for r in cursor.fetchall()]


def retrieve_multiquery(question: str, k: int, table: str, tei: TEIClient,
                        llm: LlamaClient, n: int = 100) -> list[tuple]:
    """Multi-query: reescribe la pregunta a jurídico y recupera con la ORIGINAL y la
    REESCRITA, uniendo los candidatos densos por RRF. Duplica el recall del pool
    (0.40→0.80 @50 en el eval) porque cubre tanto el registro coloquial como el
    jurídico — sin arriesgar: la original siempre está incluida.

    Requiere el embedder (TEI) y el llama-server (LLM_URL) alcanzables."""
    rewrite = llm.rewrite_legal(question)
    print(f"   ↳ rewrite: {rewrite}")
    with connect() as connection, connection.cursor() as cursor:
        orders = [_dense_ids(q, table, tei, n, cursor) for q in (question, rewrite)]
        fused = rrf(orders)[:k]
        meta = {}
        cursor.execute(f"SELECT id, source, title, hierarchy, text FROM {table} WHERE id = ANY(%s)", (fused,))
        for row in cursor.fetchall():
            meta[row[0]] = row
    orig_set, rw_set = set(orders[0]), set(orders[1])
    out = []
    for cid in fused:
        _, source, title, hierarchy, text = meta[cid]
        tag = ("O" if cid in orig_set else "") + ("R" if cid in rw_set else "")
        out.append((source, title, hierarchy, text, tag))
    return out


def ask(question: str, k: int, table: str | None = None, mode: str = "hybrid") -> None:
    table = table or table_name()
    tei = TEIClient(cache_dir=CACHE_DIR)
    print(f"\nQ: {question}   [{mode}]")
    if mode == "dense":
        results = [(s, t, h, txt, f"{d:.3f}") for s, t, h, txt, d in retrieve(question, k, table, tei)]
    elif mode == "rerank":
        results = retrieve_rerank(question, k, table, tei)
    elif mode == "multiquery":
        results = retrieve_multiquery(question, k, table, tei, LlamaClient())
    else:
        results = retrieve_hybrid(question, k, table, tei)
    for source, title, hierarchy, text, note in results:
        snippet = re.sub(r"\s+", " ", text)[:150]
        print(f"   • {note:>6}  [{source} · {title}]  {snippet}...")


def count(table: str | None = None) -> None:
    table = table or table_name()
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(f"SELECT count(*), count(DISTINCT source) FROM {table}")
        n, docs = cursor.fetchone()
        cursor.execute(f"SELECT unit_type, count(*) FROM {table} GROUP BY unit_type ORDER BY 2 DESC")
        by_type = cursor.fetchall()
    print(f"tabla '{table}': {n} chunks de {docs} documentos")
    for unit_type, c in by_type:
        print(f"   {unit_type:<10} {c}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingesta RAG del corpus Sistema Penal Acusatorio")
    subparsers = parser.add_subparsers(dest="cmd", required=True)
    subparsers.add_parser("ingest")
    ask_parser = subparsers.add_parser("ask")
    ask_parser.add_argument("question")
    ask_parser.add_argument("--k", type=int, default=5)
    ask_parser.add_argument("--mode", choices=["hybrid", "dense", "rerank", "multiquery"], default="hybrid")
    subparsers.add_parser("count")
    args = parser.parse_args()

    if args.cmd == "ingest":
        table = table_name()
        print(f"ingestando corpus penal → tabla '{table}' ...")
        n = ingest(table)
        print(f"✓ guardados {n} chunks en '{table}'.")
    elif args.cmd == "ask":
        ask(args.question, args.k, mode=args.mode)
    else:
        count()


if __name__ == "__main__":
    main()
