"""Set 12 con «seguir remisiones»: tlacua-v1, configuración de Karen (#50) + filtro + remisiones, 2 repeticiones.
Comparar con #90/#92 (igual sin remisiones). Copia temporal 8099 con el código del commit de remisiones."""
import json, sys, time, urllib.request
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect
from shared.object_store import store
def q(sql, args=()):
    with connect() as c, c.cursor() as cur:
        cur.execute(sql, args); return cur.fetchall()
text = q("SELECT text FROM bench_prompt_tags WHERE tag = 'tlacua-v1'")[0][0]
for rep in (1, 2):
    cfg = {'setting': 'orig', 'k': 10, 'neighbors': True, 'hyde': True, 'decompose': False, 'route': False, 'gate': True,
           'remisiones': True, 'set_id': 12, 'system': text,
           'label': f'set12-remisiones-v2 · tlacua-v1 · karen50 + filtro + remisiones (sin listas largas) · rep {rep}'}
    while q("select id from bench_runs where status='running'"):
        time.sleep(15)
    req = urllib.request.Request('http://127.0.0.1:8099/api/bench/run', json.dumps(cfg).encode(), {'Content-Type': 'application/json'})
    rid = json.load(urllib.request.urlopen(req, timeout=60))['run_id']
    time.sleep(10)
    while q("select status from bench_runs where id=%s", (rid,))[0][0] == 'running':
        time.sleep(10)
    m = q("select metrics->>'score', metrics->>'must_coverage', metrics->>'retrieval_recall', metrics->>'avg_seconds', metrics->'avg_timings' from bench_runs where id=%s", (rid,))[0]
    print(rid, cfg['label'], m, flush=True)
    key, = q("select artifact_key from bench_runs where id=%s", (rid,))[0]
    for d in store.get_json(key)['results']:
        ri = d.get('remisiones') or {}
        print('   q', d.get('question_id'), '· agregadas:', [f"{x['a']} ← {x['de']}" for x in ri.get('agregadas', [])],
              '· omitidas:', [x['a'] for x in ri.get('omitidas', [])], flush=True)
print('FIN', flush=True)
