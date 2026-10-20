"""Set 14 (57 preguntas): ¿descomponer por delito empeora las preguntas simples? Configuración de Karen (#50) + filtro por
estado, con y sin descomponer por delito (+3 chunks), con los 2 prompts de la ronda 2. Copia exacta del código de prod en
8099 (74c0c40); las corridas quedan en la base de prod."""
import json, sys, time, urllib.request
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect
API = 'http://127.0.0.1:8099/api/bench'
def q(sql, args=()):
    with connect() as c, c.cursor() as cur:
        cur.execute(sql, args); return cur.fetchall()
BASE = {'setting': 'orig', 'k': 10, 'neighbors': True, 'hyde': True, 'decompose': False, 'route': False, 'gate': True}
for tag in ('penal-original-v1', 'penal-sencillo-jur-v1'):
    text = q("SELECT text FROM bench_prompt_tags WHERE tag = %s", (tag,))[0][0]
    for crimes in (False, True):
        cfg = dict(BASE, set_id=14, system=text, crimes=crimes, crime_extra_k=3 if crimes else None,
                   label=f'set14-delito · {tag} · karen50 + filtro' + (' + por delito (+3)' if crimes else ''))
        while q("select id from bench_runs where status='running'"):
            time.sleep(15)
        req = urllib.request.Request(API + '/run', json.dumps(cfg).encode(), {'Content-Type': 'application/json'})
        rid = json.load(urllib.request.urlopen(req, timeout=60))['run_id']
        time.sleep(10)
        while q("select status from bench_runs where id=%s", (rid,))[0][0] == 'running':
            time.sleep(20)
        print(rid, cfg['label'], q("select metrics->>'score', metrics->>'errors', metrics->>'avg_seconds', metrics->'avg_timings' "
                                    "from bench_runs where id=%s", (rid,))[0], flush=True)
print('FIN', flush=True)
