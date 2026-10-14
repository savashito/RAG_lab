# Solo lectura. ¿Qué le gana al art. 15 de la Ley de Extorsión cuando la consulta ya dice «extorsión»? y ¿cuánto
# ayuda filtrar los códigos de OTROS estados (Querétaro + federal/nacional/generales/doctrina)?
import sys, json, io, contextlib, statistics as st, collections
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
import os; os.chdir('/home/tlacua/apps/RAG_lab/apps/rewrite_lab')
from dotenv import load_dotenv; load_dotenv('.env')
os.environ['GOOGLE_CLIENT_ID'] = ''
with contextlib.redirect_stdout(io.StringIO()):
    import main as M
from shared.db import connect
from shared.code_routes import short_label
ART = {30846: 'Quáter', 30847: 'Quinquies', 37759: 'LG15', 37761: 'LG17'}
TOPIC = 'derecho_penal_mexicano'
OTROS = {'CDMX', 'CPEM', 'Morelos'}
d = json.load(open('/tmp/diag_hechos.json'))
pref = M.query_prefix(M.instruct_for(TOPIC))
def lab(i):
    m = M.DOC_BY_ID.get(i) or {}
    return short_label(m.get('source') or ''), (m.get('hierarchy') or '').split(' > ')[-1][:40], (m.get('source') or '')[:50]
pos = {'hechos': {a: [] for a in ART.values()}, 'hechos+filtro': {a: [] for a in ART.values()}}
top = collections.Counter()
with connect() as c, c.cursor() as cur:
    for q, h in d['ejemplos']:
        dx = M.dense_ranked(cur, M.tei.embed([pref + h], use_cache=False)[0], TOPIC)
        ids = [i for i, _ in M.rrf_scored([[i for i, _ in dx], [i for i, _ in M.bm25_ranked(h, TOPIC)]])]
        filt = [i for i in ids if lab(i)[0] not in OTROS]
        for k, L in (('hechos', ids), ('hechos+filtro', filt)):
            for i, a in ART.items(): pos[k][a].append(L.index(i) + 1 if i in L else 999)
        for i in ids[:10]: top[lab(i)[2]] += 1
print('documentos en el top-10 de la consulta «hechos/delitos» (23 consultas):')
for s, n in top.most_common(15): print(f'  {n:3}  {s}')
for q, h in d['ejemplos'][:1]:
    with connect() as c, c.cursor() as cur:
        dx = M.dense_ranked(cur, M.tei.embed([pref + h], use_cache=False)[0], TOPIC)
        ids = [i for i, _ in M.rrf_scored([[i for i, _ in dx], [i for i, _ in M.bm25_ranked(h, TOPIC)]])]
    print('\nejemplo top-15:'); [print('  ', n + 1, lab(i)) for n, i in enumerate(ids[:15])]
for k in pos:
    print(k, {a: dict(mediana=st.median(xs), top10=sum(x <= 10 for x in xs), top3=sum(x <= 3 for x in xs)) for a, xs in pos[k].items()})
