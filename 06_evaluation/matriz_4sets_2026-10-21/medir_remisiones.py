"""¿Qué trajeron las remisiones en las corridas C de la matriz? Cuántas se agregaron, de qué materia, y cuántas eran un
artículo que la pregunta espera (lista de artículos del set). Se corre en el servidor: python medir_remisiones.py"""
import sys, json, re, collections
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect
from shared.object_store import store
from shared.code_routes import short_label
def norm(s): return re.sub(r'\s+', ' ', s.lower().replace('artículo', '').replace('°', '').replace('º','')).strip()
with connect() as c, c.cursor() as cur:
    cur.execute("select id, set_id, label, artifact_key from bench_runs where label like 'matriz-2026-10-21%%' and status='done' and (label like '%% B +%%' or label like '%% C +%%') order by id")
    runs = cur.fetchall()
tot = collections.Counter(); mat = collections.Counter()
for rid, sid, label, key in runs:
    cfg = 'C' if ' C +' in label else 'B'
    res = store.get_json(key.removeprefix(store.prefix))['results']
    for x in res:
        ag = (x.get('remisiones') or {}).get('agregadas') or []
        tot[(cfg, sid, 'preguntas')] += 1
        if cfg != 'C': 
            continue
        if ag: tot[(cfg, sid, 'con_remision')] += 1
        tot[(cfg, sid, 'remisiones')] += len(ag)
        for a in ag: mat[a['materia']] += 1
        gold = {norm(l) for g in (x.get('retrieval') or {}).get('groups', []) for l in g['labels']}
        hits = [a for a in ag if norm(f"{short_label(a['source'])} {a['a']}") in gold]
        if hits:
            tot[(cfg, sid, 'remision_es_gold')] += 1
            print(f"  run {rid} set {sid} q{x['question_id']} score {x.get('score')}: remisión trajo artículo esperado {[short_label(h['source'])+' '+h['a']+' ← '+h['de'] for h in hits]}")
for sid in (3, 13, 14, 12):
    print(f"set {sid}: preguntas C {tot[('C',sid,'preguntas')]} · con ≥1 remisión {tot[('C',sid,'con_remision')]} · remisiones {tot[('C',sid,'remisiones')]} · trajeron un artículo esperado {tot[('C',sid,'remision_es_gold')]}")
print('materia de lo agregado:', dict(mat))
