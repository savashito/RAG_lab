"""Vuelve a pasar las conversaciones REALES de la ronda 1 (piloto_penal) por el asistente del estudio, con tres
configuraciones que solo difieren en lo que se quiere medir:
  A  ronda 1:        sin filtro por estado, penal-original-v1
  B  + filtro v3:    con filtro, penal-original-v1          (A → B = efecto del filtro)
  C  ronda 2 nuevo:  con filtro, ultimo-promt-v2            (lo que verá la condición «nuevo»)
El resto es la configuración del estudio (híbrido, k 10, vecinos, HyDE, descomponer, routing, historial 10). Cada
conversación se repite en orden: los mensajes de la persona son los reales; las respuestas las escribe el asistente de
nuevo (y entran al historial). Cada respuesta se mide con study.analisis.analizar_respuesta (las métricas de la ronda 1,
sin juez) y se guarda la decisión del filtro.

Los mensajes de las personas NO salen del servidor: el resultado va a /tmp/replay_ronda1/ (fuera del repo); al repo solo
llega el resumen agregado (resumir_replay.py). Corre en prod con el código de prod (importa main, no levanta servidor):
    python repetir_ronda1.py [repeticiones] [config,config…] [--multiturno]
Configuraciones extra (24-oct): B_condensa_v2 y C_condensa_v2 = B y C con la búsqueda reescrita v2 (main.CONDENSE_SYSTEM_V2).
--multiturno: solo las conversaciones con 2+ mensajes (la búsqueda reescrita no cambia el primer mensaje)."""
import json, sys, time
from pathlib import Path
RAIZ = Path('/home/tlacua/apps/RAG_lab')
sys.path[:0] = [str(RAIZ / 'apps' / 'rewrite_lab'), str(RAIZ)]
import os; os.chdir(RAIZ / 'apps' / 'rewrite_lab')
import main                                          # noqa: E402  (carga .env, conexiones y el chat del estudio)
from study.analisis import analizar_respuesta         # noqa: E402
from study.validar import escenario_efectivo          # noqa: E402

args = [a for a in sys.argv[1:] if not a.startswith('--')]
REPS = int(args[0]) if args else 2
ELEGIDAS = args[1].split(',') if len(args) > 1 else ['A_ronda1', 'B_filtro', 'C_nuevo']
MULTITURNO = '--multiturno' in sys.argv
SALIDA = Path('/tmp/replay_ronda1'); SALIDA.mkdir(exist_ok=True)
def prompt(tag):
    with main.connect() as c, c.cursor() as cur:
        cur.execute('SELECT text FROM bench_prompt_tags WHERE tag = %s', (tag,)); return cur.fetchone()[0]
datos = main.study_store.export('piloto_penal')
spec = main.study_store.spec('piloto_penal')
base = dict(spec['asistente'])
CONFIGS = {'A_ronda1': dict(base, filtro_estado=False, sistema=prompt('penal-original-v1')),
           'B_filtro': dict(base, filtro_estado=True, sistema=prompt('penal-original-v1')),
           'C_nuevo': dict(base, filtro_estado=True, sistema=prompt('ultimo-promt-v2')),
           'B_condensa_v2': dict(base, filtro_estado=True, sistema=prompt('penal-original-v1'), condensa='v2'),
           'C_condensa_v2': dict(base, filtro_estado=True, sistema=prompt('ultimo-promt-v2'), condensa='v2')}
CONFIGS = {k: v for k, v in CONFIGS.items() if k in ELEGIDAS}
por_id = {e['id']: e for e in spec['escenarios']}
gold = {}
for i in datos['intentos']:
    clave = (i['escenario'], i['variante'])
    if clave not in gold and i['escenario'] in por_id:
        ef = escenario_efectivo(por_id[i['escenario']], i['variante'])
        gold[clave] = main._study_resolver([g for x in ef.get('gold') or [] for g in main._study_gold_refs(x)])
turnos = {}
for t in datos['turnos']:
    turnos.setdefault(t['intento_id'], []).append(t)
intentos = [i for i in datos['intentos'] if len(turnos.get(i['id']) or []) >= (2 if MULTITURNO else 1)]
print(f'{len(intentos)} conversaciones, {sum(len(turnos[i["id"]]) for i in intentos)} mensajes; {len(CONFIGS)} configuraciones × {REPS} repeticiones', flush=True)

for rep in range(1, REPS + 1):
    for nombre, cfg in CONFIGS.items():
        archivo = SALIDA / f'{nombre}_rep{rep}.jsonl'
        hechos = {json.loads(l)['intento_id'] for l in archivo.open()} if archivo.exists() else set()
        with archivo.open('a') as f:
            for i in intentos:
                if i['id'] in hechos:
                    continue
                msgs, filas = [], []
                for t in sorted(turnos[i['id']], key=lambda t: t['n']):
                    msgs.append({'role': 'user', 'content': t['pregunta']})
                    t0, partes, filtro, err, busqueda = time.time(), [], None, None, None
                    for ev in main._study_chat_stream(msgs, cfg):
                        st = ev.get('stage')
                        if st == 'token':
                            partes.append(ev.get('text') or '')
                        elif st == 'filtro':
                            filtro = {k: ev.get(k) for k in ('estados', 'otros', 'faltan', 'tipo')}
                        elif st == 'search':
                            busqueda = ev.get('query')
                        elif st == 'error':
                            err = ev.get('error')
                    resp = ''.join(partes)
                    msgs.append({'role': 'assistant', 'content': resp})
                    filas.append({'n': t['n'], 'turno_original': t['id'], 'segundos': round(time.time() - t0, 1), 'error': err,
                                  'filtro': filtro, 'busqueda': busqueda, 'respuesta': resp,
                                  'analisis': analizar_respuesta(resp, gold.get((i['escenario'], i['variante'])) or [])})
                f.write(json.dumps({'intento_id': i['id'], 'codigo': i['codigo'], 'escenario': i['escenario'],
                                    'variante': i['variante'], 'turnos': filas}, ensure_ascii=False) + '\n')
                f.flush()
        print(f'rep {rep} · {nombre}: listo', flush=True)
print('FIN', flush=True)
