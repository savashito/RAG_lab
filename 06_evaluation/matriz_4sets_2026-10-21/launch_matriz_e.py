"""Config E de la matriz (ver launch_matriz.py): C (filtro + por delito (+3) + remisiones) con el prompt del usuario
tlacua-secuencia-y-penas, tal cual (como en la corrida 106). Sets 13, 14, 3, 12, 2 repeticiones. Espera a que termine
launch_matriz.py para no intercalarse con sus corridas. Contra una copia exacta del código de prod en 8099."""
import json, subprocess, sys, time, urllib.request
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect
def q(sql, args=()):
    with connect() as c, c.cursor() as cur:
        cur.execute(sql, args); return cur.fetchall()
while subprocess.run(['pgrep', '-f', 'launch_matriz.py'], capture_output=True).returncode == 0:
    time.sleep(60)
(prompt,), = q("SELECT text FROM bench_prompt_tags WHERE tag = 'tlacua-secuencia-y-penas'")
cfg = {'setting': 'híbrido', 'k': 10, 'neighbors': True, 'hyde': True, 'rerank': False, 'decompose': True, 'route': False,
       'jurisdictions': [], 'gate': True, 'crimes': True, 'crime_extra_k': 3, 'remisiones': True, 'system': prompt}
for rep in (1, 2):
    for sid in (13, 14, 3, 12):
        body = dict(cfg, set_id=sid,
                    label=f'matriz-2026-10-21 · E C con tlacua-secuencia-y-penas · tlacua-secuencia-y-penas · rep {rep}')
        while q("select id from bench_runs where status='running'"):
            time.sleep(20)
        req = urllib.request.Request('http://127.0.0.1:8099/api/bench/run', json.dumps(body).encode(),
                                     {'Content-Type': 'application/json'})
        rid = json.load(urllib.request.urlopen(req, timeout=60))['run_id']
        time.sleep(10)
        while q("select status from bench_runs where id=%s", (rid,))[0][0] == 'running':
            time.sleep(20)
        print(rid, f'set {sid}', body['label'],
              q("select status, done, n, metrics->>'score', metrics->>'other_state_rate', metrics->>'retrieval_recall' "
                "from bench_runs where id=%s", (rid,))[0], flush=True)
print('FIN', flush=True)
