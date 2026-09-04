"""
Lab 03 — Chunking, measured (on the real legal corpus).

Runs the SAME corpus and the SAME questions through several chunking strategies
and scores each on whether retrieval surfaces the right ARTICLE. Same embedder,
same retrieval — only the chunk boundaries change — so any difference in the
score is caused by chunking alone.

Corpus: the two Mexican penal codes (CNPP + Código Penal Federal), converted to
Markdown under `ingestion/out/`. They're where article structure exists, so
they're where the chunking strategy actually matters. Questions + the expected
article come from `ingestion/penal_qa.json`.

Metric: for each question we retrieve the top-5 chunks (cosine) for a strategy
and check whether any of them contains the expected 'Artículo N'.
  * art_hit@k = fraction of questions whose article is in the top-k chunks
  * MRR       = mean of 1/(rank of the first chunk containing the article)

Usage (tunnel open — Postgres + a MULTILINGUAL TEI embedder for Spanish):
    uv run python 03_chunking/compare.py               # default: --model tei
    uv run python 03_chunking/compare.py --model tei
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, ".")
from shared.db import connect
from shared.embedder import get_embedder

import chunkers  # noqa: E402  (local module, added to path above)

HERE = Path(__file__).parent
CORPUS_DIR = HERE.parent / "ingestion" / "out" / "Sistema Penal Acusatorio"
CODE_DOCS = ["Código Nacional de Procedimientos Penales", "Código Penal Federal"]
QA_FILE = HERE.parent / "ingestion" / "penal_qa.json"
TABLE = "chunk_lab"
TOPK = 5


def load_docs() -> list[tuple[str, str]]:
    """The two codes → [(name, full_markdown), ...]."""
    return [(name, (CORPUS_DIR / f"{name}.md").read_text()) for name in CODE_DOCS]


def load_questions() -> list[tuple[str, str]]:
    """Questions that cite an article → [(question, article_number), ...].
    (Skips the out-of-corpus control and any question without an article.)"""
    items = json.loads(QA_FILE.read_text())["questions"]
    out: list[tuple[str, str]] = []
    for item in items:
        match = re.search(r"Art\.?\s*(\d+)", item["source"])
        if item["in_corpus"] and match:
            out.append((item["question"], match.group(1)))
    return out


def chunk_has_article(article_number: str, text: str) -> bool:
    return re.search(rf"Art[íi]culo\s+{article_number}\b", text, re.I) is not None


def article_word_counts() -> dict[str, list[int]]:
    return {name: [len(span.split()) for span in chunkers.article_spans(text)]
            for name, text in load_docs()}


def strategies():
    """(name, function) pairs. Each maps a document's text -> list[chunk].
    Language-agnostic strategies only (Spanish corpus); `by-article` is the
    structure-aware one this lab adds. Sentence/semantic strategies from
    chunkers.py are English-tuned — porting them to Spanish (pysbd language='es')
    is a good exercise."""
    return [
        ("fixed-150/25", lambda text: chunkers.fixed(text, size=150, overlap=25)),
        ("fixed-400/40", lambda text: chunkers.fixed(text, size=400, overlap=40)),
        ("recursive-150", lambda text: chunkers.recursive(text, size=150)),
        ("by-article",   lambda text: chunkers.by_article(text, max_words=250)),
    ]


def build(embedder) -> int:
    """Chunk the corpus with every strategy and store all chunks in one table,
    tagged with a `strategy` column so we can score each with a WHERE filter."""
    docs = load_docs()
    rows: list[tuple[str, str, str]] = []  # (strategy, source, text)
    for name, chunk_fn in strategies():
        for source, text in docs:
            for chunk in chunk_fn(text):
                rows.append((name, source, chunk))

    vectors = embedder.encode([text for _, _, text in rows])
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(f"DROP TABLE IF EXISTS {TABLE}")
        cursor.execute(
            f"CREATE TABLE {TABLE} (id bigserial PRIMARY KEY, strategy text, "
            f"source text, text text, embedding vector({embedder.dim}))"
        )
        with cursor.copy(f"COPY {TABLE} (strategy, source, text, embedding) FROM STDIN") as copy:
            for (strategy, source, text), vector in zip(rows, vectors):
                copy.write_row((strategy, source, text, vector))
        connection.commit()
    return len(rows)


def collect_metrics(embedder) -> list[dict]:
    """Score every strategy and RETURN the numbers (so the notebook can plot them)."""
    questions = load_questions()
    question_vectors = embedder.encode([question for question, _ in questions])
    question_count = len(questions)
    results: list[dict] = []
    with connect() as connection, connection.cursor() as cursor:
        for name, _ in strategies():
            cursor.execute(
                f"SELECT count(*), avg(array_length(string_to_array(text,' '),1)) "
                f"FROM {TABLE} WHERE strategy=%s", (name,))
            n_chunks, avg_words = cursor.fetchone()

            hits = {1: 0, 3: 0, 5: 0}
            reciprocal_rank_sum = 0.0
            for (question, article_number), question_vector in zip(questions, question_vectors):
                cursor.execute(
                    f"SELECT text FROM {TABLE} WHERE strategy=%s "
                    f"ORDER BY embedding <=> %s LIMIT {TOPK}", (name, question_vector))
                retrieved = [row[0] for row in cursor.fetchall()]
                rank = next((i + 1 for i, text in enumerate(retrieved)
                             if chunk_has_article(article_number, text)), None)
                if rank:
                    reciprocal_rank_sum += 1.0 / rank
                    for k in (1, 3, 5):
                        if rank <= k:
                            hits[k] += 1
            results.append({
                "strategy": name, "n_chunks": n_chunks, "avg_words": float(avg_words),
                "art_hit@1": hits[1] / question_count,
                "art_hit@3": hits[3] / question_count,
                "art_hit@5": hits[5] / question_count,
                "mrr": reciprocal_rank_sum / question_count,
            })
    return results


def evaluate(embedder) -> None:
    results = collect_metrics(embedder)
    print(f"\n{'strategy':<14}{'#chunks':>8}{'avg_words':>10}"
          f"{'art@1':>8}{'art@3':>8}{'art@5':>8}{'MRR':>7}")
    print("-" * 63)
    for result in results:
        print(f"{result['strategy']:<14}{result['n_chunks']:>8}{result['avg_words']:>10.1f}"
              f"{result['art_hit@1']:>8.2f}{result['art_hit@3']:>8.2f}"
              f"{result['art_hit@5']:>8.2f}{result['mrr']:>7.2f}")
    print("\nSame corpus, same questions, same embedder — only the chunking changed.")
    print("art_hit@k = the expected article landed in the top-k retrieved chunks.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Lab 03 — compare chunking strategies")
    parser.add_argument("--model", default="tei",
                        help="MUST be multilingual for Spanish: tei (GPU) | bge-m3 | ...")
    args = parser.parse_args()

    embedder = get_embedder(args.model)
    print(f"embedder: {embedder.name} ({embedder.dim}d)")
    n_chunks = build(embedder)
    print(f"stored {n_chunks} chunks across {len(strategies())} strategies in '{TABLE}'")
    evaluate(embedder)


if __name__ == "__main__":
    main()
