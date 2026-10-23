"""Genera apps/rewrite_lab/componentes_casos.json: los casos iniciales de la página 🧩 Componentes. Se cargan en la base
(comp_casos) solo si el componente no tiene casos; después se editan en la página.

- filtro: las frases de las pruebas que ya existían (compuerta_2026-10-19/probar_deteccion.py y probar_clasificacion.py,
  matriz_4sets_2026-10-21/probar_doctrina.py) + el caso de «Trabajo en Morelos…» (set 14, q376). Revisados (vienen de
  pruebas ya usadas).
- descomponer: las preguntas de los sets 3 y 14, etiquetadas en automático: compara si nombra 2+ códigos o estados
  (codes_in, la regex del routing, + «ámbito/fuero federal» = CPF; entidades = esos códigos) o si dice «diferencia entre / distingue / vs» (conceptos,
  sin entidades fijas). NO revisadas.
- por_delito: borrador de relatos con sus conductas (raíces de palabras). NO revisados: Karen debe corregirlos.
- hyde: las preguntas de los sets 3, 13 y 14; los estados permitidos son los que la pregunta nombra.
Corre en el servidor (lee los sets de la base):  python generar_casos.py > componentes_casos.json"""
import json, re, sys
from pathlib import Path
RAIZ = Path('/home/tlacua/apps/RAG_lab')
sys.path[:0] = [str(RAIZ / 'apps' / 'rewrite_lab'), str(RAIZ), str(RAIZ / '06_evaluation' / 'compuerta_2026-10-19'),
                str(RAIZ / '06_evaluation' / 'matriz_4sets_2026-10-21')]
from dotenv import load_dotenv; load_dotenv(RAIZ / 'apps' / 'rewrite_lab' / '.env')
from shared.db import connect
from shared.code_routes import codes_in
import probar_deteccion as det, probar_clasificacion as cla
import jurisdiction_gate as jgate
from componentes import contar_preguntas
NUEVAS_TEORICAS = [l for l in (RAIZ / '06_evaluation' / 'matriz_4sets_2026-10-21' / 'probar_doctrina.py').read_text().split('NUEVAS = [')[1].split(']\n')[0].splitlines() if l.strip().startswith('(')]

with connect() as c, c.cursor() as cur:
    cur.execute("SELECT set_id, id, question, notes FROM bench_questions WHERE set_id IN (3, 13, 14) ORDER BY set_id, id")
    preguntas = cur.fetchall()
    cur.execute("SELECT DISTINCT question_id FROM bench_components WHERE kind = 'must' AND text ~* '^\\s*cita'")
    con_cita = {r[0] for r in cur.fetchall()}

filtro = []
for sid, qid, q, notas in preguntas:
    if sid == 14:
        filtro.append({'entrada': q, 'esperado': {'estados': sorted(det.esperado_set14(notas or ''))},
                       'fuente': f'set 14 · q{qid}', 'revisado': True})
filtro += [{'entrada': f, 'esperado': {'estados': sorted(e)}, 'fuente': 'probar_deteccion (extra)', 'revisado': True}
           for f, e in det.EXTRA]
filtro += [{'entrada': f, 'esperado': {'hechos': sorted(h), 'otros': sorted(o)}, 'fuente': 'probar_deteccion (rol)',
            'revisado': True} for f, h, o in det.ROLES]
filtro.append({'entrada': 'Trabajo en Morelos y mi jefa me presiona para salir con ella a cambio de un aumento. ¿Es delito?',
               'esperado': {'hechos': ['Morelos'], 'otros': []}, 'fuente': 'set 14 · q376',
               'nota': 'El acoso ocurre en el trabajo: Morelos es el lugar de los hechos (falla vista el 22-oct).',
               'revisado': True})
filtro += [{'entrada': f, 'esperado': {'depende': d, 'federal': x}, 'fuente': f'probar_clasificacion ({t})', 'revisado': True}
           for f, d, x, t in cla.CASOS + [(f, d, x, t + ', nueva') for f, d, x, t in cla.NUEVAS]]
for linea in NUEVAS_TEORICAS:
    frase, teorica = eval(linea.strip().rstrip(','))   # noqa: S307 — tuplas literales de nuestro propio archivo
    filtro.append({'entrada': frase, 'esperado': {'teorica': teorica}, 'fuente': 'probar_doctrina', 'revisado': True})

CONCEPTOS = re.compile(r'(?i)diferencias?\s+(hay\s+)?entre|distingue|\bvs\.?\b|frente\s+a')
descomponer = []
for sid, qid, q, _ in preguntas:
    if sid not in (3, 14):
        continue
    ents = {h['label'] for h in codes_in(q)}
    if jgate.FEDERAL_RE.search(q):   # «ámbito federal», «fuero federal»: codes_in solo reconoce el nombre del código
        ents.add('CPF')
    ents = sorted(ents)
    if len(ents) >= 2:
        esp, nota = {'compara': True, 'entidades': ents}, 'automático: nombra 2+ códigos o estados'
    elif CONCEPTOS.search(q):
        esp, nota = {'compara': True}, 'automático: compara conceptos (revisar)'
    else:
        esp, nota = {'compara': False}, 'automático: no nombra 2+ códigos ni compara conceptos'
    descomponer.append({'entrada': q, 'esperado': {**esp, 'preguntas': contar_preguntas(q), 'nombrados': ents},
                        'fuente': f'set {sid} · q{qid}', 'nota': nota + ' · preguntas: conteo automático', 'revisado': False})

BORRADOR = 'Borrador de Claude: Karen debe revisar las conductas y sus raíces.'
por_delito = [{'entrada': r, 'esperado': {'conductas': cs}, 'fuente': 'borrador', 'nota': BORRADOR, 'revisado': False} for r, cs in [
    ('Me drogaron en un bar y me robaron la cartera.', [['sustancia', 'droga', 'narcot', 'administr'], ['rob', 'apoder']]),
    ('Mi expareja me amenazó por WhatsApp y publicó fotos íntimas mías.', [['amenaz'], ['intim', 'sexual', 'imagen', 'difusi']]),
    ('Un policía me detuvo sin razón y me pidió dinero para soltarme.', [['detenc', 'privaci', 'arbitrari'], ['dinero', 'cohecho', 'extorsi', 'soborno']]),
    ('Mi jefe me acosa y me amenazó con despedirme si no salgo con él.', [['acoso', 'hostig'], ['amenaz']]),
    ('Un conductor ebrio chocó mi coche, lesionó a mi hijo y huyó.', [['dano', 'propiedad', 'choque'], ['lesion'], ['abandon', 'huy', 'fuga', 'omisi', 'auxilio']]),
    ('Entraron a mi casa rompiendo la puerta y se llevaron la televisión.', [['allan', 'domicilio', 'morada'], ['rob', 'apoder']]),
    ('Me vendieron un terreno que no era suyo y falsificaron la escritura.', [['fraude', 'engan'], ['falsific']]),
    ('Un hombre me tocó sin permiso en el camión y me grabó con su celular.', [['abuso', 'sexual', 'toc'], ['grab', 'video', 'intimid', 'imagen']]),
    ('Me robaron el celular en el metro.', [['rob', 'apoder']]),
    ('Me llamaron diciendo que tenían a mi hijo y me pidieron un depósito.', [['extorsi', 'secuestro']]),
    ('Mi tío golpea a mi tía en su casa desde hace años.', [['violencia familiar', 'golpe', 'lesion']]),
]]

hyde = []
for sid, qid, q, _ in preguntas:
    permitidos = sorted({h['label'] for h in codes_in(q)})
    hyde.append({'entrada': q, 'esperado': {'permitidos': permitidos}, 'fuente': f'set {sid} · q{qid}', 'revisado': True})

# Las versiones del prompt de descomponer se prueban con las mismas preguntas; cada evaluador aplica su regla.
versiones = {f'desc_{v}': descomponer for v in ('solo_lugar', 'solo_pregunta', 'lugar_y_pregunta', 'libre', 'libre_corto', 'libre_max2')}
# Pruebas de recall: preguntas de los sets 3, 13 y 14 con artículos esperados (algún «Cita el art.» en sus criterios).
recall = [{'entrada': q, 'esperado': {'set': sid}, 'fuente': f'set {sid} · q{qid}', 'revisado': True}
          for sid, qid, q, _ in preguntas if qid in con_cita]
print(json.dumps({'filtro': filtro, 'descomponer': descomponer, 'por_delito': por_delito, 'hyde': hyde, **versiones,
                  'division_recall': recall, 'hyde_recall': recall, 'rerank_recall': recall}, ensure_ascii=False, indent=1))
