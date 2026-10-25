"""«fotos» con la configuración de la ronda 2 (filtro + descomponer + HyDE + rerank), con todos los documentos y con los
apagados en prod: por artículo esperado, cuántas veces entra en los 10 primeros resultados del buscador, y qué
documentos ocupan esos 10 lugares. Mismos casos que recall_apagar_fuentes.py, solo «fotos». Solo agregados.
    python fotos_detalle_apagados.py /ruta/a/apps/rewrite_lab"""
import sys, os
from collections import Counter
APP = sys.argv[1] if len(sys.argv) > 1 else '/home/tlacua/apps/RAG_lab/apps/rewrite_lab'
sys.path[:0] = [APP, os.path.dirname(os.path.dirname(APP))]
os.chdir(APP)
import main
from study.validar import escenario_efectivo

TEMA, CORRIDA = 'derecho_penal_mexicano', 30
APAGAR = set(main.APAGADAS)
spec = main.study_store.spec('piloto_penal')
ef = escenario_efectivo(next(e for e in spec['escenarios'] if e['id'] == 'fotos'), None)
gold = [g for g in main._study_resolver([g for x in ef.get('gold') or [] for g in main._study_gold_refs(x)]) if any(x.get('ids') for x in g)]
nombres = [f"{g[0].get('article')} · {g[0].get('source', '')[:45]}" for g in gold]

c = main.connect()
c.autocommit = True
cur = c.cursor()
d = main.study_store.export('piloto_penal')
intento = {i['id']: i for i in d['intentos']}
casos = [(t['pregunta'], t['pregunta']) for t in d['turnos'] if t['n'] == 1 and intento[t['intento_id']]['escenario'] == 'fotos']
cur.execute("SELECT r.salida, k.esperado FROM comp_resultados r JOIN comp_casos k ON k.id = r.caso_id "
            "WHERE r.corrida_id = %s AND r.error IS NULL ORDER BY r.id", (CORRIDA,))
for salida, esperado in cur.fetchall():
    if salida['tipos'][0] != 'situación fotos':
        continue
    cur.execute("SELECT t.intento_id, t.n FROM estudio_turnos t WHERE t.id = %s", (int(esperado['turno_id']),))
    fila = cur.fetchone()
    if not fila:
        continue
    cur.execute("SELECT pregunta FROM estudio_turnos WHERE intento_id = %s AND n <= %s ORDER BY n", fila)
    casos.append((salida['textos']['reescritura v1'], '\n'.join(p for (p,) in cur.fetchall())))

for nombre, apagar in {'todos los documentos': set(), f'{len(APAGAR)} documentos apagados (prod)': APAGAR}.items():
    main.APAGADAS.clear(); main.APAGADAS.update(apagar)
    por_art, fuentes = Counter(), Counter()
    for texto, texto_filtro in casos:
        jur = main.gate_for(texto_filtro, TEMA)['jurisdictions']
        scored, _, _ = main.retrieve_ranked(cur, texto, 'híbrido', TEMA, jur, True, True, True, True)
        ids = [cid for cid, _ in scored]
        chk = main.retrieval_check(gold, ids[:50])
        for n_, g in zip(nombres, chk['groups']):
            por_art[n_] += bool(g['rank'] and g['rank'] <= 10)
        for i in ids[:10]:
            fuentes[(main.DOC_BY_ID.get(i) or {}).get('source', '?')[:70]] += 1
    print(f'== {nombre} · {len(casos)} casos de «fotos» (primeros mensajes y siguientes)', flush=True)
    for n_ in nombres:
        print(f'   en los 10 primeros: {n_}: {por_art[n_]} de {len(casos)}')
    print(f'   documentos en los 10 primeros (de {10 * len(casos)} lugares):')
    for s, k in fuentes.most_common(12):
        print(f'      {k:4d}  {s}')
c.close()
