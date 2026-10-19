"""Set 12 de Karen (Control de tipicidad, 3 casos) con la configuración del estudio: 3 prompts (por etiqueta) × con/sin
compuerta. Espera a que no haya otra corrida. Contra la copia temporal 8099."""
import json, sys, time, urllib.request
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect
API = 'http://127.0.0.1:8099/api/bench'
def q(sql, args=()):
    with connect() as c, c.cursor() as cur:
        cur.execute(sql, args); return cur.fetchall()
CFG = {'setting': 'híbrido', 'k': 10, 'neighbors': True, 'hyde': True, 'decompose': True, 'route': True}
for tag in ('penal-original-v1', 'tlacua-v1', 'penal-sencillo-jur-v1'):
    text = q("SELECT text FROM bench_prompt_tags WHERE tag = %s", (tag,))[0][0]
    for gate in (False, True):
        cfg = dict(CFG, set_id=12, gate=gate, system=text,
                   label=f'set12-estudio-2026-10-19 · {tag}' + (' + compuerta' if gate else ''))
        while q("select id from bench_runs where status='running'"):
            time.sleep(20)
        req = urllib.request.Request(API + '/run', json.dumps(cfg).encode(), {'Content-Type': 'application/json'})
        rid = json.load(urllib.request.urlopen(req, timeout=60))['run_id']
        print('lanzada', rid, cfg['label'], flush=True)
        time.sleep(10)
        while q("select status from bench_runs where id=%s", (rid,))[0][0] == 'running':
            time.sleep(15)
        print('terminó', rid, q("select status, metrics->>'score', metrics->>'must_coverage', metrics->>'violations', metrics->>'errors' from bench_runs where id=%s", (rid,))[0], flush=True)
print('FIN', flush=True)
