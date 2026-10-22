"""¿Sirve «descomponer»? B·v3 (filtro v3, penal-original-v1) sin descomponer, y con routing por código en lugar de
descomponer. Sets 3 y 14, 2 repeticiones. Comparar con B·v3 con descomponer (#179–#182). Arranca la copia temporal de
prod en 8099 y la apaga al final; deja /tmp/rltest para las pruebas por componente."""
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
                 stdout=open('/tmp/rltest_app_d.log', 'w'), stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                 start_new_session=True)
for _ in range(100):
    try:
        urllib.request.urlopen('http://127.0.0.1:8099/healthz', timeout=5); break
    except Exception:  # noqa: BLE001
        time.sleep(3)
(prompt,), = q("SELECT text FROM bench_prompt_tags WHERE tag = 'penal-original-v1'")
base = {'setting': 'híbrido', 'k': 10, 'neighbors': True, 'hyde': True, 'rerank': False, 'jurisdictions': [], 'gate': True,
        'system': prompt}
configs = {'sin descomponer': dict(base, decompose=False, route=False),
           'routing en lugar de descomponer': dict(base, decompose=False, route=True)}
try:
    for rep in (1, 2):
        for nombre, cfg in configs.items():
            for sid in (3, 14):
                body = dict(cfg, set_id=sid, label=f'descomponer-2026-10-22 · B·v3 {nombre} · penal-original-v1 · rep {rep}')
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
