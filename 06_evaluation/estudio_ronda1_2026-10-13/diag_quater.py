# Solo lectura. ¿Por qué gana el 167 Quáter? Rango de Quáter/Quinquies/LG15/LG17 en cada buscador
# (denso, denso+HyDE guardado, BM25, RRF) para las preguntas de «Las fotos», y cuánto mueve un reranker
# o una descripción en lenguaje cotidiano del artículo.
import sys, json, io, contextlib, statistics as st
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
import os; os.chdir('/home/tlacua/apps/RAG_lab/apps/rewrite_lab')
from dotenv import load_dotenv; load_dotenv('.env')
os.environ['GOOGLE_CLIENT_ID'] = ''
with contextlib.redirect_stdout(io.StringIO()):
    import main as M
from shared.db import connect
ART = {30846: 'Quáter', 30847: 'Quinquies', 37759: 'LG15', 37761: 'LG17'}
TOPIC = 'derecho_penal_mexicano'
PRUEBAS = ['NGSX-GGPH', 'K9TQ-6P86', 'FYJ2-VS7R']
with connect() as c, c.cursor() as cur:
    cur.execute("""select t.n, t.pregunta, t.busqueda_debug from estudio_turnos t join estudio_intentos i on i.id=t.intento_id
                   where i.escenario='fotos' and i.codigo <> all(%s) order by t.id""", (PRUEBAS,))
    filas = cur.fetchall()
    pref = M.query_prefix(M.instruct_for(TOPIC))
    def rk(lst):
        ids = [i for i, _ in lst] if lst and isinstance(lst[0], tuple) else list(lst)
        return {a: (ids.index(i) + 1 if i in ids else None) for i, a in ART.items()}
    res = []
    for n, q, dbg in filas:
        dbg = dbg if isinstance(dbg, dict) else (json.loads(dbg) if dbg else {})
        hp = None
        for k in ('hyde_passage',):
            hp = dbg.get(k) or hp
        if not hp and isinstance(dbg.get('subs'), list):
            for s in dbg['subs']:
                hp = hp or (s or {}).get('hyde_passage')
        dq = M.dense_ranked(cur, M.tei.embed([pref + q], use_cache=False)[0], TOPIC)
        dh = M.dense_ranked(cur, M.tei.embed([pref + q + ('\n\n' + hp if hp else '')], use_cache=False)[0], TOPIC)
        bm = M.bm25_ranked(q, TOPIC)
        rrf = M.rrf_scored([[i for i, _ in dh], [i for i, _ in bm]])
        r = dict(n=n, q=q[:80], hyde=bool(hp), denso=rk(dq), denso_hyde=rk(dh), bm25=rk(bm), rrf=rk(rrf))
        if M.reranker.enabled:
            ids, _ = M._rerank_ids(q, [i for i, _ in rrf], top_n=50)
            r['rerank50'] = rk(ids)
        res.append(r)
for r in res:
    print(f"t{r['n']} hyde={int(r['hyde'])} {r['q']!r}")
    for k in ('denso', 'denso_hyde', 'bm25', 'rrf', 'rerank50'):
        if k in r: print(f"   {k:10}", r[k])
print('\nreranker activo:', M.reranker.enabled)
def resumen(k):
    out = {}
    for a in ART.values():
        xs = [r[k][a] for r in res if k in r]
        out[a] = dict(mediana=st.median([x or 999 for x in xs]), top10=sum(1 for x in xs if x and x <= 10), top3=sum(1 for x in xs if x and x <= 3), n=len(xs))
    return out
for k in ('denso', 'denso_hyde', 'bm25', 'rrf', 'rerank50'):
    if k in res[0]: print(k, resumen(k))
json.dump(res, open('/tmp/diag_quater.json', 'w'), ensure_ascii=False)
