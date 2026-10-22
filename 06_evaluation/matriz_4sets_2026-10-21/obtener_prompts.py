"""Reúne el texto de cada prompt que usa el sistema, para mostrarlo en el informe (prompts_sistema.json):
- del código (tal como está en el commit desplegado): filtro por estado, HyDE por omisión, descomponer, descomponer por
  delito y juez; y las instrucciones que el filtro le deja al LLM que responde, generadas con la función real
  `jurisdiction_gate.decidir` sobre un ejemplo de cada caso;
- de la base: el prompt de HyDE y la instrucción de embeddings del tema penal, los prompts de respuesta etiquetados y los
  criterios del juez de los sets 3, 12, 13 y 14.
Se corre en el servidor:  python obtener_prompts.py > prompts_sistema.json"""
import ast, json, sys
from pathlib import Path
RAIZ = Path('/home/tlacua/apps/RAG_lab')
sys.path[:0] = [str(RAIZ / 'apps' / 'rewrite_lab'), str(RAIZ)]
from dotenv import load_dotenv; load_dotenv(RAIZ / 'apps' / 'rewrite_lab' / '.env')
from shared.db import connect
import jurisdiction_gate as jg


def constante(archivo, nombre):
    """Valor de una constante de texto de un módulo, sin importarlo (main.py y bench.py arrancan servicios)."""
    for nodo in ast.parse((RAIZ / archivo).read_text()).body:
        if isinstance(nodo, ast.Assign) and any(getattr(t, 'id', None) == nombre for t in nodo.targets):
            return ast.literal_eval(nodo.value)
    raise KeyError(nombre)


class LLMFijo:   # devuelve la extracción indicada, para generar la instrucción real de cada caso
    def __init__(self, out): self.out = out
    def chat(self, *a, **k): return json.dumps(self.out)


DISP = {'Ciudad de México': 'cdmx', 'Estado de México': 'edomex', 'Querétaro': 'queretaro', 'Morelos': 'morelos'}
NO_EST = ['federal', 'nacional', 'general']
lugar = lambda t, e, rol='hechos': {'texto': t, 'estado': e, 'rol': rol}  # noqa: E731
CASOS = [
    ('Me robaron el celular en Toluca', {'lugares': [lugar('Toluca', 'Estado de México')], 'tipo': 'delito_comun'}),
    ('Me robaron la cartera en Pachuca', {'lugares': [lugar('Pachuca', 'Hidalgo')], 'tipo': 'delito_comun'}),
    ('Vivo en Toluca y me robaron el celular', {'lugares': [lugar('Toluca', 'Estado de México', 'otro')], 'tipo': 'delito_comun'}),
    ('Me robaron el celular', {'lugares': [], 'tipo': 'delito_comun'}),
    ('¿Cuánto tiempo me pueden tener detenido?', {'lugares': [], 'tipo': 'procedimiento'}),
    ('En el Código Penal Federal, ¿cómo se tipifica el estupro?', {'lugares': [], 'tipo': 'delito_comun'}),
    ('¿Qué es la tentativa punible?', {'lugares': [], 'tipo': 'otro', 'teorica': True}),
]
out = {
    'filtro': jg.EXTRAER_SYSTEM,
    'hyde_omision': constante('shared/llm_client.py', 'HYDE_SYSTEM'),
    'descomponer': constante('shared/llm_client.py', 'DECOMPOSE_SYSTEM'),
    'por_delito': constante('apps/rewrite_lab/main.py', 'CONDUCTAS_SYSTEM'),
    'juez': constante('apps/rewrite_lab/bench.py', 'JUDGE_SYSTEM'),
    'notas_filtro': [{'pregunta': p, 'buscador_ve': g['jurisdictions'], 'nota': g['nota']}
                     for p, ex in CASOS for g in [jg.decidir(p, LLMFijo(ex), DISP, NO_EST)]],
}
with connect() as c, c.cursor() as cur:
    cur.execute("SELECT hyde_prompt, instruct FROM rewrite_lab_topics WHERE topic = 'derecho_penal_mexicano'")
    out['hyde_penal'], out['instruct_penal'] = cur.fetchone()
    cur.execute("SELECT tag, text FROM bench_prompt_tags WHERE tag IN "
                "('penal-original-v1', 'tlacua-v1-penas', 'tlacua-secuencia-y-penas')")
    out['respuesta'] = dict(cur.fetchall())
    cur.execute("SELECT id, name, coalesce(judge_notes, '') FROM bench_sets WHERE id IN (3, 12, 13, 14) ORDER BY id")
    out['criterios_juez'] = [{'set': i, 'nombre': n, 'criterios': j} for i, n, j in cur.fetchall()]
print(json.dumps(out, ensure_ascii=False, indent=1))
