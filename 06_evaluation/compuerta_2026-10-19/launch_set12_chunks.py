"""Set 12, tlacua-v1, configuración de Karen (#50) + filtro por estado + descomponer por delito, con 2, 3 y 5 chunks
extra por conducta adicional, 2 repeticiones (74c0c40, con tiempos por etapa). Contra una copia exacta del código de
prod en 8099 (prod pide iniciar sesión); las corridas quedan en la base de prod."""
import json, sys, time, urllib.request
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect
API = 'http://127.0.0.1:8099/api/bench'
def q(sql, args=()):
    with connect() as c, c.cursor() as cur:
        cur.execute(sql, args); return cur.fetchall()
BASE = {'setting': 'orig', 'k': 10, 'neighbors': True, 'hyde': True, 'decompose': False, 'route': False,
        'gate': True, 'crimes': True}
text = q("SELECT text FROM bench_prompt_tags WHERE tag = 'tlacua-v1'")[0][0]
for rep in (1, 2):
    for extra in (2, 3, 5):
        cfg = dict(BASE, set_id=12, system=text, crime_extra_k=extra,
                   label=f'set12-chunks · tlacua-v1 · karen50 + filtro + por delito · +{extra} chunks · rep {rep}')
        while q("select id from bench_runs where status='running'"):
            time.sleep(15)
        req = urllib.request.Request(API + '/run', json.dumps(cfg).encode(), {'Content-Type': 'application/json'})
        rid = json.load(urllib.request.urlopen(req, timeout=60))['run_id']
        time.sleep(10)
        while q("select status from bench_runs where id=%s", (rid,))[0][0] == 'running':
            time.sleep(15)
        print(rid, cfg['label'], q("select metrics->>'score', metrics->>'must_coverage', metrics->>'retrieval_recall', "
                                    "metrics->>'avg_seconds', metrics->'avg_timings' from bench_runs where id=%s", (rid,))[0], flush=True)
print('FIN', flush=True)
