"""
Real-corpus demo + experiment — RAG over the Root Apical Meristem papers.

Ties the whole pipeline together on *real* documents:
    PDFs → (convert.py) → Markdown → clean → chunk → embed → pgvector → retrieve

The 20 questions (in `RAM 20 questions.docx`) are open-ended research questions
with no single gold answer, so this is a QUALITATIVE test. To make it measurable
we track a **reference-noise rate**: how often a retrieved chunk is actually a
bibliography fragment rather than content. That metric IS comparable across
embedding models (unlike raw cosine distance, whose scale differs per model).

Usage (tunnel open — Postgres; TEI too if --model tei):
    uv run python ingestion/ram_rag.py ingest --model bge-small --clean
    uv run python ingestion/ram_rag.py askall --model bge-small --k 3
    uv run python ingestion/ram_rag.py compare        # runs the A/B/C ablation
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, ".")
from shared.db import connect
from shared.embedder import get_embedder

LAB_DIR = Path(__file__).parent
MARKDOWN_DIR = LAB_DIR / "out" / "Root Apical Meristem"
QUESTIONS_DOCX = LAB_DIR / "pdfs" / "Root Apical Meristem" / "RAM 20 questions.docx"
CORPUS = "ram"  # etiqueta de corpus de este lab, para table_name(); el chunker aquí es siempre "fixed"


def table_name(corpus: str, model: str, chunker: str = "fixed") -> str:
    """Construye el nombre de la tabla de vectores para una combinación
    (corpus, model, chunker). Ésta es LA regla de nomenclatura, para que no se
    pierda:

        {corpus}__{model}__{chunker}

    Cada parte se normaliza a un identificador seguro de Postgres:
      * todo en minúsculas (Postgres pliega a minúsculas los identificadores sin
        comillas, así que `Penal` y `penal` serían la misma tabla),
      * cualquier tramo de caracteres no alfanuméricos ('-', '/', ':', '.',
        espacios, y también '_') colapsa a un solo '_'  — un '-' o '/' obligaría
        a poner comillas dobles o sería inválido en un identificador,
      * el separador entre ejes es '__' (doble '_'), para no confundirlo con el
        '_' que puede quedar dentro de un nombre compuesto (p. ej. 'bge_small').

    Usa alias CORTOS para el modelo (los de embedder.ALIASES: 'minilm',
    'bge-small', 'qwen06'…), no el id completo de HuggingFace. El nombre de tabla
    es sólo un identificador legible; la columna `model` de cada fila guarda el
    `embedder.name` exacto (ver store_chunks) como fuente de verdad.

    Regla dura detrás de la convención: distintos embedders producen vectores de
    distinta dimensión, que NO pueden convivir en una columna `vector(N)`; por eso
    el modelo va en el nombre. Corpus y chunker se incluyen para que cada
    experimento tenga su propia tabla (diseño 'tabla por config').

    >>> table_name("penal", "bge-small", "article")
    'penal__bge_small__article'
    >>> table_name("ram", "qwen06")
    'ram__qwen06__fixed'
    """
    def slug(part: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", part.lower()).strip("_")

    return f"{slug(corpus)}__{slug(model)}__{slug(chunker)}"


# ── corpus ──────────────────────────────────────────────────────────────────────
def load_markdown() -> list[tuple[str, str]]:
    """Read every converted paper → [(paper_name, full_markdown), ...]."""
    return [(path.stem, path.read_text()) for path in sorted(MARKDOWN_DIR.glob("*.md"))]


_REFERENCE_HEADING = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:\*+\s*)?(references|bibliography|literature cited|works cited)\b",
    re.I | re.M,
)


def remove_citation_block(markdown: str) -> str:
    """Drop everything from the first 'References'/'Bibliography' heading onward."""
    heading = _REFERENCE_HEADING.search(markdown)
    return markdown[: heading.start()] if heading else markdown


# Common English function words. Prose is full of them; reference-LIST entries
# (names + titles + journal/volume/page numbers) have very few.
_STOPWORDS = {
    "the", "of", "and", "to", "in", "a", "is", "that", "for", "as", "with",
    "are", "by", "this", "on", "be", "it", "an", "or", "we", "which", "from",
    "at", "was", "were", "these", "can", "has", "have", "not", "but", "their",
    "such", "into", "than", "also", "how", "our", "its", "may",
}


def ref_density(text: str) -> float:
    """
    'Looks like a bibliography ENTRY' score — high for reference-list lines, low
    for prose that merely cites. Keys on what separates the two:
      * few stopwords (names/titles/numbers, not sentences)
      * many author initials  (V.A.  J.  A.F.M.)
      * journal page ranges    (1053e1057)
    In-text citations like "(Benkova et al. 2003)" sit inside normal sentences,
    so their stopword ratio stays high and they score LOW (kept).
    """
    word_count = max(1, len(text.split()))
    tokens = re.findall(r"[a-z]+", text.lower())
    stopword_ratio = sum(token in _STOPWORDS for token in tokens) / max(1, len(tokens))
    initials_per_100w = len(re.findall(r"\b[A-Z]\.", text)) / word_count * 100
    page_ranges_per_100w = len(re.findall(r"\b\d+\s*[e\-–]\s*\d+\b", text)) / word_count * 100
    prose_deficit = max(0.0, 0.18 - stopword_ratio) * 100  # how far BELOW normal prose
    return initials_per_100w + page_ranges_per_100w * 2.0 + prose_deficit


def is_ref_chunk(text: str, threshold: float = 20.0) -> bool:
    # need real content to judge; very short chunks are never flagged
    return len(text.split()) >= 8 and ref_density(text) >= threshold


def chunk_words(text: str, size: int = 150, overlap: int = 25) -> list[str]:
    """Fixed-size word windows with overlap — robust for long, messy paper text."""
    words = text.split()
    step = max(1, size - overlap)
    chunks = []
    for start in range(0, len(words), step):
        window = words[start : start + size]
        if window:
            chunks.append(" ".join(window))
        if start + size >= len(words):
            break
    return chunks


def load_questions() -> list[str]:
    """Pull the questions out of the .docx (every paragraph ending in '?')."""
    document_xml = zipfile.ZipFile(QUESTIONS_DOCX).read("word/document.xml").decode("utf-8", "ignore")
    document_xml = re.sub(r"</w:p>", "\n", document_xml)
    plain_text = html.unescape(re.sub(r"<[^>]+>", "", document_xml))
    return [line.strip() for line in plain_text.split("\n") if line.strip().endswith("?")]


# ── ingest ──────────────────────────────────────────────────────────────────────
# The pipeline is chunk → embed → store. Each step below is its own small
# function so a notebook can run and inspect them one at a time; `ingest()` is
# just the three composed in order.
def load_chunks(remove_citation: bool) -> list[tuple[str, str]]:
    """Corpus → [(source, chunk_text), ...]. With clean=True, strip the
    reference sections and drop any leftover citation-dense chunks."""
    chunks: list[tuple[str, str]] = []
    for src_name, text in load_markdown():
        body = remove_citation_block(text) if remove_citation else text
        # body = clean_text(text) if clean else text
        for chunk in chunk_words(body):
            # if clean and is_ref_chunk(chunk):
                # continue  # drop leftover citation-dense chunks
            chunks.append((src_name, chunk))
    return chunks

def remove_citation_chunks(chunks):
    out_chunks: list[tuple[str, str]] = []
    for chunk_obj in chunks:
        chunk = chunk_obj[1]
        if is_ref_chunk(chunk) == False:
            out_chunks.append(chunk_obj)
    return out_chunks
            




def embed_chunks(embedder, chunks: list[tuple[str, str]]):
    """Embed just the text of each (source, text) chunk → (n, dim) vectors."""
    return embedder.encode([text for _, text in chunks])


def store_chunks(chunks: list[tuple[str, str]], vectors, dim: int, model: str,
                 table: str) -> None:
    """Persist chunks + vectors into `table`: recreate it, then COPY every row in.

    `model` (the embedder's name) is written on every row, so the table records
    which embedder produced its vectors. That matters: vectors from different
    models live in different spaces and aren't comparable, so you need to know
    what a table was built with before you query it.

    NOTE: `table` is interpolated straight into the SQL (a table name can't be a
    bound %s parameter), so it must be a trusted, code-supplied name — never
    end-user input.
    """
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
        cursor.execute(
            f"CREATE TABLE {table} (id bigserial PRIMARY KEY, source text, "
            f"text text, model text, embedding vector({dim}))"
        )
        with cursor.copy(f"COPY {table} (source, text, model, embedding) FROM STDIN") as copy:
            for (source, text), vector in zip(chunks, vectors):
                copy.write_row((source, text, model, vector))
        connection.commit()


def ingest(model: str, remove_citations: bool = False, table: str | None = None) -> int:
    """chunk → embed → store, returning how many chunks landed in `table`.
    Si no se da `table`, se deriva con la convención: table_name("ram", model)."""
    if table is None:
        table = table_name(CORPUS, model, "fixed")
    embedder = get_embedder(model)
    chunks = load_chunks(remove_citations)
    if remove_citations:
        chunks = remove_citation_chunks(chunks)
    vectors = embed_chunks(embedder, chunks)
    store_chunks(chunks, vectors, embedder.dim, embedder.name, table)
    return len(chunks)


# ── retrieve ────────────────────────────────────────────────────────────────────
def retrieve(embedder, question: str, k: int, table: str) -> list[tuple]:
    """Return the k nearest (source, text, distance) chunks in `table`.

    `embedder` must be the same model the table was built with — mixing models
    compares vectors from different spaces and gives nonsense distances. The
    stored `model` column (see store_chunks) is how you'd check that."""
    query_vector = embedder.encode([question])[0]
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            f"SELECT source, text, embedding <=> %s AS dist FROM {table} "
            f"ORDER BY dist LIMIT %s", (query_vector, k))
        return cursor.fetchall()


def _show(question: str, results: list[tuple]) -> None:
    print(f"\nQ: {question}")
    for source, text, distance in results:
        flag = "  ⚠ref" if is_ref_chunk(text) else ""
        snippet = re.sub(r"\s+", " ", text)[:150]
        print(f"   • {distance:.3f}  [{source}]{flag}  {snippet}...")


def ask(model: str, question: str, k: int, table: str | None = None) -> None:
    if table is None:
        table = table_name(CORPUS, model, "fixed")
    _show(question, retrieve(get_embedder(model), question, k, table))


def askall(model: str, k: int, table: str | None = None) -> None:
    if table is None:
        table = table_name(CORPUS, model, "fixed")
    embedder = get_embedder(model)
    for question in load_questions():
        _show(question, retrieve(embedder, question, k, table))


# ── experiment: one config, measured ────────────────────────────────────────────
def score_questions(embedder, questions: list[str], k: int, table: str) -> dict:
    """Retrieve k chunks for every question against `table`, then measure
    retrieval quality. Assumes the table is already ingested.
      * avg_top1_dist — mean cosine distance of each question's best hit
      * ref_noise     — fraction of retrieved chunks that are citation fragments
    Returns those plus the raw (question, results) pairs for inspection."""
    top_distances, ref_chunk_count, retrieved_count, examples = [], 0, 0, []
    for question in questions:
        results = retrieve(embedder, question, k, table)
        top_distances.append(results[0][2])
        for _, text, _ in results:
            retrieved_count += 1
            ref_chunk_count += is_ref_chunk(text)
        examples.append((question, results))
    return {
        "avg_top1_dist": sum(top_distances) / len(top_distances),
        "ref_noise": ref_chunk_count / retrieved_count,
        "examples": examples,
    }


def evaluate_config(model: str, clean: bool, k: int = 3,
                    questions: list[str] | None = None,
                    table: str | None = None) -> dict:
    """Run one experiment configuration end to end: ingest with this
    (model, clean) into `table`, then score `questions` against it.
    `questions` defaults to the lab's 20; `table` defaults to the convention
    table_name("ram", model). Just ingest() + score_questions() with a label."""
    if questions is None:
        questions = load_questions()
    if table is None:
        table = table_name(CORPUS, model, "fixed")
    chunk_count = ingest(model, clean, table)
    embedder = get_embedder(model)
    scores = score_questions(embedder, questions, k, table)
    return {
        "config": f"{model}{' +clean' if clean else ' (raw)'}",
        "model": model, "clean": clean, "n_chunks": chunk_count,
        **scores,
    }


EXPERIMENT_CONFIGS = [("minilm", False), ("minilm", True), ("bge-small", True)]


def compare(k: int = 3) -> list[dict]:
    results = [evaluate_config(model, clean, k) for model, clean in EXPERIMENT_CONFIGS]
    print(f"\n{'config':<18}{'#chunks':>8}{'avg top-1 dist':>16}{'ref-noise@'+str(k):>14}")
    print("-" * 56)
    for result in results:
        print(f"{result['config']:<18}{result['n_chunks']:>8}"
              f"{result['avg_top1_dist']:>16.3f}{result['ref_noise']:>14.1%}")
    print("\nNote: avg distance is only comparable WITHIN a model (minilm raw vs clean);")
    print("ref-noise is comparable across all three.")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG over the Root Apical Meristem papers")
    subparsers = parser.add_subparsers(dest="cmd", required=True)
    ingest_parser = subparsers.add_parser("ingest")
    ingest_parser.add_argument("--model", default="bge-small")
    ingest_parser.add_argument("--clean", action="store_true")
    ask_parser = subparsers.add_parser("ask")
    ask_parser.add_argument("question")
    ask_parser.add_argument("--model", default="bge-small")
    ask_parser.add_argument("--k", type=int, default=3)
    askall_parser = subparsers.add_parser("askall")
    askall_parser.add_argument("--model", default="bge-small")
    askall_parser.add_argument("--k", type=int, default=3)
    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("--k", type=int, default=3)
    args = parser.parse_args()
    if args.cmd == "ingest":
        table = table_name(CORPUS, args.model, "fixed")
        print(f"ingesting with model={args.model} clean={args.clean} → tabla '{table}' ...")
        chunk_count = ingest(args.model, args.clean, table)
        print(f"✓ stored {chunk_count} chunks in '{table}'.")
    elif args.cmd == "ask":
        ask(args.model, args.question, args.k)
    elif args.cmd == "askall":
        askall(args.model, args.k)
    else:
        compare(args.k)


if __name__ == "__main__":
    main()
