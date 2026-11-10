"""
Tareas del LLM para la máquina de estados de la consulta. Cada una tiene su prompt fijo y responde JSON; el programa
valida la respuesta y la descarta si no sirve. El LLM nunca decide el estado.

  · clasificar_caso: la conversación y los tipos de caso del expediente → qué tipos agregar o quitar (o dudoso
    entre 2–3 si todavía no hay ninguno). Solo la lista cerrada del catálogo.
  · extraer_expediente: los mensajes de la persona → valores de los datos del expediente que se le piden.
    El lugar de los hechos lo extrae jurisdiction_gate.extraer_lugares (el mismo filtro de las rondas 1 y 2).

Cada respuesta trae `_llamada` = {tarea, md5 del prompt, respuesta cruda, segundos} para el registro del mensaje.
"""
from __future__ import annotations

import hashlib
import json
import re
import time

import jurisdiction_gate as jgate

CLASIFICAR_CASO_SYSTEM = """Clasificas consultas legales de personas en México. Recibes una lista cerrada de TIPOS DE
CASO (id: nombre, y a veces — descripción), los TIPOS DE CASO ACTUALES del expediente (puede estar vacía) y la
CONVERSACIÓN entre la persona y el asistente. Dices qué tipos de caso hay que agregar o quitar para que los actuales
describan lo que le pasó a la persona. Puede haber más de uno (por ejemplo, fotos íntimas y amenazas).

Responde SOLO un JSON:
{"agregar": [], "quitar": [], "por_que": "", "dudoso": false, "opciones": []}

- "agregar": ids de la lista que describen algo que contó la persona y que no están en los actuales.
- "quitar": ids de los actuales que ya no corresponden. Quita solo si la persona corrigió o contradijo lo que había
  dicho. Que no lo repita en su último mensaje no es motivo para quitar.
- "por_que": en una frase, qué dijo la persona que justifica agregar o quitar. Vacío si no cambias nada.
- Si nada de lo que dijo cambia el tipo de caso, deja "agregar" y "quitar" vacíos.
- Si los actuales están vacíos y no corresponde ningún tipo, "agregar": ["otro"].
- Si los actuales están vacíos y no puedes decidir entre 2 o 3 tipos, deja "agregar" vacío, pon "dudoso": true y en
  "opciones" esos 2 o 3 ids.
- No inventes ids. No expliques nada fuera del JSON."""

EXTRAER_EXPEDIENTE_SYSTEM = """Extraes datos de una consulta legal en México. Recibes los mensajes de la persona, la última
pregunta que le hizo el asistente y una lista de DATOS con su id, su tipo y la pregunta que lo obtiene.

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

    def clasificar_caso(self, conversacion: str, actuales: list[str], catalogo: dict) -> dict:
        """La conversación (persona y asistente) y los tipos de caso del expediente → qué agregar y qué quitar.
        Descarta ids que no están en la lista, agregar lo que ya está y quitar lo que no está."""
        tipos = catalogo.get('tipos_caso', [])
        # La descripción solo se manda si dice algo más que el nombre (mientras Karen no la escriba, es una copia).
        lista = '\n'.join(f'- {t["id"]}: {t["titulo"]}'
                          + (f' — {t["descripcion"]}' if t.get('descripcion') and t['descripcion'] != t['titulo'] else '')
                          for t in tipos if t.get('estado') != 'descartada')
        raw, llamada = self._llamar('clasificar_caso', CLASIFICAR_CASO_SYSTEM,
                                    f'TIPOS DE CASO:\n{lista}\n- otro: ninguno de los anteriores\n\n'
                                    f'TIPOS DE CASO ACTUALES: {", ".join(actuales) or "(ninguno)"}\n\n'
                                    f'CONVERSACIÓN:\n{conversacion}', 200)
        d = _json(raw) or {}
        ids = {t['id'] for t in tipos} | {'otro'}
        agregar = [t for t in d.get('agregar') or [] if t in ids and t not in actuales]
        quitar = [t for t in d.get('quitar') or [] if t in actuales]
        opciones = [t for t in d.get('opciones') or [] if t in ids and t != 'otro'][:3]
        if actuales or agregar:
            opciones = []                 # la duda solo cuenta si todavía no hay tipo de caso
        elif len(opciones) < 2:
            agregar, opciones = opciones, []   # «dudoso» con una sola opción = esa opción
        return {'agregar': list(dict.fromkeys(agregar)), 'quitar': list(dict.fromkeys(quitar)),
                'por_que': str(d.get('por_que') or '').strip(), 'opciones': opciones, '_llamada': llamada}

    def extraer_expediente(self, texto: str, ultima_pregunta: str, datos: list[dict]) -> dict:
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
                              + f'): {d.get("pregunta") or d.get("para_que")}' for d in resto)   # la pregunta dice qué buscar
            raw, llamada = self._llamar('extraer_expediente', EXTRAER_EXPEDIENTE_SYSTEM,
                                        f'DATOS:\n{lista}\n\nÚLTIMA PREGUNTA DEL ASISTENTE:\n{ultima_pregunta or "(ninguna)"}'
                                        f'\n\nMENSAJES DE LA PERSONA:\n{texto}', 300)
            llamadas.append(llamada)
            d = _json(raw) or {}
            ids = {x['id'] for x in resto}
            out.update({k: v for k, v in d.items() if k in ids and v is not None})
        return {'datos': out, '_llamada': {'tarea': 'extraer_expediente', 'partes': llamadas}}
