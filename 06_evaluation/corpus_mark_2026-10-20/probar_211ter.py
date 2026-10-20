"""Tras la reingesta (6312911): ¿el buscador entrega el 211 Ter del Estado de México y el LLM lo cita? Corre la pregunta
del video íntimo por WhatsApp (set 14, q374) con penal-original-v1, configuración de Karen + filtro por estado.
Contra una copia exacta del código de prod en 8099."""
import json, sys, time, urllib.request
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect
from shared.object_store import store
def q(sql, args=()):
    with connect() as c, c.cursor() as cur:
        cur.execute(sql, args); return cur.fetchall()
text = q("SELECT text FROM bench_prompt_tags WHERE tag = 'penal-original-v1'")[0][0]
cfg = {'setting': 'orig', 'k': 10, 'neighbors': True, 'hyde': True, 'decompose': False, 'route': False, 'gate': True,
       'set_id': 14, 'system': text, 'question_ids': [374], 'subset': 'q374 (211 Ter)',
       'label': 'corpus-mark-2026-10-20 · 211 Ter · penal-original-v1 + filtro'}
req = urllib.request.Request('http://127.0.0.1:8099/api/bench/run', json.dumps(cfg).encode(), {'Content-Type': 'application/json'})
rid = json.load(urllib.request.urlopen(req, timeout=60))['run_id']
time.sleep(10)
while q("select status from bench_runs where id=%s", (rid,))[0][0] == 'running':
    time.sleep(5)
key, = q("select artifact_key from bench_runs where id=%s", (rid,))[0]
d = store.get_json(key)['results'][0]
print('corrida', rid, '· score', d.get('score'))
print('artículos en el contexto:', [(ch.get('source', '')[:30], (ch.get('hierarchy') or '').split(' > ')[-1]) for ch in d.get('chunks', [])][:12])
print('respuesta:', (d.get('answer') or '')[:900].replace('\n', ' / '))
