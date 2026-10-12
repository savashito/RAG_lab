"""Benchmark de 3 prompts (A actual, B sencillo de Karen, C sencillo + uso del contexto) en los sets 11 y 3,
con la MISMA configuración del estudio (híbrido, k=10, vecinos, HyDE, descomponer, routing) y el corpus de hoy.
Corridas en cadena contra la copia temporal (8099); espera si hay otra corrida en curso."""
import sys, json, time, urllib.request, urllib.error
sys.path.insert(0, '/home/tlacua/apps/RAG_lab'); sys.path.insert(0, '/home/tlacua/apps/RAG_lab/apps/rewrite_lab')
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect
API = 'http://127.0.0.1:8099/api/bench'
def q(sql, args=()):
    with connect() as c, c.cursor() as cur:
        cur.execute(sql, args); return cur.fetchall()
B = open('/tmp/prompt_sencillo_karen.txt').read().strip()
C = open('/tmp/prompt_sencillo_contexto.txt').read().strip()
CFG = {'setting': 'híbrido', 'k': 10, 'neighbors': True, 'hyde': True, 'decompose': True, 'route': True}
PLAN = [(sid, sysm, f'prompts-2026-10-12 · {nombre}') for sid in (11, 3)
        for nombre, sysm in (('A actual', ''), ('B sencillo (Karen)', B), ('C sencillo + contexto', C))]
for sid, sysm, label in PLAN:
    cfg = dict(CFG, set_id=sid, label=label, system=sysm)
    while True:
        if not q("select id from bench_runs where status='running'"):
            try:
                req = urllib.request.Request(API + '/run', json.dumps(cfg).encode(), {'Content-Type': 'application/json'})
                rid = json.load(urllib.request.urlopen(req, timeout=60))['run_id']; break
            except urllib.error.HTTPError as e:
                print('reintento:', e.read()[:200], flush=True)
        time.sleep(30)
    print('lanzada', rid, 'set', sid, label, flush=True)
    while q("select status from bench_runs where id=%s", (rid,))[0][0] == 'running':
        time.sleep(20)
    print('terminó', rid, q("select status, done, n, metrics from bench_runs where id=%s", (rid,))[0], flush=True)
print('FIN', flush=True)
