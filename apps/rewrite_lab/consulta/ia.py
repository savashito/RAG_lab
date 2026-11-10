"""
Tareas del LLM para la máquina de estados de la consulta. Cada una tiene su prompt fijo y responde JSON; el programa
valida la respuesta y la descarta si no sirve. El LLM nunca decide el estado.

  · clasificar_caso: el mensaje de la persona → tipos de caso de la lista cerrada del catálogo (o dudoso entre 2–3).
  · extraer_hechos: los mensajes de la persona → valores de los datos del expediente que se le piden.
    El lugar de los hechos lo extrae jurisdiction_gate.extraer_lugares (el mismo filtro de las rondas 1 y 2).

Cada respuesta trae `_llamada` = {tarea, md5 del prompt, respuesta cruda, segundos} para el registro del mensaje.
"""
from __future__ import annotations

import hashlib
import json
import re
import time

import jurisdiction_gate as jgate

CLASIFICAR_SYSTEM = """Clasificas consultas legales de personas en México. Recibes lo que escribió la persona y una
lista cerrada de TIPOS DE CASO (id: nombre — descripción). Elige el tipo o los tipos de caso que describen lo que le
pasó. Puede haber más de uno (por ejemplo, fotos íntimas y amenazas).

Responde SOLO un JSON:
{"tipos": ["id", ...], "dudoso": false, "opciones": []}

- "tipos": los ids que corresponden, solo de la lista. Si no corresponde ninguno, ["otro"].
- Si no puedes decidir entre 2 o 3 tipos, deja "tipos" vacío, pon "dudoso": true y en "opciones" esos 2 o 3 ids.
- No inventes ids. No expliques nada fuera del JSON."""

EXTRAER_SYSTEM = """Extraes datos de una consulta legal en México. Recibes los mensajes de la persona, la última
pregunta que le hizo el asistente y una lista de DATOS con su id, su tipo y qué significa.

Responde SOLO un JSON con los ids de la lista como llaves:
{"id_del_dato": valor, ...}

Reglas:
- Solo datos que la persona dijo o que se deducen sin duda de lo que dijo. Si no lo dijo, pon null. No adivines.
- Si la persona dice que no sabe, pon "no_sabe".
- Si su mensaje es una respuesta corta («sí», «no», «24»), es la respuesta a la ÚLTIMA PREGUNTA del asistente.
- Tipos: si_no → "si" o "no"; numero → un número; opcion → exactamente una de las opciones listadas.
- No expliques nada fuera del JSON."""


def _md5(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()


def _json(raw: str) -> dict | None:
    m = re.search(r'\{.*\}', raw or '', re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except ValueError:
        return None
    return d if isinstance(d, dict) else None


class ConsultaIA:
    def __init__(self, llm):
        """`llm`: shared.llm_client.LlamaClient (o uno falso en las pruebas): .chat(system, user, ...) → str."""
        self.llm = llm

    def _llamar(self, tarea: str, system: str, user: str, max_tokens: int) -> tuple[str, dict]:
        t0 = time.time()
        try:
            raw = self.llm.chat(system, user, temperature=0.0, max_tokens=max_tokens, timeout=90)
        except Exception as e:   # el LLM caído no tumba la conversación: se pregunta lo que falte
            raw = f'__error__: {e}'
        return raw, {'tarea': tarea, 'prompt_md5': _md5(system), 'raw': raw, 'segundos': round(time.time() - t0, 2)}

    def clasificar_caso(self, texto: str, catalogo: dict) -> dict:
        tipos = catalogo.get('tipos_caso', [])
        lista = '\n'.join(f'- {t["id"]}: {t["titulo"]} — {t.get("descripcion") or t["titulo"]}'
                          for t in tipos if t.get('estado') != 'descartada')
        raw, llamada = self._llamar('clasificar_caso', CLASIFICAR_SYSTEM,
                                    f'TIPOS DE CASO:\n{lista}\n- otro: ninguno de los anteriores\n\nCONSULTA:\n{texto}', 120)
        d = _json(raw) or {}
        ids = {t['id'] for t in tipos} | {'otro'}
        elegidos = [t for t in d.get('tipos') or [] if t in ids]
        opciones = [t for t in d.get('opciones') or [] if t in ids and t != 'otro'][:3]
        if not elegidos and len(opciones) < 2:
            elegidos = opciones or []   # «dudoso» con una sola opción = esa opción
            opciones = []
        return {'tipos': list(dict.fromkeys(elegidos)), 'opciones': opciones if not elegidos else [], '_llamada': llamada}

    def extraer_hechos(self, texto: str, ultima_pregunta: str, datos: list[dict]) -> dict:
        out: dict = {}
        llamadas = []
        if any(d['id'] == 'lugar_hechos' for d in datos):
            lug = jgate.extraer_lugares(texto, self.llm)
            llamadas.append({'tarea': 'extraer_lugares', 'prompt_md5': _md5(jgate.EXTRAER_SYSTEM), 'raw': lug.get('raw', ''),
                             'fuente': lug.get('fuente')})
            hechos = list(dict.fromkeys(x['estado'] for x in lug.get('lugares', [])
                                        if x.get('estado') and x.get('rol', 'hechos') == 'hechos'))
            if len(hechos) == 1:          # dos estados distintos: no se decide; se vuelve a preguntar
                out['lugar_hechos'] = hechos[0]
        resto = [d for d in datos if d['id'] != 'lugar_hechos']
        if resto:
            lista = '\n'.join(f'- {d["id"]} ({d.get("tipo", "si_no")}'
                              + (f': {", ".join(d["opciones"])}' if d.get('opciones') else '')
                              + f'): {d.get("para_que") or d.get("pregunta")}' for d in resto)
            raw, llamada = self._llamar('extraer_hechos', EXTRAER_SYSTEM,
                                        f'DATOS:\n{lista}\n\nÚLTIMA PREGUNTA DEL ASISTENTE:\n{ultima_pregunta or "(ninguna)"}'
                                        f'\n\nMENSAJES DE LA PERSONA:\n{texto}', 300)
            llamadas.append(llamada)
            d = _json(raw) or {}
            ids = {x['id'] for x in resto}
            out.update({k: v for k, v in d.items() if k in ids and v is not None})
        return {'datos': out, '_llamada': {'tarea': 'extraer_hechos', 'partes': llamadas}}
