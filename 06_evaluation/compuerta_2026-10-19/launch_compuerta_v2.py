"""Compuerta v2 (decide si la respuesta depende del estado). 1) Agrega al set 14 las preguntas nuevas de
set_jurisdiccion_inteligente.json (las que aún no están, por texto) y actualiza nombre y descripción. 2) Corre solo las
categorías sin_lugar y nacional con penal-original-v1 y penal-sencillo-jur-v1 + compuerta, misma configuración que
#52/#53. Contra la copia temporal 8099."""
import json, sys, time, urllib.error, urllib.request
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect
API = 'http://127.0.0.1:8099/api/bench'
def q(sql, args=()):
    with connect() as c, c.cursor() as cur:
        cur.execute(sql, args); return cur.fetchall()
def post(path, obj):
    req = urllib.request.Request(API + path, json.dumps(obj).encode(), {'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(req, timeout=60))
spec = json.load(open('/tmp/set_jurisdiccion_inteligente.json'))
ya = {r[0] for r in q("SELECT question FROM bench_questions WHERE set_id = 14")}
nuevas = [x for x in spec['questions'] if x['question'] not in ya]
for x in nuevas:
    print('agregada', post('/sets/14/questions', x)['id'], x['question'][:70], flush=True)
post('/sets/14', {'name': spec['name'], 'description': spec['description']})
ids = [r[0] for r in q("SELECT id FROM bench_questions WHERE set_id = 14 AND (notes LIKE '%%cat=sin_lugar%%' OR notes LIKE '%%cat=nacional%%') ORDER BY position, id")]
print('preguntas a correr:', len(ids), flush=True)
CFG = {'setting': 'híbrido', 'k': 10, 'neighbors': True, 'hyde': True, 'decompose': True, 'route': True, 'gate': True,
       'question_ids': ids, 'subset': 'sin_lugar + nacional'}
for tag in ('penal-original-v1', 'penal-sencillo-jur-v1'):
    text = q("SELECT text FROM bench_prompt_tags WHERE tag = %s", (tag,))[0][0]
    cfg = dict(CFG, set_id=14, label=f'compuerta-v2-2026-10-19 · {tag} + compuerta', system=text)
    while q("select id from bench_runs where status='running'"):
        time.sleep(30)
    rid = post('/run', cfg)['run_id']
    print('lanzada', rid, cfg['label'], flush=True)
    while q("select status from bench_runs where id=%s", (rid,))[0][0] == 'running':
        time.sleep(20)
    print('terminó', rid, q("select status, done, n, metrics->>'errors' from bench_runs where id=%s", (rid,))[0], flush=True)
print('FIN', flush=True)
