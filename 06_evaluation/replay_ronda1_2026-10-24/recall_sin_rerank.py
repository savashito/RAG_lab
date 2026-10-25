"""¿Cuánto aporta el rerank? Mide la configuración de la ronda 2 (filtro + descomponer + HyDE, SIN rerank) con los mismos
casos y artículos esperados de las dos pruebas que ya tenían «filtro + descomponer + HyDE + rerank»:
  1. Primeros mensajes reales de la ronda 1 (como recall_primer_mensaje.py).
  2. Mensajes siguientes: los casos de la corrida #30 de «💬 Reescritura multiturno · recall», buscando con el mismo
     texto que escribió la reescritura v1 en esa corrida (guardado en sus resultados; no se vuelve a reescribir), así
     que la comparación contra la corrida #30 solo cambia el rerank (y el borrador de HyDE, que se vuelve a escribir).
El filtro lee los mensajes de la persona (v1), como en la corrida #30. Conexión en autocommit: no deja transacciones
abiertas mientras llama a Gemma. Imprime solo agregados.
    python recall_sin_rerank.py"""
import sys, os, time, statistics as st
from collections import defaultdict
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
os.chdir('/home/tlacua/apps/RAG_lab/apps/rewrite_lab')
import main
from study.validar import escenario_efectivo

NOMBRE = 'filtro + descomponer + HyDE (sin rerank)'
TEMA = 'derecho_penal_mexicano'
CORRIDA = 30
_gold = {}


def gold_de(estudio, esc, var):
    if (estudio, esc, var) not in _gold:
        spec = main.study_store.spec(estudio)
        ef = escenario_efectivo(next(e for e in spec['escenarios'] if e['id'] == esc), var)
        _gold[(estudio, esc, var)] = [g for g in main._study_resolver([g for x in ef.get('gold') or [] for g in main._study_gold_refs(x)])
                                      if any(x.get('ids') for x in g)]
    return _gold[(estudio, esc, var)]


def buscar(cur, texto, texto_filtro, gold):
    t0 = time.time()
    jur = main.gate_for(texto_filtro, TEMA)['jurisdictions']
    scored, _, _ = main.retrieve_ranked(cur, texto, 'híbrido', TEMA, jur, True, True, False, True)
    chk = main.retrieval_check(gold, [cid for cid, _ in scored][:50])
    return sum(1 for g in chk['groups'] if g['rank'] and g['rank'] <= 10), time.time() - t0


def imprimir(titulo, tot, seg):
    print(f'== {titulo} · {NOMBRE} · {st.mean(seg):.1f} s por mensaje (filtro + HyDE + búsqueda)')
    for clave, (h, g) in sorted(tot.items()):
        print(f'   {clave}: {100 * h / g:.1f} % ({h} de {g})')


c = main.connect()
c.autocommit = True
cur = c.cursor()

# 1. Primeros mensajes de la ronda 1
d = main.study_store.export('piloto_penal')
intento = {i['id']: i for i in d['intentos']}
tot, seg = defaultdict(lambda: [0, 0]), []
for t in d['turnos']:
    if t['n'] != 1:
        continue
    i = intento[t['intento_id']]
    gold = gold_de('piloto_penal', i['escenario'], i['variante'])
    h, s = buscar(cur, t['pregunta'], t['pregunta'], gold)
    seg.append(s)
    for clave in ('todas', f"situación {i['escenario']}{' ' + i['variante'] if i['variante'] else ''}"):
        tot[clave][0] += h; tot[clave][1] += len(gold)
imprimir('Primeros mensajes de la ronda 1', tot, seg)

# 2. Mensajes siguientes: casos de la corrida #30, mismo texto de la reescritura v1
cur.execute("SELECT r.salida, k.esperado FROM comp_resultados r JOIN comp_casos k ON k.id = r.caso_id "
            "WHERE r.corrida_id = %s AND r.error IS NULL ORDER BY r.id", (CORRIDA,))
filas = cur.fetchall()
tot, seg, antes = defaultdict(lambda: [0, 0]), [], defaultdict(lambda: [0, 0])
for salida, esperado in filas:
    tid = int(esperado['turno_id'])
    cur.execute("SELECT t.intento_id, t.n, i.escenario, i.variante, k.estudio FROM estudio_turnos t JOIN estudio_intentos i "
                "ON i.id = t.intento_id JOIN estudio_codigos k ON k.codigo = i.codigo WHERE t.id = %s", (tid,))
    fila = cur.fetchone()
    if not fila:   # el turno ya no existe (la persona se retiró)
        continue
    iid, n, esc, var, estudio = fila
    cur.execute("SELECT pregunta, respuesta FROM estudio_turnos WHERE intento_id = %s AND n <= %s ORDER BY n", (iid, n))
    msgs = []
    for p, r in cur.fetchall():
        msgs += [{'role': 'user', 'content': p}] + ([{'role': 'assistant', 'content': r}] if r else [])
    msgs = msgs[:-1] if msgs[-1]['role'] == 'assistant' else msgs   # la respuesta al mensaje medido no cuenta
    gold = gold_de(estudio, esc, var)
    assert len(gold) == salida['gold'], (tid, len(gold), salida['gold'])
    h, s = buscar(cur, salida['textos']['reescritura v1'], main.gate_text(msgs), gold)
    seg.append(s)
    for clave in ('todas', salida['tipos'][0]):
        tot[clave][0] += h; tot[clave][1] += len(gold)
        antes[clave][0] += salida['aciertos']['reescritura v1 · filtro + descomponer + HyDE + rerank']; antes[clave][1] += len(gold)
imprimir(f'Mensajes siguientes (casos de la corrida #{CORRIDA}, texto de la reescritura v1)', tot, seg)
print(f'   corrida #{CORRIDA}, misma reescritura v1, filtro + descomponer + HyDE + rerank:')
for clave, (h, g) in sorted(antes.items()):
    print(f'   {clave}: {100 * h / g:.1f} % ({h} de {g})')
c.close()
