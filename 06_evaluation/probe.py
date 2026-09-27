"""Sonda de una sola consulta: qué recupera cada método (read-only).

    python 06_evaluation/probe.py <topic> "<pregunta>" [--depth 100 --show 8]
"""
from __future__ import annotations
import argparse, os, pathlib, sys, unicodedata
REPO = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO))
_env = REPO / "apps/rewrite_lab/.env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1); os.environ.setdefault(k, v)
from shared.db import connect
from shared.tei_client import TEIClient
from shared.lexical import BM25, tokenize, rank_indices_by_score, rrf

TABLE = os.environ.get("LEGAL_TABLE", "sistema_penal__qwen06__legal")
ap = argparse.ArgumentParser(); ap.add_argument("topic"); ap.add_argument("query")
ap.add_argument("--depth", type=int, default=100); ap.add_argument("--show", type=int, default=8)
a = ap.parse_args()

tei = TEIClient()
with connect() as c, c.cursor() as cur:
    cur.execute("SELECT instruct FROM rewrite_lab_topics WHERE topic=%s", (a.topic,))
    row = cur.fetchone(); task = (row[0].strip() if row and row[0] else "Recupera el pasaje que responde la pregunta.")
    cur.execute(f"SELECT id, source, text FROM {TABLE} WHERE topic=%s ORDER BY id", (a.topic,))
    rows = cur.fetchall()
ids = [r[0] for r in rows]; sources = [r[1] for r in rows]; texts = [r[2] for r in rows]
id2idx = {i: n for n, i in enumerate(ids)}
bm = BM25([tokenize(t) for t in texts])
qv = tei.embed([f"Instruct: {task}\nQuery: " + a.query], use_cache=False)[0]
vlit = "[" + ",".join(map(repr, (float(x) for x in qv))) + "]"
with connect() as c, c.cursor() as cur:
    cur.execute(f"SELECT id FROM {TABLE} WHERE topic=%s ORDER BY embedding <=> %s::vector LIMIT %s",
                (a.topic, vlit, a.depth))
    dense_idx = [id2idx[r[0]] for r in cur.fetchall()]
bm_idx = rank_indices_by_score(bm.scores(tokenize(a.query)))[:a.depth]
hyb_idx = rrf([dense_idx, bm_idx])

def docs(idxs):
    seen, out = set(), []
    for i in idxs:
        if sources[i] not in seen:
            seen.add(sources[i]); out.append(sources[i])
    return out

print(f"Query: {a.query!r}\nInstruct: {task!r}\n")
for name, idxs in [("DENSO", dense_idx), ("BM25", bm_idx), ("HÍBRIDO", hyb_idx)]:
    print(f"── {name} — top docs ──")
    for d in docs(idxs)[:a.show]:
        print("   ", d)
    print()
print("── DENSO — top chunks (source · snippet) ──")
for i in dense_idx[:a.show]:
    body = texts[i].split("\n\n", 1)[-1] if texts[i].startswith("Fuente:") else texts[i]
    print(f"   [{sources[i][:38]:38}] {' '.join(body.split())[:150]}")
