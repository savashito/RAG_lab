"""Análisis SIN LLM (regex + base) de corridas del set «Jurisdicción inteligente», por categoría. Uso en prod:
  python analizar.py <run_id> [<run_id> …]
Por respuesta: estados cuyos ARTÍCULOS cita (citations.extract), si pide el lugar (study.analisis._PIDE_LUGAR), y
según la categoría de la pregunta (notas «jur2 · cat=…»):
  sin_lugar        ✔ pide el lugar       ✘ cita algún código estatal
  un_estado        ✔ cita el estado      ✘ cita otro estado   ✘ vuelve a pedir el lugar
  lugar_indirecto  ✔ cita el estado      ✘ cita otro estado
  comparacion      ✔ cita TODOS los pedidos   ✘ cita uno no pedido   ✘ pide el lugar en vez de comparar
  nacional         ✘ pide el lugar       ✘ cita algún código estatal
  fuera_corpus     ✘ cita algún código estatal de la base (CDMX, Querétaro, Edomex, Morelos)
«Comportamiento correcto» = todos los ✔ y ningún ✘ de su categoría. Se compara con «pasa» del juez."""
import sys, re, json, collections, unicodedata
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect
from shared.object_store import store
# «Pide el lugar» = una PREGUNTA real por el estado o lugar (no frases explicativas como «depende del lugar donde ocurrió»).
_PIDE_LUGAR = re.compile(r'¿[^?]{0,140}\b(estado|entidad|ciudad|municipio|alcald[ií]a|lugar)\b[^?]{0,80}\?'
                         r'|(necesito|necesitar[ií]a|es (muy )?importante|es indispensable|me ayudar[ií]a)\s+(saber|conocer)[^.\n]{0,60}\b(estado|entidad|ciudad|municipio|lugar)\b'
                         r'|(dime|ind[ií]came|podr[ií]as decirme|confirma(me)?|me dices)[^.\n]{0,60}\b(estado|entidad|ciudad|municipio|lugar)\b')
import citations as cit
fold = lambda t: ''.join(ch for ch in unicodedata.normalize('NFKD', (t or '').lower()) if not unicodedata.combining(ch))
def evaluar(cat, esperados, ans):
    citados = {c['label'] for c in cit.extract(ans) if c['label'] in cit.ESTADOS}
    pide = bool(_PIDE_LUGAR.search(fold(ans)))
    e = set(esperados)
    reglas = {
        'sin_lugar':       {'pide el lugar': pide, 'NO cita código estatal': not citados},
        'un_estado':       {'cita el estado': bool(citados & e), 'NO cita otro estado': not (citados - e), 'NO vuelve a pedir el lugar': not pide},
        'lugar_indirecto': {'cita el estado': bool(citados & e), 'NO cita otro estado': not (citados - e)},
        'comparacion':     {'cita todos los pedidos': e <= citados, 'NO cita un estado no pedido': not (citados - e)},   # pedir el lugar Y responder no es falla
        'nacional':        {'NO pide el lugar': not pide, 'NO cita código estatal': not citados},
        'fuera_corpus':    {'NO cita código estatal de la base': not citados},
    }[cat]
    return reglas, citados, pide
for rid in map(int, sys.argv[1:]):
    with connect() as c, c.cursor() as cur:
        cur.execute("SELECT label, set_id, artifact_key FROM bench_runs WHERE id=%s", (rid,)); label, sid, key = cur.fetchone()
        cur.execute("SELECT id, notes FROM bench_questions WHERE set_id=%s", (sid,)); notas = dict(cur.fetchall())
    art = store.get_json(key)
    por_cat = collections.defaultdict(list)
    for r in art['results']:
        if r.get('error'):
            continue
        n = notas.get(r['question_id']) or ''
        cat = re.search(r'cat=(\w+)', n).group(1)
        esperados = (re.search(r'estados=([^ ·]+)', n) or [None, ''])[1].split(',') if 'estados=' in n else []
        reglas, citados, pide = evaluar(cat, esperados, r.get('answer') or '')
        por_cat[cat].append(dict(q=r['question_id'], reglas=reglas, ok=all(reglas.values()), juez=bool(r.get('passed')),
                                 citados=sorted(citados), pide=pide))
        por_cat['_pide'].append(dict(cat=cat, pide=pide))
    print(f'\n### run {rid} · {label}')
    tot_ok = tot = 0
    for cat in ('sin_lugar', 'un_estado', 'lugar_indirecto', 'comparacion', 'nacional', 'fuera_corpus'):
        fs = por_cat.get(cat) or []
        if not fs: continue
        ok = sum(f['ok'] for f in fs); tot_ok += ok; tot += len(fs)
        detalle = ' · '.join(f"{k} {sum(f['reglas'][k] for f in fs)}/{len(fs)}" for k in fs[0]['reglas'])
        print(f"  {cat:16} correcto (regex) {ok}/{len(fs)} ({ok/len(fs):.0%}) · pasa (juez) {sum(f['juez'] for f in fs)}/{len(fs)} · {detalle}")
        for f in fs:
            if not f['ok']:
                print(f"      q{f['q']}: falla {[k for k, v in f['reglas'].items() if not v]} · cita {f['citados']} · pide lugar={f['pide']}")
    print(f"  TOTAL correcto (regex) {tot_ok}/{tot} ({tot_ok/max(tot,1):.0%})")
    pc = [x for x in por_cat['_pide'] if x['cat'] == 'comparacion']
    print(f"  (comparación: además pidió el lugar en {sum(x['pide'] for x in pc)}/{len(pc)}, aunque respondió)")
    todos = [f for k, v in por_cat.items() if k != '_pide' for f in v]
    print(f"  acuerdo regex ↔ juez (correcto vs pasa): {sum(f['ok'] == f['juez'] for f in todos)}/{len(todos)}")
    json.dump(por_cat, open(f'/tmp/jur2_run{rid}.json', 'w'), ensure_ascii=False, indent=1)
