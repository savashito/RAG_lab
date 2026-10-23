"""Benchmark del prompt «ultimo-promt» de Karen (08cee8aa, 23-oct; candidato a prompt nuevo de la ronda 2) con la
configuración de la ronda 2: filtro por estado v3, descomponer (actual), routing por código, sin rerank, sin por delito
ni remisiones. Sets 3, 13, 14 y 12, 2 repeticiones = 8 corridas, una por una. Se compara contra penal-original-v1 con
la misma configuración: las corridas «sin rerank» de rerank-2026-10-23 (#211, #213… del mismo día). Espera a que
termine launch_rerank.py (las dos usan la copia temporal en 8099), arranca la copia y la apaga al final."""
import json, os, subprocess, sys, time, urllib.request
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect
def q(sql, args=()):
    with connect() as c, c.cursor() as cur:
        cur.execute(sql, args); return cur.fetchall()
while subprocess.run(['pgrep', '-f', '[l]aunch_rerank.py'], capture_output=True).returncode == 0:
    time.sleep(30)
subprocess.run('rm -rf /tmp/rltest && rsync -a --exclude .venv --exclude .git ~/apps/RAG_lab/ /tmp/rltest/', shell=True, check=True)
subprocess.Popen(['/home/tlacua/apps/RAG_lab/.venv/bin/uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '8099'],
                 cwd='/tmp/rltest/apps/rewrite_lab', env=dict(os.environ, GOOGLE_CLIENT_ID=''),
                 stdout=open('/tmp/rltest_app_u.log', 'w'), stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                 start_new_session=True)
for _ in range(100):
    try:
        urllib.request.urlopen('http://127.0.0.1:8099/healthz', timeout=5); break
    except Exception:  # noqa: BLE001
        time.sleep(3)
(prompt,), = q("SELECT text FROM bench_prompt_tags WHERE tag = 'ultimo-promt'")
cfg = {'setting': 'híbrido', 'k': 10, 'neighbors': True, 'hyde': True, 'decompose': True, 'route': True,
       'jurisdictions': [], 'gate': True, 'system': prompt}
try:
    for rep in (1, 2):
        for sid in (3, 13, 14, 12):
            body = dict(cfg, rerank=False, set_id=sid,
                        label=f'ultimo-prompt-2026-10-23 · ronda 2 (B·v3 + routing) sin rerank · ultimo-promt · rep {rep}')
            while q("select id from bench_runs where status='running'"):
                time.sleep(20)
            req = urllib.request.Request('http://127.0.0.1:8099/api/bench/run', json.dumps(body).encode(),
                                         {'Content-Type': 'application/json'})
            rid = json.load(urllib.request.urlopen(req, timeout=60))['run_id']
            time.sleep(10)
            while q("select status from bench_runs where id=%s", (rid,))[0][0] == 'running':
                time.sleep(20)
            print(rid, f'set {sid}', body['label'],
                  q("select status, done, n, metrics->>'score', metrics->>'other_state_rate', metrics->>'retrieval_recall', "
                    "round(extract(epoch from finished_at-created_at)/60) from bench_runs where id=%s", (rid,))[0], flush=True)
finally:
    subprocess.run(['pkill', '-f', '[u]vicorn main:app --host 127.0.0.1 --port 8099'])
    print('copia temporal apagada', flush=True)
print('FIN', flush=True)
