"""Lo que SÍ hace el LLM en el asistente de trámites (ver forms/asistente.py). Tres tareas acotadas,
todas con salida JSON que el código valida; ninguna decide el estado ni redacta el documento:

  · elegir_formulario — de lo que cuenta la persona, ¿cuál formulario del catálogo aplica?
  · extraer           — de una respuesta libre, sacar los valores de los campos pendientes
                        («nos casamos en julio del 99 y tenemos dos hijos» → fecha + hijos)
  · responder_duda    — si lo que escribió es una pregunta jurídica, contestarla con el RAG

Cada método devuelve (resultado, debug) para que el panel de depuración muestre lo que hizo Gemma.
"""
from __future__ import annotations

import json
import re


def _json(raw: str) -> dict:
    m = re.search(r'\{.*\}', raw or '', re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        return {}


class IA:
    def __init__(self, llm, ask=None):
        self.llm, self.ask = llm, ask

    def _chat(self, system: str, user: str, max_tokens: int = 500) -> str:
        return self.llm.chat(system, user, temperature=0.0, max_tokens=max_tokens, timeout=90,
                             extra={'response_format': {'type': 'json_object'}})

    def elegir_formulario(self, catalogo: dict, texto: str) -> tuple[str | None, dict]:
        opciones = '\n'.join(f'- {fid}: {s["titulo"]}. {s.get("descripcion", "")} '
                             f'Aplica cuando: {"; ".join(s.get("cuando_aplica") or [])}'
                             for fid, s in catalogo.items())
        system = ('Eres un asistente que identifica qué trámite legal necesita una persona. Recibes una '
                  'lista de formularios y lo que la persona cuenta. Devuelve SOLO un JSON '
                  '{"formulario": "<id>"} con el id del formulario que corresponde, o {"formulario": null} '
                  'si ninguno corresponde claramente. No inventes ids.')
        raw = self._chat(system, f'FORMULARIOS:\n{opciones}\n\nLO QUE CUENTA LA PERSONA:\n{texto}', 60)
        fid = _json(raw).get('formulario')
        return (fid if fid in catalogo else None), {'tarea': 'elegir_formulario', 'raw': raw}

    def extraer(self, spec: dict, campos: list[dict], texto: str, actual: str | None,
                conocidas: dict | None = None) -> tuple[dict, dict]:
        def describe(c):
            d = f'- {c["id"]} ({c.get("tipo")}): {c.get("pregunta", "")}'
            if c.get('tipo') == 'opcion':
                d += ' Valores posibles: ' + ', '.join(f'"{k}" = {v}' for k, v in (c.get('opciones') or {}).items())
            if c.get('tipo') == 'lista':
                d += ' Lista de objetos con: ' + ', '.join(s['id'] for s in c.get('subcampos') or [])
            if c.get('requiere'):
                d += ' Debe incluir: ' + '; '.join(c['requiere']) + '.'
            return d
        system = (
            (spec.get('instrucciones_entrevista') or '') + '\n\n'
            'Tarea: extrae de la RESPUESTA los valores de los CAMPOS que la persona haya dado. Devuelve SOLO un '
            'JSON con el id de cada campo encontrado y su valor: si_no → true/false; opcion → el valor exacto de '
            'la lista; lista → arreglo de objetos; fecha y texto → el texto tal como lo dijo. No incluyas campos '
            'que la persona no haya mencionado y no inventes datos. Si la RESPUESTA es una pregunta o duda en vez '
            'de un dato, agrega "_es_duda": true.\n'

            'Los valores de texto van tal como deben aparecer en un escrito formal: en tercera persona y sin '
            'muletillas; sustituye «yo», «conmigo» por el nombre de quien solicita y «él», «ella» por el nombre del '
            'cónyuge, usando los DATOS YA CONOCIDOS. Si para un domicilio dice «en mi casa», «el mismo» o «donde '
            'vivo», usa el domicilio que ya dio (DATOS YA CONOCIDOS); si no hay ninguno, devuelve lo que dijo. Cada '
            'valor de texto es una sola cadena, nunca un objeto. Fechas sin artículo («30 de noviembre de 2026»; si '
            'no dijo el año, no lo inventes). Nunca agregues información que la persona no dio.')
        ya = {k: v for k, v in (conocidas or {}).items() if isinstance(v, str) and len(v) < 120}
        user = (('DATOS YA CONOCIDOS:\n' + '\n'.join(f'- {k}: {v}' for k, v in ya.items()) + '\n\n' if ya else '') +
                'CAMPOS:\n' + '\n'.join(describe(c) for c in campos) +
                (f'\n\nLa pregunta que se le acaba de hacer corresponde al campo: {actual}' if actual else '') +
                f'\n\nRESPUESTA:\n{texto}')
        raw = self._chat(system, user, 700)
        datos = _json(raw)
        validos = {c['id'] for c in campos} | {'_es_duda'}
        return {k: v for k, v in datos.items() if k in validos}, {'tarea': 'extraer', 'raw': raw}

    def revisar_partes(self, campo: dict, valor: str, partes: list[str]) -> tuple[list[str], dict]:
        """¿Qué partes de la lista NO aparecen en el valor? Llamada corta y dedicada (un modelo chico
        lo hace mejor así que mezclado con la extracción)."""
        system = ('Revisas si un dato está completo. Devuelve SOLO un JSON {"faltan": [...]} con los elementos de '
                  'la lista que NO aparecen en el dato. Si todos aparecen, {"faltan": []}.')
        raw = self._chat(system, f'DATO ({campo.get("id")}): {valor}\nLISTA: {json.dumps(partes, ensure_ascii=False)}', 80)
        faltan = _json(raw).get('faltan') or []
        return [x for x in faltan if isinstance(x, str)], {'tarea': 'revisar_partes', 'raw': raw}

    def responder_duda(self, spec: dict, texto: str) -> tuple[str, dict]:
        if not self.ask:
            return 'Por ahora no puedo responder dudas aquí; consúltalo con tu abogada o abogado.', {}
        system = ('Eres un asistente jurídico. Responde la duda en 3 a 5 líneas, en lenguaje sencillo y SOLO con '
                  'base en el CONTEXTO, citando el artículo y la ley. Si el contexto no alcanza, dilo. Recuerda '
                  'que la persona está llenando: ' + spec.get('titulo', ''))
        r = self.ask(texto, 'híbrido', 6, system, spec.get('tema'), None, True, False, False, False, route=True)
        fuentes = [f"{c.get('doc_label') or c.get('source')} — {c.get('title')}" for c in (r.get('chunks') or [])[:4]]
        return r.get('answer', ''), {'tarea': 'responder_duda', 'fuentes': fuentes}


class Medidor:
    """Envuelve a IA para UN turno y anota cada llamada (tarea y segundos). El panel de depuración
    y el registro del servidor muestran cuántas llamadas hizo el turno y cuánto tardó cada una."""
    TAREAS = ('elegir_formulario', 'extraer', 'revisar_partes', 'responder_duda')

    def __init__(self, ia):
        self._ia, self.llamadas = ia, []

    def __getattr__(self, nombre):
        fn = getattr(self._ia, nombre)
        if nombre not in self.TAREAS:
            return fn
        def medido(*a, **kw):
            import time
            t0 = time.time()
            try:
                return fn(*a, **kw)
            finally:
                self.llamadas.append({'tarea': nombre, 'segundos': round(time.time() - t0, 2),
                                      # responder_duda = búsqueda RAG (con HyDE) + respuesta: 2 llamadas al LLM
                                      'llm': 2 if nombre == 'responder_duda' else 1})
        return medido
