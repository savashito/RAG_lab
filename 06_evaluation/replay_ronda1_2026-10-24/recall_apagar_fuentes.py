"""¿Qué pasa con el recall si se apagan documentos (📥 Ingestar → ⏸ apagar)? Configuración de la ronda 2 (versión 12:
filtro + descomponer + HyDE + rerank), con y sin APAGAR, sobre los mismos casos que recall_sin_rerank.py:
  1. Primeros mensajes reales de la ronda 1.
  2. Mensajes siguientes: casos de la corrida #30, con el texto que escribió la reescritura v1 en esa corrida.
Las dos variantes corren en este mismo proceso (cambia solo main.APAGADAS); no toca la tabla de documentos apagados.
Revisa además que ningún resultado venga de un documento apagado. Conexión en autocommit. Imprime solo agregados.
    python recall_apagar_fuentes.py /ruta/a/apps/rewrite_lab"""
import sys, os, time, statistics as st
from collections import defaultdict
APP = sys.argv[1] if len(sys.argv) > 1 else '/home/tlacua/apps/RAG_lab/apps/rewrite_lab'
sys.path[:0] = [APP, os.path.dirname(os.path.dirname(APP))]
os.chdir(APP)
import main
from study.validar import escenario_efectivo

# Lo apagado en prod (tabla fuentes_apagadas) al arrancar este proceso. El 25-oct: la Ley General de Acceso de las
# Mujeres y «Violencia Digital» (dependen de quién es la persona, igual que los códigos penales de dónde pasó) y lo que
# Karen quitó por no tener que ver con el estudio (derecho ambiental, ficha de la Ley Olimpia, etc.).
# Con un segundo argumento «sin-referencia» no repite la variante con todos los documentos.
APAGAR = set(main.APAGADAS)
VARIANTES = {'todos los documentos': set(), f'como está prod ({len(APAGAR)} documentos apagados)': APAGAR}
if len(sys.argv) > 2 and sys.argv[2] == 'sin-referencia':
    del VARIANTES['todos los documentos']
print('apagados:', sorted(APAGAR), flush=True)
TEMA, CORRIDA = 'derecho_penal_mexicano', 30
_gold = {}


def gold_de(estudio, esc, var):
    if (estudio, esc, var) not in _gold:
        spec = main.study_store.spec(estudio)
        ef = escenario_efectivo(next(e for e in spec['escenarios'] if e['id'] == esc), var)
        _gold[(estudio, esc, var)] = [g for g in main._study_resolver([g for x in ef.get('gold') or [] for g in main._study_gold_refs(x)])
                                      if any(x.get('ids') for x in g)]
    return _gold[(estudio, esc, var)]


c = main.connect()
c.autocommit = True
cur = c.cursor()
d = main.study_store.export('piloto_penal')
intento = {i['id']: i for i in d['intentos']}
casos = []   # (parte, situación, texto de búsqueda, texto del filtro, gold)
for t in d['turnos']:
    if t['n'] == 1:
        i = intento[t['intento_id']]
        casos.append(('primeros mensajes', f"situación {i['escenario']}{' ' + i['variante'] if i['variante'] else ''}",
                      t['pregunta'], t['pregunta'], gold_de('piloto_penal', i['escenario'], i['variante'])))
cur.execute("SELECT r.salida, k.esperado FROM comp_resultados r JOIN comp_casos k ON k.id = r.caso_id "
            "WHERE r.corrida_id = %s AND r.error IS NULL ORDER BY r.id", (CORRIDA,))
for salida, esperado in cur.fetchall():
    cur.execute("SELECT t.intento_id, t.n, i.escenario, i.variante, k.estudio FROM estudio_turnos t JOIN estudio_intentos i "
                "ON i.id = t.intento_id JOIN estudio_codigos k ON k.codigo = i.codigo WHERE t.id = %s", (int(esperado['turno_id']),))
    fila = cur.fetchone()
    if not fila:
        continue
    iid, n, esc, var, estudio = fila
    cur.execute("SELECT pregunta, respuesta FROM estudio_turnos WHERE intento_id = %s AND n <= %s ORDER BY n", (iid, n))
    msgs = []
    for p, r in cur.fetchall():
        msgs += [{'role': 'user', 'content': p}] + ([{'role': 'assistant', 'content': r}] if r else [])
    msgs = msgs[:-1] if msgs[-1]['role'] == 'assistant' else msgs
    casos.append(('mensajes siguientes', salida['tipos'][0], salida['textos']['reescritura v1'], main.gate_text(msgs),
                  gold_de(estudio, esc, var)))

for nombre, apagar in VARIANTES.items():
    main.APAGADAS.clear(); main.APAGADAS.update(apagar)
    tot, seg, fugas = defaultdict(lambda: [0, 0]), defaultdict(list), 0
    for parte, sit, texto, texto_filtro, gold in casos:
        t0 = time.time()
        jur = main.gate_for(texto_filtro, TEMA)['jurisdictions']
        scored, _, _ = main.retrieve_ranked(cur, texto, 'híbrido', TEMA, jur, True, True, True, True)
        seg[parte].append(time.time() - t0)
        ids = [cid for cid, _ in scored]
        fugas += sum(1 for i in ids if (main.DOC_BY_ID.get(i) or {}).get('source') in apagar)
        chk = main.retrieval_check(gold, ids[:50])
        h = sum(1 for g in chk['groups'] if g['rank'] and g['rank'] <= 10)
        for clave in (f'{parte} · todas', f'{parte} · {sit}'):
            tot[clave][0] += h; tot[clave][1] += len(gold)
    print(f'== {nombre} · filtro + descomponer + HyDE + rerank · resultados de documentos apagados: {fugas}', flush=True)
    for clave, (h, g) in sorted(tot.items()):
        print(f'   {clave}: {100 * h / g:.1f} % ({h} de {g})')
    for parte, xs in seg.items():
        print(f'   {parte}: {st.mean(xs):.1f} s por mensaje')
c.close()
