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

HERE = Path(__file__).parent
MD_DIR = HERE / "out" / "Root Apical Meristem"
DOCX = HERE / "pdfs" / "Root Apical Meristem" / "RAM 20 questions.docx"
TABLE = "ram_chunks"


# ── corpus ──────────────────────────────────────────────────────────────────────
def load_markdown() -> list[tuple[str, str]]:
    return [(p.stem, p.read_text()) for p in sorted(MD_DIR.glob("*.md"))]


_REF_HEADING = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:\*+\s*)?(references|bibliography|literature cited|works cited)\b",
    re.I | re.M,
)


def clean_text(md: str) -> str:
    """Drop everything from the first 'References'/'Bibliography' heading onward."""
    m = _REF_HEADING.search(md)
    return md[: m.start()] if m else md


# Common English function words. Prose is full of them; reference-LIST entries
# (names + titles + journal/volume/page numbers) have very few.
_STOP = {
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
    words = text.split()
    nwords = max(1, len(words))
    toks = re.findall(r"[a-z]+", text.lower())
    stop_ratio = sum(t in _STOP for t in toks) / max(1, len(toks))
    initials = len(re.findall(r"\b[A-Z]\.", text)) / nwords * 100      # per 100 words
    pageranges = len(re.findall(r"\b\d+\s*[e\-–]\s*\d+\b", text)) / nwords * 100
    prose_deficit = max(0.0, 0.18 - stop_ratio) * 100  # how far BELOW normal prose
    return initials + pageranges * 2.0 + prose_deficit


def is_ref_chunk(text: str, thresh: float = 8.0) -> bool:
    # need real content to judge; very short chunks are never flagged
    return len(text.split()) >= 8 and ref_density(text) >= thresh


def chunk_words(text: str, size: int = 150, overlap: int = 25) -> list[str]:
    """Fixed-size word windows with overlap — robust for long, messy paper text."""
    words = text.split()
    step = max(1, size - overlap)
    out = []
    for start in range(0, len(words), step):
        piece = words[start : start + size]
        if piece:
            out.append(" ".join(piece))
        if start + size >= len(words):
            break
    return out


def load_questions() -> list[str]:
    """Pull the questions out of the .docx (every paragraph ending in '?')."""
    xml = zipfile.ZipFile(DOCX).read("word/document.xml").decode("utf-8", "ignore")
    xml = re.sub(r"</w:p>", "\n", xml)
    plain = html.unescape(re.sub(r"<[^>]+>", "", xml))
    return [ln.strip() for ln in plain.split("\n") if ln.strip().endswith("?")]


# ── ingest ──────────────────────────────────────────────────────────────────────
def build_chunks(clean: bool) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for src, text in load_markdown():
        body = clean_text(text) if clean else text
        for ch in chunk_words(body):
            if clean and is_ref_chunk(ch):
                continue  # drop leftover citation-dense chunks
            rows.append((src, ch))
    return rows


def ingest(model: str, clean: bool = False) -> int:
    embedder = get_embedder(model)
    rows = build_chunks(clean)
    print(f"{len(rows)} chunks (clean={clean}); embedding with "
          f"{embedder.name} ({embedder.dim}d)...")
    vecs = embedder.encode([c for _, c in rows])
    with connect() as conn, conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {TABLE}")
        cur.execute(f"CREATE TABLE {TABLE} (id bigserial PRIMARY KEY, source text, "
                    f"text text, embedding vector({embedder.dim}))")
        with cur.copy(f"COPY {TABLE} (source, text, embedding) FROM STDIN") as copy:
            for (src, ch), v in zip(rows, vecs):
                copy.write_row((src, ch, v))
        conn.commit()
    return len(rows)


# ── retrieve ────────────────────────────────────────────────────────────────────
def retrieve(embedder, question: str, k: int) -> list[tuple]:
    qv = embedder.encode([question])[0]
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT source, text, embedding <=> %s AS dist FROM {TABLE} "
            f"ORDER BY dist LIMIT %s", (qv, k))
        return cur.fetchall()


def _show(question: str, results: list[tuple]) -> None:
    print(f"\nQ: {question}")
    for src, text, dist in results:
        flag = "  ⚠ref" if is_ref_chunk(text) else ""
        snippet = re.sub(r"\s+", " ", text)[:150]
        print(f"   • {dist:.3f}  [{src}]{flag}  {snippet}...")


def ask(model: str, question: str, k: int) -> None:
    _show(question, retrieve(get_embedder(model), question, k))


def askall(model: str, k: int) -> None:
    embedder = get_embedder(model)
    for q in load_questions():
        _show(q, retrieve(embedder, q, k))


# ── experiment: one config, measured ────────────────────────────────────────────
def run_config(model: str, clean: bool, k: int = 3) -> dict:
    """Ingest with this (model, clean), run all questions, return metrics.
    ref_noise@k = fraction of retrieved chunks that are bibliography fragments."""
    n_chunks = ingest(model, clean)
    embedder = get_embedder(model)
    questions = load_questions()
    dists, ref_hits, total = [], 0, 0
    examples = []
    for q in questions:
        res = retrieve(embedder, q, k)
        dists.append(res[0][2])
        for _, txt, _ in res:
            total += 1
            ref_hits += is_ref_chunk(txt)
        examples.append((q, res))
    return {
        "config": f"{model}{' +clean' if clean else ' (raw)'}",
        "model": model, "clean": clean, "n_chunks": n_chunks,
        "avg_top1_dist": sum(dists) / len(dists),
        "ref_noise": ref_hits / total,
        "examples": examples,
    }


CONFIGS = [("minilm", False), ("minilm", True), ("bge-small", True)]


def compare(k: int = 3) -> list[dict]:
    rows = [run_config(m, c, k) for m, c in CONFIGS]
    print(f"\n{'config':<18}{'#chunks':>8}{'avg top-1 dist':>16}{'ref-noise@'+str(k):>14}")
    print("-" * 56)
    for r in rows:
        print(f"{r['config']:<18}{r['n_chunks']:>8}{r['avg_top1_dist']:>16.3f}{r['ref_noise']:>14.1%}")
    print("\nNote: avg distance is only comparable WITHIN a model (minilm raw vs clean);")
    print("ref-noise is comparable across all three.")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description="RAG over the Root Apical Meristem papers")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pi = sub.add_parser("ingest")
    pi.add_argument("--model", default="bge-small")
    pi.add_argument("--clean", action="store_true")
    pa = sub.add_parser("ask")
    pa.add_argument("question")
    pa.add_argument("--model", default="bge-small")
    pa.add_argument("--k", type=int, default=3)
    pl = sub.add_parser("askall")
    pl.add_argument("--model", default="bge-small")
    pl.add_argument("--k", type=int, default=3)
    pc = sub.add_parser("compare")
    pc.add_argument("--k", type=int, default=3)
    args = ap.parse_args()
    if args.cmd == "ingest":
        n = ingest(args.model, args.clean)
        print(f"✓ stored {n} chunks in '{TABLE}'.")
    elif args.cmd == "ask":
        ask(args.model, args.question, args.k)
    elif args.cmd == "askall":
        askall(args.model, args.k)
    else:
        compare(args.k)


if __name__ == "__main__":
    main()
