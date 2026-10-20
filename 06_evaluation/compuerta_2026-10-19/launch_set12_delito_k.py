"""Set 12 con tlacua-v1 + filtro + descomponer por delito (05cf7a3), 2 configuraciones × 2 repeticiones.
estudio) × filtro sí/no × 2 repeticiones = 8 corridas. Filtro con tipo de asunto y rol del lugar (6ea2dd8)."""
import json, sys, time, urllib.request
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect
API = 'http://127.0.0.1:8099/api/bench'
def q(sql, args=()):
    with connect() as c, c.cursor() as cur:
        cur.execute(sql, args); return cur.fetchall()
CONFIGS = {'karen50': {'setting': 'orig', 'k': 10, 'neighbors': True, 'hyde': True, 'decompose': False, 'route': False},
           'estudio': {'setting': 'híbrido', 'k': 10, 'neighbors': True, 'hyde': True, 'decompose': True, 'route': True}}
text = q("SELECT text FROM bench_prompt_tags WHERE tag = 'tlacua-v1'")[0][0]
for rep in (1, 2):
    for nombre, base in CONFIGS.items():
        for gate in (True,):
            cfg = dict(base, set_id=12, gate=gate, crimes=True, system=text,
                       label=f'set12-delito · tlacua-v1 · {nombre} + filtro + por delito + k por delito' + f' · rep {rep}')
            while q("select id from bench_runs where status='running'"):
                time.sleep(15)
            req = urllib.request.Request(API + '/run', json.dumps(cfg).encode(), {'Content-Type': 'application/json'})
            rid = json.load(urllib.request.urlopen(req, timeout=60))['run_id']
            time.sleep(10)
            while q("select status from bench_runs where id=%s", (rid,))[0][0] == 'running':
                time.sleep(15)
            print(rid, cfg['label'], q("select metrics->>'score', metrics->>'must_coverage', metrics->>'retrieval_recall' from bench_runs where id=%s", (rid,))[0], flush=True)
print('FIN', flush=True)
