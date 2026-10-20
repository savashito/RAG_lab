"""tlacua-v1-penas = tlacua-v1 + sección «7. Penas». La etiqueta en bench_prompt_tags (si no existe) y corre el set 12 con
la configuración de Karen (#50) + filtro + seguir remisiones, 2 repeticiones. Comparar con #97/#98 (igual con tlacua-v1).
Contra una copia exacta del código de prod en 8099."""
import hashlib, json, sys, time, urllib.request
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect
def q(sql, args=(), commit=False):
    with connect() as c, c.cursor() as cur:
        cur.execute(sql, args)
        out = cur.fetchall() if cur.description else None
        if commit: c.commit()
        return out
text = open('/tmp/tlacua-v1-penas.txt', encoding='utf-8').read().strip()
md5 = hashlib.md5(text.encode()).hexdigest()
nota = 'tlacua-v1 + sección «7. Penas»: indicar prisión y multa con artículo y fracción cuando estén en el CONTEXTO, como rangos (no condena segura).'
if not q("SELECT 1 FROM bench_prompt_tags WHERE md5 = %s", (md5,)):
    q("INSERT INTO bench_prompt_tags (md5, tag, note, text, created_by, updated_by) VALUES (%s,%s,%s,%s,%s,%s)",
      (md5, 'tlacua-v1-penas', nota, text, 'rodrigosavagerower@gmail.com', 'rodrigosavagerower@gmail.com'), commit=True)
    q("INSERT INTO bench_prompt_tags_history (md5, action, tag, note, changed_by) VALUES (%s,'crear',%s,%s,%s)",
      (md5, 'tlacua-v1-penas', nota, 'rodrigosavagerower@gmail.com'), commit=True)
print('etiqueta:', q("SELECT tag, left(md5, 8) FROM bench_prompt_tags WHERE md5 = %s", (md5,)), flush=True)
for rep in (1, 2):
    cfg = {'setting': 'orig', 'k': 10, 'neighbors': True, 'hyde': True, 'decompose': False, 'route': False, 'gate': True,
           'remisiones': True, 'set_id': 12, 'system': text,
           'label': f'set12-penas · tlacua-v1-penas · karen50 + filtro + remisiones · rep {rep}'}
    while q("select id from bench_runs where status='running'"):
        time.sleep(15)
    req = urllib.request.Request('http://127.0.0.1:8099/api/bench/run', json.dumps(cfg).encode(), {'Content-Type': 'application/json'})
    rid = json.load(urllib.request.urlopen(req, timeout=60))['run_id']
    time.sleep(10)
    while q("select status from bench_runs where id=%s", (rid,))[0][0] == 'running':
        time.sleep(10)
    print(rid, cfg['label'], q("select metrics->>'score', metrics->>'must_coverage', metrics->>'violations', metrics->>'retrieval_recall' from bench_runs where id=%s", (rid,))[0], flush=True)
print('FIN', flush=True)
