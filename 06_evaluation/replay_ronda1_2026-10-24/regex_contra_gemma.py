"""¿Cuántas peticiones de lugar se le escapan a la regex (jurisdiction_gate.pregunta_de_lugar)? Compara, en respuestas
reales del asistente, lo que saca la regex con lo que dice Gemma. Las respuestas son del asistente (no de participantes).
Imprime agregados y ejemplos de los desacuerdos.
    python regex_contra_gemma.py            → las 216 primeras respuestas con filtro (B_filtro y C_nuevo, repetición 1)
    python regex_contra_gemma.py --todas    → además: todos los mensajes de todas las repeticiones con filtro y las
                                              respuestas de los benchmarks #211–#242 (sets 3, 12, 13, 14)"""
import sys, os, json, re
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
os.chdir('/home/tlacua/apps/RAG_lab/apps/rewrite_lab')
import main
import jurisdiction_gate as jg
SISTEMA = ('Lees la respuesta de un asistente jurídico a una persona. ¿Al final de la respuesta, o en algún lugar, el asistente '
           'le PIDE a la persona que diga dónde ocurrieron los hechos (el estado, la ciudad o el lugar)? Cuenta preguntas («¿en qué '
           'estado pasó?») y peticiones («indícame dónde ocurrió»). No cuenta si solo explica que la ley depende del estado sin '
           'pedirlo. Devuelve SOLO JSON: {"pide_lugar": true|false, "frase": "<la frase exacta con la que lo pide, o vacío>"}')
TODAS = '--todas' in sys.argv
with main.connect() as c, c.cursor() as cur:
    if TODAS:
        cur.execute("""SELECT t->>'respuesta', 'ronda 1 real · ' || r.nombre FROM rep_conversaciones v JOIN rep_corridas r ON r.id = v.corrida_id,
                       jsonb_array_elements(v.turnos) t WHERE (r.config->>'filtro_estado')::bool ORDER BY v.id""")
        respuestas = [(r, f) for r, f in cur.fetchall() if r]
        cur.execute("SELECT id, artifact_key FROM bench_runs WHERE id BETWEEN 211 AND 242 AND artifact_key IS NOT NULL")
        from shared.object_store import store
        for rid, k in cur.fetchall():
            for x in store.get_json(k.removeprefix(store.prefix))['results']:
                if x.get('answer'):
                    respuestas.append((x['answer'], f'benchmark #{rid}'))
    else:
        cur.execute("""SELECT v.turnos->0->>'respuesta', r.nombre FROM rep_conversaciones v JOIN rep_corridas r ON r.id = v.corrida_id
                       WHERE r.nombre IN ('B_filtro', 'C_nuevo') AND r.repeticion = 1 ORDER BY v.id""")
        respuestas = [(r, f) for r, f in cur.fetchall() if r]
tabla = {(True, True): 0, (True, False): 0, (False, True): 0, (False, False): 0}
escapan, sobran = [], []
from collections import Counter
por_fuente = Counter()
for r, fuente in respuestas:
    rx = jg.pregunta_de_lugar(r)
    try:
        d = jg._json(main.llm.chat(SISTEMA, r, temperature=0.0, max_tokens=200, timeout=60)) or {}
    except Exception:
        d = {}
    g = bool(d.get('pide_lugar'))
    tabla[(g, rx is not None)] += 1
    if g and rx is None:
        escapan.append(d.get('frase')); por_fuente[('se escapa', fuente.split(' · ')[0])] += 1
    if rx is not None and not g:
        sobran.append(rx); por_fuente[('sobra', fuente.split(' · ')[0])] += 1
n = len(respuestas)
print(f'{n} respuestas del asistente' + (' (todas las fuentes)' if TODAS else ' (primer mensaje, con filtro)'))
print(f'  Gemma: pide el lugar · regex lo encuentra : {tabla[(True, True)]}')
print(f'  Gemma: pide el lugar · regex NO lo ve     : {tabla[(True, False)]}   ← se le escapan a la regex')
print(f'  Gemma: no pide        · regex encuentra algo: {tabla[(False, True)]}   ← la regex ve una petición que Gemma no')
print(f'  Gemma: no pide        · regex nada         : {tabla[(False, False)]}')
print('Desacuerdos por fuente:', dict(por_fuente))
print('\nFrases que se le escapan a la regex (según Gemma):'); [print('  -', f) for f in escapan[:40]]
print('\nFrases que la regex ve y Gemma no:'); [print('  -', f) for f in sobran[:40]]
