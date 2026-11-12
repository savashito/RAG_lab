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
{"agregar": [], "quitar": [], "por_que": "", "dudoso": false, "opciones": [], "conto_algo": false}

- "agregar": ids de la lista que describen algo que contó la persona y que no están en los actuales.
- "quitar": ids de los actuales que ya no corresponden. Quita solo si la persona corrigió o contradijo lo que había
  dicho. Que no lo repita en su último mensaje no es motivo para quitar.
- "por_que": en una frase, qué dijo la persona que justifica agregar o quitar. Vacío si no cambias nada.
- Si nada de lo que dijo cambia el tipo de caso, deja "agregar" y "quitar" vacíos.
- Si la persona todavía no ha contado ninguna situación (solo saluda, pide ayuda sin decir de qué, o solo da datos
  sueltos como su estado o su edad), deja "agregar" vacío y "dudoso": false: el asistente le pedirá que la cuente.
- Si los actuales están vacíos y la persona contó algo que no corresponde a ningún tipo, "agregar": ["otro"]. Cualquier
  situación que cuente, aunque no sea un delito o no esté en la lista («me encontré una cartera tirada»), va en «otro»:
  la lista vacía es solo para cuando no contó nada.
- Si a la persona la acusan, la denunciaron o la detuvieron, agrega el tipo de proceso penal (si está en la lista) y
  además el tipo de caso del delito del que la acusan (por ejemplo, compartir fotos íntimas → también el de fotos).
- Un mismo caso puede ser de familia y penal a la vez: si una expareja o un familiar se llevó o retiene a un menor, va
  el tipo de custodia y también el de privación de la libertad (sustracción de menores).
- Si llaman o escriben diciendo que tienen a un familiar para pedir dinero, pero no se sabe que de verdad se lo
  llevaron (secuestro virtual), es amenazas o extorsión, no privación de la libertad.
- Si los actuales están vacíos y no puedes decidir entre 2 o 3 tipos, deja "agregar" vacío, pon "dudoso": true y en
  "opciones" esos 2 o 3 ids.
- "conto_algo": true si en toda la conversación la persona dijo algo de su situación, aunque sea muy poco para saber
  el tipo de caso («mandé fotos», «me robaron», «tengo problemas con mi ex»); false si solo saludó, pidió ayuda sin
  decir de qué o solo dio datos sueltos (su estado, su edad).
- No inventes ids. No expliques nada fuera del JSON."""

EXTRAER_EXPEDIENTE_SYSTEM = """Extraes datos de una consulta legal en México. Recibes los mensajes de la persona, la última
pregunta que le hizo el asistente y una lista de DATOS con su id, su tipo y la pregunta que lo obtiene.

Responde SOLO un JSON con los ids de la lista como llaves, más "hechos":
{"id_del_dato": valor, ..., "hechos": ["frase corta", ...]}

Reglas:
- Solo datos que la persona dijo o que se deducen sin duda de lo que dijo. Si no lo dijo, pon null. No adivines.
- Si la persona dice que no sabe, pon "no_sabe".
- Si su mensaje es una respuesta corta («sí», «no», «mucho», «24»), es la respuesta a la ÚLTIMA PREGUNTA del asistente
  y solo a esa: no la uses para ningún otro dato.
- «papel» (a quién le pasó): "victima" si le pasó a la persona que escribe, aunque ella haya mandado las fotos, pagado,
  tomado o aceptado algo antes («mandé unas fotos y ahora me piden dinero» → victima); "persona_senalada" solo si la
  acusan, la denunciaron o la detuvieron a ella; "familiar_o_tercero" si le pasó a otra persona.
- Tipos: si_no → "si" o "no"; numero → un número; opcion → exactamente una de las opciones listadas.
- "hechos": lo que la persona contó en su ÚLTIMO MENSAJE que importa para su caso y que no cabe en ningún dato de la
  lista, en frases cortas en tercera persona («la golpearon muy feo», «le quitaron el celular y la cartera»). No repitas
  lo que ya quedó en un dato, ni saludos o preguntas, ni nada que diga lo mismo que los HECHOS YA ANOTADOS (aunque
  sea con otras palabras). Lista vacía si no hay nada nuevo.
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
        return raw, {'tarea': tarea, 'prompt_md5': _md5(system), 'system': system, 'user': user, 'raw': raw,
                     'segundos': round(time.time() - t0, 2)}

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
                'por_que': str(d.get('por_que') or '').strip(), 'opciones': opciones,
                'conto_algo': d.get('conto_algo') is True, '_llamada': llamada}

    def extraer_expediente(self, texto: str, ultima_pregunta: str, datos: list[dict], ultimo: str | None = None,
                           hechos: list[str] | None = None) -> dict:
        """`texto`: todos los mensajes de la persona; `ultimo`: el actual (al final de `texto`). Para el lugar, la pregunta
        del asistente va justo antes de `ultimo` (v2 del filtro): a «¿En qué estado pasó?» → «en cdmx», CDMX es de los
        hechos y no donde vive la persona."""
        out: dict = {}
        llamadas = []
        residencia = None
        if any(d['id'] == 'lugar_hechos' for d in datos):
            sistema, texto_lugar = jgate.EXTRAER_SYSTEM, texto
            if ultima_pregunta and ultimo and texto.endswith(ultimo):
                sistema = jgate.EXTRAER_SYSTEM_V2
                texto_lugar = f'{texto[:-len(ultimo)]}{jgate.PREGUNTA_PREFIJO}{ultima_pregunta}]\n{ultimo}'
            # El respaldo por regex lee solo a la persona: los ejemplos de la pregunta («Ciudad de México, Querétaro…») no cuentan.
            lug = jgate.extraer_lugares(texto_lugar, self.llm, sistema=sistema, texto_regex=texto)
            llamadas.append({'tarea': 'extraer_lugares', 'prompt_md5': _md5(sistema), 'system': sistema,
                             'user': f'CONSULTA:\n{texto_lugar}', 'raw': lug.get('raw', ''), 'fuente': lug.get('fuente')})
            hechos = list(dict.fromkeys(x['estado'] for x in lug.get('lugares', [])
                                        if x.get('estado') and x.get('rol', 'hechos') == 'hechos'))
            if len(hechos) == 1:          # dos estados distintos: no se decide; se vuelve a preguntar
                out['lugar_hechos'] = hechos[0]
            otros = list(dict.fromkeys(x['estado'] for x in lug.get('lugares', [])
                                       if x.get('estado') and x.get('rol') == 'otro'))
            if len(otros) == 1:           # «soy de CDMX»: donde vive, no donde pasó; la máquina lo ofrece al preguntar
                residencia = otros[0]
        resto = [d for d in datos if d['id'] != 'lugar_hechos']
        hechos = []
        if resto or ultimo:
            lista = '\n'.join(f'- {d["id"]} ({d.get("tipo", "si_no")}'
                              + (f': {", ".join(d["opciones"])}' if d.get('opciones') else '')
                              + f'): {d.get("pregunta") or d.get("para_que")}' for d in resto)   # la pregunta dice qué buscar
            raw, llamada = self._llamar('extraer_expediente', EXTRAER_EXPEDIENTE_SYSTEM,
                                        f'DATOS:\n{lista or "(ninguno)"}\n\nÚLTIMA PREGUNTA DEL ASISTENTE:\n{ultima_pregunta or "(ninguna)"}'
                                        f'\n\nMENSAJES DE LA PERSONA:\n{texto}'
                                        + (f'\n\nÚLTIMO MENSAJE:\n{ultimo}' if ultimo else '')
                                        + ('\n\nHECHOS YA ANOTADOS:\n' + '\n'.join(f'- {h}' for h in hechos) if hechos else ''), 400)
            llamadas.append(llamada)
            d = _json(raw) or {}
            ids = {x['id'] for x in resto}
            out.update({k: v for k, v in d.items() if k in ids and v is not None})
            hechos = [h.strip() for h in d.get('hechos') or [] if isinstance(h, str) and h.strip()][:5]
        return {'datos': out, 'residencia': residencia, 'hechos': hechos,
                '_llamada': {'tarea': 'extraer_expediente', 'partes': llamadas}}
