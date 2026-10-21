"""Filtro por estado, cambio del 2026-10-21 (campo «teorica» y CPF nombrado en la pregunta): ¿qué tipo da el LLM real a
cada pregunta de los sets 3, 13 y 14, y a frases nuevas? Lo que importa: que ninguna pregunta con un caso concreto
(set 13, set 14) quede como teórica, porque entonces el filtro dejaría ver todos los códigos estatales.
Se corre en el servidor:  python probar_doctrina.py [ruta del jurisdiction_gate.py a probar]"""
import collections, json, os, sys
from pathlib import Path
AQUI = Path(__file__).resolve().parent
sys.path[:0] = ['/home/tlacua/apps/RAG_lab', sys.argv[1] if len(sys.argv) > 1 else str(AQUI.parents[1] / 'apps' / 'rewrite_lab')]
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect  # noqa: E402
from shared.llm_client import LlamaClient  # noqa: E402
import jurisdiction_gate as jg  # noqa: E402
print('filtro:', jg.__file__)

NUEVAS = [  # (frase, ¿doctrina?) — escritas después de las instrucciones; ninguna aparece en ellas
    ('¿Qué diferencia hay entre dolo directo y dolo eventual?', True),
    ('¿Qué es la legítima defensa y cuándo excluye el delito?', True),
    ('¿Qué significa que un delito sea de resultado material?', True),
    ('¿Cuál es la diferencia entre autor mediato y coautor?', True),
    ('¿Qué es el error de prohibición?', True),
    ('¿Qué diferencia hay entre robo y abuso de confianza?', True),
    ('Mi primo se defendió de un asaltante y lo hirió, ¿lo pueden meter a la cárcel?', False),
    ('Le prestamos dinero a un amigo y ya no lo quiere devolver, ¿es delito?', False),
    ('Me empujaron en el metro y me fracturé la muñeca.', False),
    ('Mi hermano intentó robar una tienda pero lo detuvieron antes, ¿qué le pasa?', False),
    ('Un vecino dice que me va a matar si no me voy de la colonia.', False),
    ('Un compañero de trabajo me sacó fotos en el baño.', False),
]

with connect() as c, c.cursor() as cur:
    cur.execute("SELECT set_id, id, question FROM bench_questions WHERE set_id IN (3, 13, 14) ORDER BY set_id, id")
    preguntas = cur.fetchall()
llm = LlamaClient(url=os.environ.get('LLM_URL', 'http://127.0.0.1:1237'))
cuenta, salida = collections.Counter(), []
for sid, qid, texto in preguntas:
    ex = jg.extraer_lugares(texto, llm)
    cuenta[(sid, ex['tipo'] + (' teórica' if ex['teorica'] else ''))] += 1
    salida.append({'set': sid, 'id': qid, 'tipo': ex['tipo'], 'teorica': ex['teorica'], 'pide_federal': ex['pide_federal'], 'pregunta': texto})
    if ex['teorica'] or ex['pide_federal']:
        print(f"  set {sid} q{qid} tipo={ex['tipo']} teorica={ex['teorica']} pide_federal={ex['pide_federal']} | {texto[:110]}")
print()
for sid in (3, 13, 14):
    print(f'set {sid}:', {t: n for (s, t), n in sorted(cuenta.items(), key=str) if s == sid})
print()
ok = 0
for frase, doc in NUEVAS:
    ex = jg.extraer_lugares(frase, llm)
    ok += ex['teorica'] == doc
    print(f"{'✓' if ex['teorica'] == doc else '✗'} esperado {'teórica' if doc else 'caso'} · obtuvo {ex['tipo']} teorica={ex['teorica']} | {frase}")
print(f'frases nuevas: {ok}/{len(NUEVAS)}')
(AQUI / 'doctrina_resultados.json').write_text(json.dumps(salida, ensure_ascii=False, indent=1))
