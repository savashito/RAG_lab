"""Casos de dos mensajes para «Filtro por estado · métodos»: pregunta del benchmark (sets 12, 13 y 14, escritas por
expertos) que NO menciona ningún lugar (si mencionara uno, lo esperado del segundo mensaje cambiaría) ni el ámbito federal → la respuesta REAL de Tlacua en las corridas #211–#242 que pide el lugar (según el set de Gemma,
pide_lugar_etiquetas) → 8 formas de contestar con su resultado correcto. 10 conversaciones distintas (mitad con cada
prompt de respuesta) × 8 respuestas = 80 casos. Sin datos de participantes. Escribe JSON en stdout.
    python generar_casos_dos_mensajes.py > casos.json"""
import sys, os, json, hashlib
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
os.chdir('/home/tlacua/apps/RAG_lab/apps/rewrite_lab')
from dotenv import load_dotenv; load_dotenv('.env')
from shared.db import connect
from shared.object_store import store
from shared.code_routes import codes_in, fold
import jurisdiction_gate as jg

_sin_lugar = {}
def sin_lugar(q: str) -> bool:
    """Ni un código o estado reconocido (codes_in), ni el ámbito federal, ni ningún lugar que encuentre el filtro (con
    Gemma: atrapa ciudades y alcaldías como «Iztapalapa» o «Cuernavaca»)."""
    if q not in _sin_lugar:
        import main
        f = f' {fold(q)} '
        _sin_lugar[q] = (not codes_in(q) and not jg.FEDERAL_RE.search(q) and not any(f' {n} ' in f for n in jg._POR_NOMBRE if len(n) > 3)
                         and not jg.extraer_lugares(q, main.llm)['lugares'])
    return _sin_lugar[q]

RESPUESTAS = [   # (lo que contesta la persona, lo esperado, tipo de caso)
    ('Querétaro', {'hechos': ['Querétaro'], 'otros': []}, 'contesta solo el estado'),
    ('en Quere', {'hechos': ['Querétaro'], 'otros': []}, 'contesta el estado abreviado'),
    ('en Toluca', {'hechos': ['Estado de México'], 'otros': []}, 'contesta una ciudad'),
    ('aquí en la colonia Roma', {'hechos': ['Ciudad de México'], 'otros': []}, 'contesta una colonia'),
    ('fue en Querétaro pero vivo en la CDMX', {'hechos': ['Querétaro'], 'otros': ['Ciudad de México']}, 'lugar de los hechos y donde vive'),
    ('vivo en Morelos', {'hechos': [], 'otros': ['Morelos']}, 'solo dice dónde vive'),
    ('no sé, fue por internet', {'hechos': [], 'otros': []}, 'no sabe dónde fue'),
    ('en Jalisco', {'hechos': ['Jalisco'], 'otros': []}, 'un estado que no está en el corpus'),
]
PROMPT = {**{r: 'penal-original-v1' for r in range(211, 227)}, **{r: 'ultimo-promt' for r in range(227, 235)},
          **{r: 'ultimo-promt-v2' for r in range(235, 243)}}
with connect() as c, c.cursor() as cur:
    cur.execute('SELECT respuesta_md5 FROM pide_lugar_etiquetas WHERE gemma_pide')
    pide = {r[0] for r in cur.fetchall()}
    cur.execute("SELECT id, set_id, artifact_key FROM bench_runs WHERE id BETWEEN 211 AND 242 AND artifact_key IS NOT NULL ORDER BY id")
    corridas = cur.fetchall()
# OJO: las llamadas a Gemma (sin_lugar) van FUERA de la conexión. Con una transacción abierta durante minutos, la app se
# quedó esperando un bloqueo en bench_runs y prod dejó de responder (25-oct, ~17:50).
candidatas = {'penal-original-v1': [], 'ultimo-promt-v2': []}
vistas = set()
for rid, sid, k in corridas:
    p = PROMPT.get(rid)
    if p not in candidatas or sid not in (12, 13, 14):
        continue
    for x in store.get_json(k.removeprefix(store.prefix))['results']:
        a, q = x.get('answer') or '', x.get('question') or ''
        # La misma pregunta puede entrar con cada prompt: la respuesta de Tlacua es distinta.
        if a and (q, p) not in vistas and hashlib.md5(a.encode()).hexdigest() in pide and sin_lugar(q):
            candidatas[p].append((q, a, f'set {sid} · corrida #{rid} · {p}')); vistas.add((q, p))
conversaciones = []
for i in range(5):   # alterna los dos prompts
    for p in ('penal-original-v1', 'ultimo-promt-v2'):
        if i < len(candidatas[p]):
            conversaciones.append(candidatas[p][i])
casos = [{'entrada': resp, 'esperado': {'conversacion': [{'role': 'user', 'content': q}, {'role': 'assistant', 'content': a}], **esp,
                                         'tipo_caso': f'dos mensajes (respuesta real de Tlacua) · {tipo}'},
          'fuente': fuente, 'nota': 'Generado 25-oct: la respuesta de Tlacua es real y pide el lugar (set de Gemma).', 'revisado': False}
         for q, a, fuente in conversaciones for resp, esp, tipo in RESPUESTAS]
print(json.dumps(casos, ensure_ascii=False, indent=1))
print(f'{len(conversaciones)} conversaciones · {len(casos)} casos', file=sys.stderr)
