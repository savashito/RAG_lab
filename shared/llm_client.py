"""
shared/llm_client.py — cliente para el LLM local (llama.cpp / llama-server) en rtx5090.

El server expone una API OpenAI-compatible (`/v1/chat/completions`). Aquí sólo se usa
para **query rewriting**: traducir una pregunta coloquial a lenguaje jurídico para
cerrar el semantic gap del retrieval (ver exploracion_datos/exploracion_experimentos).

El puerto (41499) NO está en tunnel.sh por defecto; añade el forward para usarlo:
    ssh -N -L 41499:localhost:41499 rtx5090
"""

from __future__ import annotations

import json
import os
import re
import urllib.request

# Prompt deliberadamente TERSO: las reescrituras largas del LLM (citas
# constitucionales, latinismos) derivan hacia otros chunks. Se pide el vocabulario
# exacto del código, breve. Aun así una sola reescritura es una apuesta: úsala en
# multi-query (original + reescrita), no como reemplazo.
REWRITE_SYSTEM = (
    "Reescribe la pregunta del usuario como un enunciado jurídico BREVE (máximo 18 "
    "palabras) usando los términos exactos del Código Nacional de Procedimientos "
    "Penales mexicano. Sin citas constitucionales, sin números de artículo, sin latín. "
    "Devuelve SOLO el enunciado, una sola línea."
)

# ── HyDE (Hypothetical Document Embeddings) ───────────────────────────────────────
# El problema: la pregunta usa el NOMBRE del delito ("estupro") pero el artículo que lo
# define no repite esa palabra (habla de "cópula con menor de 18 mediante engaño"), así
# que el embedding de la pregunta no lo encuentra. HyDE lo resuelve: el LLM redacta un
# borrador de cómo LUCIRÍA el artículo buscado (con el vocabulario jurídico de la
# conducta), y se embebe ESO en vez de —o además de— la pregunta. El borrador puede
# tener imprecisiones; no importa, solo se usa para acercar el vector a los pasajes
# correctos, nunca se le muestra al usuario ni al LLM final.
HYDE_SYSTEM = (
    "Eres jurista penal mexicano. Redacta en 2 a 4 oraciones cómo luciría el TEXTO del "
    "artículo o pasaje doctrinal que responde la pregunta, con el vocabulario técnico de "
    "la CONDUCTA descrita: verbos rectores, sujeto activo y pasivo, medios comisivos y "
    "circunstancias (edades, consentimiento, engaño, parentesco, etc.). "
    "NO uses el nombre coloquial del delito. NO presumas violencia, fuerza ni coacción a "
    "menos que la pregunta lo diga: describe con precisión los medios que la ley señala "
    "(p. ej. seducción o engaño) sin inventarlos. NO inventes números de artículo ni "
    "entidades. Devuelve solo el pasaje, sin preámbulo."
)


# ── Query decomposition ────────────────────────────────────────────────────────────
# Una pregunta que compara varias cosas ("estupro en Morelos y en la CDMX", "conductismo vs
# psicoanálisis") se busca mal de una sola vez: la entidad con más texto parecido acapara el
# top-k. Se divide en sub-preguntas autónomas, una por entidad/ley/autor/enfoque, y se busca
# cada una por separado. Genérico por diseño: no conoce estados ni temas, solo la estructura.
DECOMPOSE_SYSTEM = (
    "Decide si la PREGUNTA compara o relaciona DOS O MÁS ENTIDADES distintas: leyes, códigos, "
    "estados o países, autores, teorías, escuelas, enfoques o conceptos contrapuestos "
    "(p. ej. «estupro en Morelos y en la CDMX», «condicionamiento clásico vs operante»). "
    "Si es así, escribe una sub-pregunta de búsqueda por entidad: autónoma, con el tema completo "
    "y nombrando solo UNA entidad. "
    "NO dividas por aspectos de una misma entidad (definición, pena, requisitos, procedimiento, "
    "efectos): eso es UNA sola entidad. Si hay una sola entidad, devuelve la pregunta EXACTA, sin "
    "reescribirla. Máximo 4 sub-preguntas. No respondas la pregunta. "
    'Devuelve SOLO un JSON: {"subpreguntas": ["…", "…"]}'
)


def parse_subquestions(raw: str, question: str, max_n: int = 4) -> list[str]:
    """Salida del LLM → lista de sub-preguntas (sin vacías ni repetidas). Ante cualquier
    problema devuelve [question]: la descomposición nunca debe romper la búsqueda."""
    m = re.search(r'\{.*\}', raw or '', re.S)
    try:
        items = json.loads(m.group(0)).get('subpreguntas') if m else None
    except (ValueError, AttributeError):
        items = None
    out = []
    for it in items or []:
        t = str(it or '').strip()
        if t and t.lower() not in {x.lower() for x in out}:
            out.append(t)
    out = out[:max_n]
    # Una sola sub-pregunta = no es comparativa: se busca con la pregunta ORIGINAL, nunca con
    # una paráfrasis del LLM (parafrasear cambia —y a veces empeora— la búsqueda).
    return out if len(out) > 1 else [question]


class LlamaClient:
    def __init__(self, url: str | None = None, model: str | None = None):
        # El puerto y el alias del modelo cambian cada vez que se relanza llama-server,
        # así que el puerto va por LLM_URL y el modelo se auto-detecta de /v1/models.
        self.url = (url or os.environ.get('LLM_URL', 'http://localhost:41499')).rstrip('/')
        self._model = model

    @property
    def model(self) -> str:
        if self._model is None:
            data = json.load(urllib.request.urlopen(self.url + '/v1/models', timeout=10))
            self._model = data['data'][0]['id']
        return self._model

    def chat(self, system: str, user: str, temperature: float = 0.1,
             max_tokens: int = 80, timeout: int = 60, extra: dict | None = None) -> str:
        payload = {
            'model': self.model,
            'messages': [{'role': 'system', 'content': system},
                         {'role': 'user', 'content': user}],
            'temperature': temperature,
            'max_tokens': max_tokens,
            # llama.cpp con modelos Qwen3: apaga el modo "thinking" para respuesta directa.
            'chat_template_kwargs': {'enable_thinking': False},
        }
        if extra:
            payload.update(extra)
        body = json.dumps(payload).encode()
        req = urllib.request.Request(self.url + '/v1/chat/completions', data=body,
                                     headers={'Content-Type': 'application/json'})
        resp = json.load(urllib.request.urlopen(req, timeout=timeout))
        return resp['choices'][0]['message']['content'].strip()

    def chat_messages(self, messages: list[dict], temperature: float = 0.1,
                      max_tokens: int = 80, timeout: int = 60) -> str:
        """Como `chat`, pero recibe la lista completa de mensajes ya armada
        ([{role, content}, ...]) para conversaciones multi-turno."""
        body = json.dumps({
            'model': self.model,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens,
            'chat_template_kwargs': {'enable_thinking': False},
        }).encode()
        req = urllib.request.Request(self.url + '/v1/chat/completions', data=body,
                                     headers={'Content-Type': 'application/json'})
        resp = json.load(urllib.request.urlopen(req, timeout=timeout))
        return resp['choices'][0]['message']['content'].strip()

    def chat_stream(self, messages: list[dict], temperature: float = 0.1,
                    max_tokens: int = 4096, timeout: int = 180):
        """Como `chat_messages` pero en STREAMING: itera los deltas de texto conforme el
        LLM los produce (SSE de llama.cpp con stream=true). Ignora los deltas de
        `reasoning_content` (thinking): solo se emite el `content` visible."""
        body = json.dumps({
            'model': self.model,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens,
            'stream': True,
            'chat_template_kwargs': {'enable_thinking': False},
        }).encode()
        req = urllib.request.Request(self.url + '/v1/chat/completions', data=body,
                                     headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for raw in resp:
                line = raw.decode('utf-8', 'replace').strip()
                if not line.startswith('data:'):
                    continue
                data = line[5:].strip()
                if data == '[DONE]':
                    break
                try:
                    delta = json.loads(data)['choices'][0].get('delta', {})
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
                piece = delta.get('content')
                if piece:
                    yield piece

    def rewrite_legal(self, question: str) -> str:
        """Pregunta coloquial → enunciado jurídico breve (para query rewriting)."""
        return self.chat(REWRITE_SYSTEM, question)

    def decompose(self, question: str) -> list[str]:
        """Pregunta comparativa → sub-preguntas autónomas (una por entidad). [question] si no
        es comparativa o si el LLM falla."""
        try:
            raw = self.chat(DECOMPOSE_SYSTEM, question, temperature=0.0, max_tokens=400, timeout=60,
                            extra={'response_format': {'type': 'json_object'}})
        except Exception:   # noqa: BLE001
            return [question]
        return parse_subquestions(raw, question)

    def hyde_passage(self, question: str, system: str | None = None) -> str:
        """Pregunta → borrador hipotético del pasaje buscado (para HyDE). Da margen de
        tokens porque queremos vocabulario de la conducta, no una frase telegráfica.
        `reasoning_effort=low`: en modelos de razonamiento (GPT-OSS) el 'thinking' se
        come el presupuesto y deja `content` vacío; con esfuerzo bajo redacta directo."""
        return self.chat(system or HYDE_SYSTEM, question, max_tokens=512, timeout=120,
                         extra={'reasoning_effort': 'low'})
