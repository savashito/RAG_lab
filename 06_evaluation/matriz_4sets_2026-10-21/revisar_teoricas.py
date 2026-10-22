"""Filtro v3 (2026-10-22): en las preguntas teóricas sin estado del set 3, ¿la respuesta cita códigos estatales? ¿ofrece
ver el código del estado de la persona? Compara las corridas del v3 (#179, #181) con las del v2 (#147, #163). Se corre en
el servidor."""
import sys, re, json
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect
from shared.object_store import store
from shared.code_routes import codes_in
def art(rid):
    with connect() as c, c.cursor() as cur:
        cur.execute("select artifact_key from bench_runs where id=%s", (rid,)); k = cur.fetchone()[0]
    return {r['question_id']: r for r in store.get_json(k.removeprefix(store.prefix))['results']}
ESTATALES = {'CDMX', 'CPEM', 'Morelos', 'Querétaro'}
OFRECE = re.compile(r'(?i)(si me (dices|indicas|compartes)|en qu[eé] estado|tu estado|su estado|entidad federativa (en la que|donde)|qu[eé] estado)')
v3 = [art(179), art(181)]; v2 = [art(147), art(163)]
teo = sorted({q for r in v3 for q, x in r.items() if (x.get('gate') or {}).get('teorica') and not (x.get('gate') or {}).get('estados')})
print('preguntas teóricas sin estado en el set 3:', teo)
for q in teo:
    linea = []
    for nombre, runs in (('v3', v3), ('v2', v2)):
        for r in runs:
            x = r[q]; ans = x.get('answer') or ''
            est = sorted({h['label'] for h in codes_in(ans) if h['label'] in ESTATALES})
            linea.append(f"{nombre} {x.get('score'):.2f} estatales={est or '-'} ofrece={'sí' if OFRECE.search(ans[-600:]) else 'no'}")
    print(f"q{q}: {v3[0][q]['question'][:80]}\n   " + '\n   '.join(linea))
print('=====')
for q in (36, 9, 38):
    print(f'--- q{q} (#179), últimos 700 caracteres:\n' + (v3[0][q].get('answer') or '')[-700:])
print('--- nota del filtro q36:', (v3[0][36].get('gate') or {}).get('nota'))
print('#####')
OF2 = re.compile(r'(?i)(ind[ií]queme|indicarme|me indica|d[ií]game|me dices|me compart|su entidad|su estado|tu estado|tu entidad)')
for nombre, runs in (('v3', v3), ('v2', v2)):
    n = sum(1 for r in runs for q in teo if OF2.search(r[q].get('answer') or ''))
    print(nombre, 'ofrecen ver su estado:', n, 'de', 2 * len(teo), '·', [q for q in teo if any(OF2.search(r[q].get('answer') or '') for r in runs)])
