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
             max_tokens: int = 80, timeout: int = 60) -> str:
        body = json.dumps({
            'model': self.model,
            'messages': [{'role': 'system', 'content': system},
                         {'role': 'user', 'content': user}],
            'temperature': temperature,
            'max_tokens': max_tokens,
            # llama.cpp con modelos Qwen3: apaga el modo "thinking" para respuesta directa.
            'chat_template_kwargs': {'enable_thinking': False},
        }).encode()
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

    def rewrite_legal(self, question: str) -> str:
        """Pregunta coloquial → enunciado jurídico breve (para query rewriting)."""
        return self.chat(REWRITE_SYSTEM, question)
