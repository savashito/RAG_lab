"""ultimo-promt-v2 (23-oct, propuesta aprobada por Karen: Fundamento siempre, máximo 2 preguntas después de orientar, no
volver a preguntar el estado; texto en ultimo-promt-v2.txt). Lo registra con esa etiqueta en bench_prompt_tags y lo corre
igual que la v1 (abajo). Se compara contra ultimo-promt (#227–#234) y penal-original-v1 sin rerank (#211–#225, impares).

Benchmark del prompt «ultimo-promt» de Karen (08cee8aa, 23-oct; candidato a prompt nuevo de la ronda 2) con la
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
subprocess.run('rm -rf /tmp/rltest && rsync -a --exclude .venv --exclude .git ~/apps/RAG_lab/ /tmp/rltest/', shell=True, check=True)
subprocess.Popen(['/home/tlacua/apps/RAG_lab/.venv/bin/uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '8099'],
                 cwd='/tmp/rltest/apps/rewrite_lab', env=dict(os.environ, GOOGLE_CLIENT_ID=''),
                 stdout=open('/tmp/rltest_app_u2.log', 'w'), stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                 start_new_session=True)
for _ in range(100):
    try:
        urllib.request.urlopen('http://127.0.0.1:8099/healthz', timeout=5); break
    except Exception:  # noqa: BLE001
        time.sleep(3)
import hashlib
from pathlib import Path
prompt = (Path(__file__).resolve().parent / 'ultimo-promt-v2.txt').read_text().strip()
md5 = hashlib.md5(prompt.encode()).hexdigest()
with connect() as c, c.cursor() as cur:
    cur.execute("SELECT md5 FROM bench_prompt_tags WHERE tag = 'ultimo-promt-v2'")
    fila = cur.fetchone()
    assert not fila or fila[0] == md5, 'ultimo-promt-v2 ya es la etiqueta de otro texto'
    if not fila:
        cur.execute("INSERT INTO bench_prompt_tags (md5, tag, note, text, created_by, updated_by) VALUES (%s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (md5) DO NOTHING", (md5, 'ultimo-promt-v2', 'ultimo-promt + Fundamento siempre, máx. 2 preguntas '
                    'después de orientar, no volver a preguntar el estado (propuesta 23-oct, aprobada por Karen)', prompt,
                    'rodrigosavagerower@gmail.com', 'rodrigosavagerower@gmail.com'))
        cur.execute("INSERT INTO bench_prompt_tags_history (md5, action, tag, note, changed_by) VALUES (%s, 'crear', %s, %s, %s)",
                    (md5, 'ultimo-promt-v2', 'propuesta 23-oct', 'rodrigosavagerower@gmail.com'))
        c.commit()
print('ultimo-promt-v2', md5, flush=True)
cfg = {'setting': 'híbrido', 'k': 10, 'neighbors': True, 'hyde': True, 'decompose': True, 'route': True,
       'jurisdictions': [], 'gate': True, 'system': prompt}
try:
    for rep in (1, 2):
        for sid in (3, 13, 14, 12):
            body = dict(cfg, rerank=False, set_id=sid,
                        label=f'ultimo-prompt-v2-2026-10-23 · ronda 2 (B·v3 + routing) sin rerank · ultimo-promt-v2 · rep {rep}')
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
