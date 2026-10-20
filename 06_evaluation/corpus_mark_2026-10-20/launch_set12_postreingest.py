"""Set 12 después de la reingesta del 2026-10-20 (141 Quáter y 224 de la CDMX ya son artículos propios): tlacua-v1,
configuración de Karen (#50) + filtro, sin descomponer y por delito (+3), 2 repeticiones. Mismas configuraciones que
#63/#67 y #74/#76 (antes de la reingesta). Contra una copia exacta del código de prod en 8099."""
import json, sys, time, urllib.request
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect
def q(sql, args=()):
    with connect() as c, c.cursor() as cur:
        cur.execute(sql, args); return cur.fetchall()
BASE = {'setting': 'orig', 'k': 10, 'neighbors': True, 'hyde': True, 'decompose': False, 'route': False, 'gate': True}
text = q("SELECT text FROM bench_prompt_tags WHERE tag = 'tlacua-v1'")[0][0]
for rep in (1, 2):
    for crimes in (False, True):
        cfg = dict(BASE, set_id=12, system=text, crimes=crimes, crime_extra_k=3 if crimes else None,
                   label=f'set12-post-reingesta · tlacua-v1 · karen50 + filtro' + (' + por delito (+3)' if crimes else '') + f' · rep {rep}')
        while q("select id from bench_runs where status='running'"):
            time.sleep(15)
        req = urllib.request.Request('http://127.0.0.1:8099/api/bench/run', json.dumps(cfg).encode(), {'Content-Type': 'application/json'})
        rid = json.load(urllib.request.urlopen(req, timeout=60))['run_id']
        time.sleep(10)
        while q("select status from bench_runs where id=%s", (rid,))[0][0] == 'running':
            time.sleep(10)
        print(rid, cfg['label'], q("select metrics->>'score', metrics->>'must_coverage', metrics->>'retrieval_recall', metrics->>'avg_seconds' "
                                    "from bench_runs where id=%s", (rid,))[0], flush=True)
print('FIN', flush=True)
