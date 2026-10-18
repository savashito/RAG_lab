"""Corre el set 14 (Jurisdicción inteligente) con la configuración del estudio y 3 prompts: original (el del tema),
sencillo (el del estudio) y sencillo + JURISDICCIÓN (candidato). Contra la copia temporal 8099; espera si hay otra corrida."""
import sys, json, time, urllib.request, urllib.error
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from pathlib import Path
from shared.db import connect
from study.store import StudyStore
from study.validar import sistema_de_condicion
API = 'http://127.0.0.1:8099/api/bench'
def q(sql, args=()):
    with connect() as c, c.cursor() as cur:
        cur.execute(sql, args); return cur.fetchall()
SENCILLO = sistema_de_condicion(StudyStore(connect, Path('/nonexistent')).spec('piloto_penal'), 'sencillo') or ''
JURIS = open('/tmp/prompt_jurisdiccion.txt').read().strip()
assert SENCILLO and JURIS
CFG = {'setting': 'híbrido', 'k': 10, 'neighbors': True, 'hyde': True, 'decompose': True, 'route': True}
for label, sysm in (('jur-inteligente-2026-10-18 · original (estudio)', ''), ('jur-inteligente-2026-10-18 · sencillo (estudio)', SENCILLO),
                    ('jur-inteligente-2026-10-18 · sencillo + JURISDICCIÓN (candidato)', JURIS)):
    cfg = dict(CFG, set_id=14, label=label, system=sysm)
    while True:
        if not q("select id from bench_runs where status='running'"):
            try:
                req = urllib.request.Request(API + '/run', json.dumps(cfg).encode(), {'Content-Type': 'application/json'})
                rid = json.load(urllib.request.urlopen(req, timeout=60))['run_id']; break
            except urllib.error.HTTPError as e:
                print('reintento:', e.read()[:200], flush=True)
        time.sleep(30)
    print('lanzada', rid, label, flush=True)
    while q("select status from bench_runs where id=%s", (rid,))[0][0] == 'running':
        time.sleep(20)
    print('terminó', rid, q("select status, done, n, metrics->>'pass_rate', metrics->>'errors' from bench_runs where id=%s", (rid,))[0], flush=True)
print('FIN', flush=True)
