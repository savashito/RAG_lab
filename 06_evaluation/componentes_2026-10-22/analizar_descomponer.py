"""¿Sirven «descomponer» y routing? B·v3 con descomponer (#179–#182), sin descomponer (#185/#186/#189/#190) y con
routing en lugar de descomponer (#187/#188/#191/#192), sets 3 y 14, 2 repeticiones cada uno. Separa las preguntas
COMPARATIVAS (las que NOMBRAN dos o más códigos o estados, con la regex del routing; independiente del LLM) de las demás,
y mide cuántas NO comparativas divide «descomponer» de todos modos (su prompt dice que no debe). Corre en el servidor."""
import json, sys, statistics as st
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect
from shared.object_store import store
from shared.code_routes import codes_in
def art(rid):
    with connect() as c, c.cursor() as cur:
        cur.execute("select artifact_key from bench_runs where id=%s", (rid,)); k = cur.fetchone()[0]
    return {r['question_id']: r for r in store.get_json(k.removeprefix(store.prefix))['results'] if not r.get('error')}
RUNS = {3: {'con descomponer': (179, 181), 'sin descomponer': (185, 189), 'routing': (187, 191)},
        14: {'con descomponer': (180, 182), 'sin descomponer': (186, 190), 'routing': (188, 192)}}
out = {}
for sid, cfgs in RUNS.items():
    A = {n: [art(r) for r in rs] for n, rs in cfgs.items()}
    qs = sorted(set.intersection(*[set(a) for v in A.values() for a in v]))
    pregunta = A['con descomponer'][0]
    comp = [q for q in qs if len({h['label'] for h in codes_in(pregunta[q]['question'])}) >= 2]
    resto = [q for q in qs if q not in comp]
    divide = lambda grupo: sum(len(a[q].get('subqueries') or []) >= 2 for a in A['con descomponer'] for q in grupo)  # noqa: E731
    out[sid] = {'n_comp': len(comp), 'n_resto': len(resto), 'divide_comp': divide(comp), 'divide_resto': divide(resto)}
    print(f'set {sid}: {len(comp)} comparativas, {len(resto)} no comparativas · «descomponer» dividió {divide(comp)} de '
          f'{2*len(comp)} respuestas comparativas y {divide(resto)} de {2*len(resto)} NO comparativas')
    for nombre, grupo in (('comparativas', comp), ('no comparativas', resto)):
        for cfg, runs in A.items():
            sc = st.mean(st.mean(a[q]['score'] for a in runs) for q in grupo) if grupo else None
            hit = sum((a[q].get('retrieval') or {}).get('hit', 0) for a in runs for q in grupo)
            att = sum((a[q].get('retrieval') or {}).get('attainable', 0) for a in runs for q in grupo)
            out[sid][f'{nombre}|{cfg}'] = {'score': sc, 'hit': hit, 'att': att}
            print(f'   {nombre:16} {cfg:16} score {sc*100:5.1f} · recall {hit}/{att} ({100*hit/att if att else 0:.0f} %)')
json.dump(out, open('/tmp/analizar_descomponer.json', 'w'))
