"""Matriz de configuraciones en los 4 sets penales (3, 12, 13, 14), 2 repeticiones, para medir el ruido entre corridas
y si los cambios del 18–20 de octubre (filtro por estado, descomponer por delito, remisiones, tlacua-v1-penas) mejoran o
rompen algo. Base = configuración de la corrida 102 (la del estudio): híbrido, k 10 + vecinos, HyDE, descomponer.

    A  base, sin filtro                            (penal-original-v1)
    B  A + filtro por estado                       (penal-original-v1)
    C  B + descomponer por delito (+3) + remisiones (penal-original-v1)
    D  C con tlacua-v1-penas

Orden: repetición 1 de todo, luego repetición 2 (si se corta, la 1 ya está completa). Los criterios del juez salen de cada
set (bench_sets.judge_notes). Contra una copia exacta del código de prod en 8099."""
import json, sys, time, urllib.request
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect
def q(sql, args=()):
    with connect() as c, c.cursor() as cur:
        cur.execute(sql, args); return cur.fetchall()
prompt = {t: x for t, x in q("SELECT tag, text FROM bench_prompt_tags WHERE tag IN ('penal-original-v1', 'tlacua-v1-penas')")}
base = {'setting': 'híbrido', 'k': 10, 'neighbors': True, 'hyde': True, 'rerank': False, 'decompose': True, 'route': False,
        'jurisdictions': []}
configs = {
    'A': dict(base, gate=False, system=prompt['penal-original-v1']),
    'B': dict(base, gate=True, system=prompt['penal-original-v1']),
    'C': dict(base, gate=True, crimes=True, crime_extra_k=3, remisiones=True, system=prompt['penal-original-v1']),
    'D': dict(base, gate=True, crimes=True, crime_extra_k=3, remisiones=True, system=prompt['tlacua-v1-penas']),
}
nombre = {'A': 'base', 'B': '+ filtro', 'C': '+ filtro + por delito (+3) + remisiones', 'D': 'C con tlacua-v1-penas'}
for rep in (1, 2):
    for letra, cfg in configs.items():
        for sid in (13, 14, 3, 12):
            tag = 'tlacua-v1-penas' if letra == 'D' else 'penal-original-v1'
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
print('FIN', flush=True)
