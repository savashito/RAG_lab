"""Prueba de la llamada de HyDE. Su objetivo: que el buscador encuentre el artículo correcto. Sin juez.
1. Recall del buscador híbrido CON y SIN HyDE, pregunta por pregunta (sets 3, 13 y 14; artículos esperados de los
   criterios «Cita el art.»): R@10 y en cuántos artículos HyDE sube o baja la posición.
2. Reglas del prompt de HyDE, revisadas con regex en los borradores guardados de la matriz (#107–#178): no inventar
   números de artículo ni nombrar estados.
Corre en el servidor sobre la copia temporal (/tmp/rltest), sin la app arrancada."""
import json, os, re, sys, collections
os.chdir('/tmp/rltest/apps/rewrite_lab'); sys.path[:0] = ['.', '../..']
import main as M, bench as B
from shared.code_routes import codes_in
from shared.object_store import store
out = {'recall': {}, 'borradores': {}}
with M.connect() as c, c.cursor() as cur:
    for sid in (3, 13, 14):
        s = B.Bench.load_set(type('X', (), {'topic_label': lambda self, t: t})(), cur, sid)
        cuenta = collections.Counter()
        for q in s['questions']:
            gold = [g for g in B.resolve_gold(cur, M.TABLE, B.gold_refs(q['question'], B.effective_components(q))) if any(x.get('ids') for x in g)]
            if not gold:
                continue
            rangos = {}
            for hyde in (False, True):
                scored, _, _ = M.retrieve_ranked(cur, q['question'], 'híbrido', s['topic'], None, True, hyde, False, False)
                rangos[hyde] = [g['rank'] for g in B.retrieval_check(gold, [cid for cid, _ in scored][:50])['groups']]
            for a, b in zip(rangos[False], rangos[True]):
                cuenta['n'] += 1
                cuenta['sin@10'] += bool(a and a <= 10); cuenta['con@10'] += bool(b and b <= 10)
                ra, rb = a or 99, b or 99
                cuenta['mejora'] += rb < ra; cuenta['empeora'] += rb > ra
        out['recall'][sid] = dict(cuenta)
        print(f"set {sid}: {cuenta['n']} artículos · R@10 sin HyDE {cuenta['sin@10']/cuenta['n']:.3f} · con HyDE "
              f"{cuenta['con@10']/cuenta['n']:.3f} · HyDE sube la posición en {cuenta['mejora']}, la baja en {cuenta['empeora']}", flush=True)
    cur.execute("select artifact_key from bench_runs where id between 107 and 178 and status='done'")
    claves = [r[0] for r in cur.fetchall()]
ART = re.compile(r'(?i)\bart[íi]culos?\s+\d+|\bart\.\s*\d+')
c = collections.Counter()
for k in claves:
    for x in store.get_json(k.removeprefix(store.prefix))['results']:
        h = x.get('hyde_passage')
        if not h:
            continue
        c['n'] += 1
        c['articulo'] += bool(ART.search(h))
        pregunta_estados = {r['label'] for r in codes_in(x['question'])}
        c['estado'] += bool({r['label'] for r in codes_in(h)} - pregunta_estados - {'CPF', 'CNPP'})
out['borradores'] = dict(c)
print(f"borradores: {c['n']} · con número de artículo {c['articulo']} ({100*c['articulo']/c['n']:.1f} %) · "
      f"nombran un estado que la pregunta no nombra {c['estado']} ({100*c['estado']/c['n']:.1f} %)", flush=True)
json.dump(out, open('/tmp/prueba_hyde.json', 'w'))
