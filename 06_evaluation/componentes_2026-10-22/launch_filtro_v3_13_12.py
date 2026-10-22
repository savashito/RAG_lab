"""Mide la regla nueva de las preguntas teóricas del filtro (commit 807198e, 2026-10-22: sin códigos estatales, con
doctrina + leyes nacionales + CPF, y ofreciendo ver el código del estado). Misma configuración que B2 de la matriz
(filtro corregido, penal-original-v1, sin descomponer por delito ni remisiones), sets 3 y 14, 2 repeticiones.
Comparar con B2 (#147/#163 en el set 3, #149/#165 en el set 14). Arranca la copia temporal de prod en 8099 y la apaga
al final."""
import json, os, subprocess, sys, time, urllib.request
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect
def q(sql, args=()):
    with connect() as c, c.cursor() as cur:
        cur.execute(sql, args); return cur.fetchall()
subprocess.run('rm -rf /tmp/rltest && rsync -a --exclude .venv --exclude .git ~/apps/RAG_lab/ /tmp/rltest/', shell=True, check=True)
subprocess.Popen(['/home/tlacua/apps/RAG_lab/.venv/bin/uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '8099'],
                 cwd='/tmp/rltest/apps/rewrite_lab', env=dict(os.environ, GOOGLE_CLIENT_ID=''),
                 stdout=open('/tmp/rltest_app_v3.log', 'w'), stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                 start_new_session=True)
for _ in range(100):
    try:
        urllib.request.urlopen('http://127.0.0.1:8099/healthz', timeout=5); break
    except Exception:  # noqa: BLE001
        time.sleep(3)
(prompt,), = q("SELECT text FROM bench_prompt_tags WHERE tag = 'penal-original-v1'")
cfg = {'setting': 'híbrido', 'k': 10, 'neighbors': True, 'hyde': True, 'rerank': False, 'decompose': True, 'route': False,
       'jurisdictions': [], 'gate': True, 'system': prompt}
try:
    for rep in (1, 2):
        for sid in (13, 12):
            body = dict(cfg, set_id=sid, label=f'filtro-v3-2026-10-22 · B·v3 (filtro v3) · penal-original-v1 · rep {rep}')
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
finally:
    subprocess.run(['pkill', '-f', '[u]vicorn main:app --host 127.0.0.1 --port 8099'])
    print('copia temporal apagada', flush=True)
print('FIN', flush=True)
