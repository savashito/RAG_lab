"""Set 14: ¿por qué ultimo-promt cumple menos «Cita el art. …» que penal-original-v1? Revisa las respuestas guardadas
(mismas preguntas, misma configuración de la ronda 2, 2 repeticiones cada uno). Corre en prod (lee el object store)."""
import sys, re, collections
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect
from shared.object_store import store
def art(rid):
    with connect() as c, c.cursor() as cur:
        cur.execute('SELECT artifact_key FROM bench_runs WHERE id = %s', (rid,)); k = cur.fetchone()[0]
    return store.get_json(k.removeprefix(store.prefix))['results']
FUND = re.compile(r'(?im)^\W*fundamento')
ART = re.compile(r'(?i)\bart(?:[íi]culo|\.)s?\s*\d')
PREG = re.compile(r'¿[^?]*\?')
V = {'penal-original-v1': (215, 223), 'ultimo-promt': (229, 233), 'ultimo-promt-v2': (237, 241)}
for nombre, rids in V.items():
    c = collections.Counter()
    for rid in rids:
        for x in art(rid):
            if x.get('error'):
                continue
            ans = x.get('answer') or ''
            c['n'] += 1; c['fund'] += bool(FUND.search(ans)); c['pal'] += len(ans.split())
            c['con_art'] += bool(ART.search(ans)); c['preg'] += len(PREG.findall(ans))
            for v in x.get('verdicts') or []:
                if v['kind'] == 'must' and re.match(r'(?i)\s*cita', v['text']):
                    c['cn'] += 1; ok = v.get('verdict') == 'presente'; c['cok'] += ok
                    if not ok:
                        c['falla'] += 1; c['falla_sin_art'] += not ART.search(ans)
    print(f"{nombre}: respuestas {c['n']} · sección Fundamento {100*c['fund']/c['n']:.0f} % · con algún número de artículo "
          f"{100*c['con_art']/c['n']:.0f} % · «Cita el art.» {c['cok']}/{c['cn']} ({100*c['cok']/c['cn']:.0f} %) · "
          f"de los que fallan, sin ningún artículo {c['falla_sin_art']}/{c['falla']} · palabras {c['pal']/c['n']:.0f} · "
          f"preguntas a la persona {c['preg']/c['n']:.1f}")
