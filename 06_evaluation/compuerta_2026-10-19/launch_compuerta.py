"""Corre el set 14 (Jurisdicción inteligente) con la compuerta de jurisdicción y 2 prompts, tomados por su
etiqueta de bench_prompt_tags: penal-original-v1 (puente de la ronda 2) y penal-sencillo-jur-v1 (candidato).
Misma configuración que las corridas #45–#47 (estudio) + gate. Contra la copia temporal 8099; espera si hay
otra corrida en curso."""
import json, sys, time, urllib.error, urllib.request
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect
API = 'http://127.0.0.1:8099/api/bench'
def q(sql, args=()):
    with connect() as c, c.cursor() as cur:
        cur.execute(sql, args); return cur.fetchall()
CFG = {'setting': 'híbrido', 'k': 10, 'neighbors': True, 'hyde': True, 'decompose': True, 'route': True, 'gate': True}
for tag in ('penal-original-v1', 'penal-sencillo-jur-v1'):
    text = q("SELECT text FROM bench_prompt_tags WHERE tag = %s", (tag,))[0][0]
    cfg = dict(CFG, set_id=14, label=f'compuerta-2026-10-19 · {tag} + compuerta', system=text)
    while True:
        if not q("select id from bench_runs where status='running'"):
            try:
                req = urllib.request.Request(API + '/run', json.dumps(cfg).encode(), {'Content-Type': 'application/json'})
                rid = json.load(urllib.request.urlopen(req, timeout=60))['run_id']; break
            except urllib.error.HTTPError as e:
                print('reintento:', e.read()[:200], flush=True)
        time.sleep(30)
    print('lanzada', rid, cfg['label'], flush=True)
    while q("select status from bench_runs where id=%s", (rid,))[0][0] == 'running':
        time.sleep(20)
    print('terminó', rid, q("select status, done, n, metrics->>'pass_rate', metrics->>'errors' from bench_runs where id=%s", (rid,))[0], flush=True)
print('FIN', flush=True)
