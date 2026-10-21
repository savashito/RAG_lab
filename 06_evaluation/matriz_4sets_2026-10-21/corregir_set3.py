"""Set 3: corrige dos errores claros que encontró una revisión externa (2026-10-21), sin cambiar nada más:

1. Criterios duplicados: en 11 preguntas la misma cita está como `should` («Cita el artículo 180…») y como `must`
   («Cita el art. 180…»), así que una respuesta sin el artículo pierde dos veces. Se borra el `should` cuando sus
   artículos ya están en un `must` de cita de la misma pregunta.
2. Pregunta «¿prescribe la acción penal por abuso sexual de menores, estupro y violación equiparada?» (CPF): la respuesta
   esperada fundaba en el art. 266 Ter, que habla de las SANCIONES. La regla de la ACCIÓN PENAL es el art. 107 Bis,
   tercer párrafo (texto del corpus, reforma DOF 18-10-2023). La conclusión («no prescriben») no cambia.

Respaldo previo en _bak_20261021_set3_questions / _bak_20261021_set3_components. Después correr recalificar_set3.py.
Corre en prod:  cd ~/apps/RAG_lab/apps/rewrite_lab && ../../.venv/bin/python ../../06_evaluation/matriz_4sets_2026-10-21/corregir_set3.py [--aplicar]"""
import re, sys
from dotenv import load_dotenv; load_dotenv('.env')
sys.path[:0] = ['.', '../..']
from shared.db import connect

APLICAR = '--aplicar' in sys.argv
SET = 3
ART = re.compile(r'(?i)art(?:[íi]culos?|s?\.)\s*(\d+(?:\s*(?:bis|ter|qu[aá]ter))?(?:\s*(?:,|y)\s*\d+(?:\s*(?:bis|ter|qu[aá]ter))?)*)')


def articulos(texto):
    return {re.sub(r'\s+', ' ', a.lower()).strip() for m in ART.finditer(texto) for a in re.split(r'\s*(?:,|\by\b)\s*', m.group(1)) if a}


PRESCRIBE_Q = 'Conforme al Código Penal Federal, ¿prescribe la acción penal por abuso sexual de menores, estupro y violación equiparada?'
PRESCRIBE_ESPERADA = (
    'No. El art. 107 Bis del CPF (tercer párrafo) establece que, en los delitos contra la libertad y el normal desarrollo '
    'psicosexual cometidos contra una persona menor de dieciocho años, los delitos de los artículos 261 (abuso sexual de '
    'menores o incapaces), 262 (estupro) y 266 (violación equiparada) son imprescriptibles; para los demás, el plazo de '
    'prescripción de la acción penal empieza a correr cuando la víctima cumple la mayoría de edad. Además, el art. 266 Ter '
    'declara imprescriptibles las sanciones de esos mismos artículos (prescripción de la pena, que es distinta de la '
    'prescripción de la acción penal). Ambos textos vienen de la reforma publicada en el DOF el 18-10-2023.')
PRESCRIBE_COMPONENTES = [   # (tipo, peso, texto)
    ('must', 2.0, 'La acción penal por esos delitos no prescribe (son imprescriptibles)'),
    ('must', 1.0, 'Cita el art. 107 Bis del Código Penal Federal (prescripción de la acción penal)'),
    ('must', 1.0, 'Se refiere a los artículos 261, 262 y 266'),
    ('should', 1.0, 'Menciona el artículo 266 Ter del CPF (imprescriptibilidad de las sanciones)'),
    ('should', 1.0, 'Distingue la prescripción de la acción penal de la prescripción de las sanciones, o dice que la regla aplica cuando la víctima es menor de 18 años'),
    ('must_not', 1.0, 'Da un plazo de prescripción para esos delitos'),
]

with connect() as c, c.cursor() as cur:
    cur.execute("SELECT q.id, k.id, k.kind, k.text FROM bench_components k JOIN bench_questions q ON q.id = k.question_id "
                "WHERE q.set_id = %s ORDER BY q.id, k.position", (SET,))
    por = {}
    for qid, kid, kind, text in cur.fetchall():
        por.setdefault(qid, []).append((kid, kind, text))
    borrar = []
    for qid, comps in por.items():
        en_must = set().union(*[articulos(t) for _, k, t in comps if k == 'must' and re.match(r'(?i)\s*cita\b', t)] or [set()])
        for kid, kind, text in comps:
            a = articulos(text)
            if kind == 'should' and re.match(r'(?i)\s*cita\b', text) and a and a <= en_must:
                borrar.append((qid, kid, text))
    print(f'{len(borrar)} criterios `should` duplicados en {len({b[0] for b in borrar})} preguntas:')
    for qid, kid, text in borrar:
        print(f'   q{qid} · componente {kid} · {text}')
    cur.execute("SELECT id, expected_answer FROM bench_questions WHERE set_id = %s AND question = %s", (SET, PRESCRIBE_Q))
    (q_presc, vieja), = cur.fetchall()
    print(f'\nq{q_presc} (prescripción): criterios de ahora:')
    for kid, kind, text in por[q_presc]:
        print(f'   [{kind}] {text}')
    print('   → nuevos:')
    for kind, w, text in PRESCRIBE_COMPONENTES:
        print(f'   [{kind} {w}] {text}')
    if not APLICAR:
        print('\nSIMULACIÓN: no se escribió nada (usa --aplicar)')
        sys.exit()
    cur.execute("CREATE TABLE _bak_20261021_set3_questions AS SELECT * FROM bench_questions WHERE set_id = %s", (SET,))
    cur.execute("CREATE TABLE _bak_20261021_set3_components AS SELECT k.* FROM bench_components k "
                "JOIN bench_questions q ON q.id = k.question_id WHERE q.set_id = %s", (SET,))
    cur.execute("DELETE FROM bench_components WHERE id = ANY(%s)", ([kid for _, kid, _ in borrar],))
    cur.execute("DELETE FROM bench_components WHERE question_id = %s", (q_presc,))
    for pos, (kind, w, text) in enumerate(PRESCRIBE_COMPONENTES):
        cur.execute("INSERT INTO bench_components (question_id, position, text, kind, weight) VALUES (%s,%s,%s,%s,%s)",
                    (q_presc, pos, text, kind, w))
    cur.execute("UPDATE bench_questions SET expected_answer = %s, updated_at = now() WHERE id = %s", (PRESCRIBE_ESPERADA, q_presc))
    cur.execute("UPDATE bench_questions SET updated_at = now() WHERE id = ANY(%s)", (list({b[0] for b in borrar}),))
    cur.execute("UPDATE bench_sets SET updated_at = now() WHERE id = %s", (SET,))
    c.commit()
    print('\nAPLICADO · respaldo en _bak_20261021_set3_questions / _bak_20261021_set3_components')
