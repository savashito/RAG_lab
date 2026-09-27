"""Benchmark de retrieval por tópico (nivel documento), read-only.

Compara DENSO (pgvector, qwen06) vs BM25 (léxico) vs HÍBRIDO (RRF) sobre un golden set
`{q, gold:[sources]}`. gold es un CONJUNTO (corpus con duplicados): acierta si trae
cualquiera de los gold. Métricas: recall@k, MRR, nDCG@10.

Corre donde alcanza la DB+TEI (p. ej. el server de prod). Reusa shared/lexical.py.

    python 06_evaluation/psico_bench.py golden_psicologia_conductual.json [--depth 200]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import pathlib
import sys
import unicodedata


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

# .env de la app (si existe) para DB/TEI/tabla
_env = REPO / "apps/rewrite_lab/.env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)

from shared.db import connect
from shared.tei_client import TEIClient
from shared.lexical import BM25, tokenize, rank_indices_by_score, rrf

TABLE = os.environ.get("LEGAL_TABLE", "sistema_penal__qwen06__legal")
KS = (1, 3, 5, 10)


def dedupe_docs(sources: list[str], idx_ranking: list[int]) -> list[str]:
    """chunk-index ranking → doc ranking (primera aparición de cada source)."""
    seen, out = set(), []
    for i in idx_ranking:
        s = sources[i]
        if s not in seen:
            seen.add(s); out.append(s)
    return out


def score(ranked_docs: list[str], gold: set[str]) -> dict:
    ranks = [r for r, d in enumerate(ranked_docs, 1) if d in gold]
    first = ranks[0] if ranks else None
    m = {f"recall@{k}": float(first is not None and first <= k) for k in KS}
    m["mrr"] = 1.0 / first if first else 0.0
    kmax = max(KS)
    dcg = sum(1.0 / math.log2(r + 1) for r in ranks if r <= kmax)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(min(len(gold), kmax)))
    m[f"ndcg@{kmax}"] = dcg / idcg if idcg else 0.0
    return m


def topic_instruct(cur, topic: str) -> str:
    try:
        cur.execute("SELECT instruct FROM rewrite_lab_topics WHERE topic=%s", (topic,))
        row = cur.fetchone()
        if row and row[0]:
            return row[0].strip()
    except Exception:
        pass
    return "Recupera el pasaje del código o la doctrina que responde la pregunta."


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("golden")
    ap.add_argument("--depth", type=int, default=200, help="candidatos (chunks) por método")
    args = ap.parse_args()

    gpath = pathlib.Path(args.golden)
    if not gpath.is_absolute():
        gpath = REPO / "06_evaluation" / args.golden
    data = json.loads(gpath.read_text(encoding="utf-8"))
    topic = data["topic"]
    questions = data["questions"]

    tei = TEIClient()
    with connect() as c, c.cursor() as cur:
        task = topic_instruct(cur, topic)
        prefix = f"Instruct: {task}\nQuery: "
        cur.execute(f"SELECT id, source, text FROM {TABLE} WHERE topic=%s ORDER BY id", (topic,))
        rows = cur.fetchall()
    ids = [r[0] for r in rows]
    sources = [nfc(r[1]) for r in rows]
    id2idx = {i: n for n, i in enumerate(ids)}
    bm = BM25([tokenize(r[2]) for r in rows])
    n_docs = len(set(sources))
    print(f"Tópico: {topic} | chunks: {len(rows)} | docs: {n_docs} | modelo: {tei.model_id}")
    print(f"Instruct: {task!r}\nPreguntas: {len(questions)} | profundidad: {args.depth}\n")

    methods = ("dense", "bm25", "hybrid")
    agg = {m: [] for m in methods}
    qvecs = tei.embed([prefix + q["q"] for q in questions], use_cache=False)

    with connect() as c, c.cursor() as cur:
        for q, qv in zip(questions, qvecs):
            gold = set(nfc(g) for g in q["gold"])
            vlit = "[" + ",".join(map(repr, (float(x) for x in qv))) + "]"
            cur.execute(
                f"SELECT id FROM {TABLE} WHERE topic=%s ORDER BY embedding <=> %s::vector LIMIT %s",
                (topic, vlit, args.depth))
            dense_idx = [id2idx[r[0]] for r in cur.fetchall()]
            bm_idx = rank_indices_by_score(bm.scores(tokenize(q["q"])))[:args.depth]
            hyb_idx = rrf([dense_idx, bm_idx])[:args.depth]
            rankings = {"dense": dense_idx, "bm25": bm_idx, "hybrid": hyb_idx}
            for mth in methods:
                agg[mth].append(score(dedupe_docs(sources, rankings[mth]), gold))

    def mean(rows, key):
        return sum(r[key] for r in rows) / len(rows)

    cols = [f"recall@{k}" for k in KS] + ["mrr", f"ndcg@{max(KS)}"]
    print(f"{'método':8}" + "".join(f"{c:>11}" for c in cols))
    results = {}
    for mth in methods:
        vals = {c: round(mean(agg[mth], c), 4) for c in cols}
        results[mth] = vals
        print(f"{mth:8}" + "".join(f"{vals[c]:>11.4f}" for c in cols))

    # Fallas duras del híbrido: gold fuera del top-10 → qué se recuperó en su lugar
    print("\n── FALLAS (gold fuera del top-10, híbrido) ──")
    with connect() as c, c.cursor() as cur:
        for q, qv in zip(questions, qvecs):
            gold = set(nfc(g) for g in q["gold"])
            vlit = "[" + ",".join(map(repr, (float(x) for x in qv))) + "]"
            cur.execute(
                f"SELECT id FROM {TABLE} WHERE topic=%s ORDER BY embedding <=> %s::vector LIMIT %s",
                (topic, vlit, args.depth))
            dense_idx = [id2idx[r[0]] for r in cur.fetchall()]
            bm_idx = rank_indices_by_score(bm.scores(tokenize(q["q"])))[:args.depth]
            docs = dedupe_docs(sources, rrf([dense_idx, bm_idx]))
            if not any(d in gold for d in docs[:10]):
                print(f"  ✗ {q['q'][:70]}")
                print(f"      gold: {list(gold)}")
                print(f"      top3: {docs[:3]}")

    out = REPO / "06_evaluation" / f"results_{topic}.json"
    out.write_text(json.dumps({"topic": topic, "n_questions": len(questions),
                               "model": tei.model_id, "results": results}, indent=2,
                              ensure_ascii=False), encoding="utf-8")
    print(f"\n→ {out}")
    print("recall@1 = doc correcto en el puesto 1; MRR = 1/rango del primer acierto.")


if __name__ == "__main__":
    main()
