"""Set 14 con la MISMA configuración y prompt que la corrida 102 (lanzada por el usuario desde la página, cancelada en
44/57 al reiniciar la app), más «seguir remisiones». Copia exacta del código de prod en 8099."""
import json, sys, time, urllib.request
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect
def q(sql, args=()):
    with connect() as c, c.cursor() as cur:
        cur.execute(sql, args); return cur.fetchall()
cfg0, = q("SELECT config FROM bench_runs WHERE id = 102")[0]
tag = q("SELECT tag FROM bench_prompt_tags WHERE md5 = md5(%s)", (cfg0['system'],))
cfg = {k: cfg0[k] for k in ('setting', 'k', 'neighbors', 'hyde', 'rerank', 'decompose', 'route', 'gate', 'crimes', 'system')}
cfg.update(set_id=14, remisiones=True, jurisdictions=cfg0.get('jurisdictions') or [],
           label=f"set14 · como #102 ({tag[0][0] if tag else 'prompt sin etiqueta'}) + remisiones")
print('prompt:', tag, '· config:', {k: v for k, v in cfg.items() if k != 'system'}, flush=True)
while q("select id from bench_runs where status='running'"):
    time.sleep(15)
req = urllib.request.Request('http://127.0.0.1:8099/api/bench/run', json.dumps(cfg).encode(), {'Content-Type': 'application/json'})
rid = json.load(urllib.request.urlopen(req, timeout=60))['run_id']
print('lanzada', rid, flush=True)
time.sleep(10)
while q("select status from bench_runs where id=%s", (rid,))[0][0] == 'running':
    time.sleep(20)
print('terminó', rid, q("select status, done, n, metrics->>'score', metrics->'avg_timings' from bench_runs where id=%s", (rid,))[0], flush=True)
print('FIN', flush=True)
