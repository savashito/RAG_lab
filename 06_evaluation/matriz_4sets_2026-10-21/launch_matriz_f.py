"""Matriz, parte F: B, C y D de launch_matriz.py otra vez, con el filtro por estado corregido (commit 50af8e3: el CPF
entra si la pregunta lo nombra; las preguntas teóricas no piden estado). Sets 3, 13, 14, 12; 2 repeticiones.

Espera a que terminen launch_matriz.py y launch_matriz_e.py; luego reinicia la copia temporal (8099) con el
jurisdiction_gate.py corregido (/tmp/gatefix) y, al final, la apaga. Prod (legis-app) no se toca."""
import json, os, shutil, subprocess, sys, time, urllib.request
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect
def q(sql, args=()):
    with connect() as c, c.cursor() as cur:
        cur.execute(sql, args); return cur.fetchall()
def vivo(patron):
    return subprocess.run(['pgrep', '-f', patron], capture_output=True).returncode == 0
APP = 'uvicorn main:app --host 127.0.0.1 --port 8099'
while vivo('launch_matriz.py') or vivo('launch_matriz_e.py') or q("select id from bench_runs where status='running'"):
    time.sleep(60)
subprocess.run(['pkill', '-f', '[u]vicorn main:app --host 127.0.0.1 --port 8099'])
while vivo('[u]vicorn main:app --host 127.0.0.1 --port 8099'):
    time.sleep(2)
shutil.copy('/tmp/gatefix/jurisdiction_gate.py', '/tmp/rltest/apps/rewrite_lab/jurisdiction_gate.py')
subprocess.Popen(['/home/tlacua/apps/RAG_lab/.venv/bin/uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '8099'],
                 cwd='/tmp/rltest/apps/rewrite_lab', env=dict(os.environ, GOOGLE_CLIENT_ID=''),
                 stdout=open('/tmp/rltest_app_f.log', 'w'), stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                 start_new_session=True)
for _ in range(100):
    try:
        urllib.request.urlopen('http://127.0.0.1:8099/healthz', timeout=5); break
    except Exception:  # noqa: BLE001
        time.sleep(3)
print('copia temporal reiniciada con el filtro corregido', flush=True)

prompt = {t: x for t, x in q("SELECT tag, text FROM bench_prompt_tags WHERE tag IN ('penal-original-v1', 'tlacua-v1-penas')")}
base = {'setting': 'híbrido', 'k': 10, 'neighbors': True, 'hyde': True, 'rerank': False, 'decompose': True, 'route': False,
        'jurisdictions': [], 'gate': True}
configs = {
    'B2': dict(base, system=prompt['penal-original-v1']),
    'C2': dict(base, crimes=True, crime_extra_k=3, remisiones=True, system=prompt['penal-original-v1']),
    'D2': dict(base, crimes=True, crime_extra_k=3, remisiones=True, system=prompt['tlacua-v1-penas']),
}
nombre = {'B2': '+ filtro corregido', 'C2': '+ filtro corregido + por delito (+3) + remisiones', 'D2': 'C2 con tlacua-v1-penas'}
try:
    for rep in (1, 2):
        for letra, cfg in configs.items():
            for sid in (3, 13, 14, 12):
                tag = 'tlacua-v1-penas' if letra == 'D2' else 'penal-original-v1'
                body = dict(cfg, set_id=sid, label=f'matriz-2026-10-21 · {letra} {nombre[letra]} · {tag} · rep {rep}')
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
