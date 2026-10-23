"""Benchmark con y sin rerank (Qwen3-Reranker-0.6B, vLLM en la RTX, túnel 8086) con la configuración de la ronda 2:
penal-original-v1, filtro por estado v3, descomponer (actual), routing por código, sin por delito ni remisiones.
Sets 3, 13, 14 y 12, 2 repeticiones = 16 corridas, una por una (espera si hay otra corrida en curso, para no mezclar
tiempos). En cada set alterna sin/con rerank. La prueba de recall de Componentes (#23) dio 75.7 → 85.1 % en los 10
primeros resultados; aquí se mide si eso llega al score. Arranca la copia temporal de prod en 8099 (lee RERANK_URL y
RERANK_FORMATO del .env de prod) y la apaga al final."""
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
                 stdout=open('/tmp/rltest_app_r.log', 'w'), stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                 start_new_session=True)
for _ in range(100):
    try:
        urllib.request.urlopen('http://127.0.0.1:8099/healthz', timeout=5); break
    except Exception:  # noqa: BLE001
        time.sleep(3)
(prompt,), = q("SELECT text FROM bench_prompt_tags WHERE tag = 'penal-original-v1'")
cfg = {'setting': 'híbrido', 'k': 10, 'neighbors': True, 'hyde': True, 'decompose': True, 'route': True,
       'jurisdictions': [], 'gate': True, 'system': prompt}
try:
    for rep in (1, 2):
        for sid in (3, 13, 14, 12):
            for rerank in (False, True):
                nombre = 'con rerank' if rerank else 'sin rerank'
                body = dict(cfg, rerank=rerank, set_id=sid,
                            label=f'rerank-2026-10-23 · ronda 2 (B·v3 + routing) {nombre} · penal-original-v1 · rep {rep}')
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
