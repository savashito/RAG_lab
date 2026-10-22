"""¿Funciona «descomponer por delito»? B·v2 contra G·v2 (iguales salvo esa opción), por set: en cuántas preguntas el LLM
encontró más de una conducta, y el score y el recall en esas preguntas contra las demás."""
import sys, statistics as st
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect
from shared.object_store import store
def art(rid):
    with connect() as c, c.cursor() as cur:
        cur.execute("select artifact_key from bench_runs where id=%s", (rid,)); k = cur.fetchone()[0]
    return {r['question_id']: r for r in store.get_json(k.removeprefix(store.prefix))['results']}
RUNS = {3: ((147, 163), (151, 167)), 13: ((148, 164), (152, 168)), 14: ((149, 165), (153, 169)), 12: ((150, 166), (154, 170))}
def rec(x):
    r = x.get('retrieval') or {}
    return (r.get('hit'), r.get('attainable')) if r.get('attainable') else None
for sid, (b, g) in RUNS.items():
    B = [art(r) for r in b]; G = [art(r) for r in g]
    qs = sorted(set(B[0]) & set(B[1]) & set(G[0]) & set(G[1]))
    multi, una = [], []
    for q in qs:
        # conductas = sub-búsquedas de G que no estaban en B (la descomposición genérica es la misma en las dos)
        extra = [len(set(x[q].get('subqueries') or []) - set(y[q].get('subqueries') or [])) for x, y in zip(G, B)]
        (multi if max(extra) >= 2 else una).append(q)
    def resumen(grupo):
        if not grupo: return '—'
        sb = st.mean(st.mean(x[q]['score'] for x in B) for q in grupo); sg = st.mean(st.mean(x[q]['score'] for x in G) for q in grupo)
        hb = sum(rec(x[q])[0] for x in B for q in grupo if rec(x[q])); ab = sum(rec(x[q])[1] for x in B for q in grupo if rec(x[q]))
        hg = sum(rec(x[q])[0] for x in G for q in grupo if rec(x[q])); ag = sum(rec(x[q])[1] for x in G for q in grupo if rec(x[q]))
        return f"score B {sb*100:.1f} → G {sg*100:.1f} · recall B {hb}/{ab} → G {hg}/{ag}"
    print(f"set {sid}: {len(qs)} preguntas · con ≥2 conductas: {len(multi)} · con 1: {len(una)}")
    print(f"   ≥2 conductas: {resumen(multi)}")
    print(f"   1 conducta:   {resumen(una)}")
