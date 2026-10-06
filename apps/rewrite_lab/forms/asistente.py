"""Asistente de trámites: la MÁQUINA DE ESTADOS que guía a una persona a llenar un formulario.

    ┌────────┐ elige o describe ┌────────┐  «es mi caso»  ┌────────────┐ todo contestado ┌──────────┐ confirma ┌───────────┐
    │ INICIO │ ───────────────▶ │ TRIAJE │ ─────────────▶ │ ENTREVISTA │ ──────────────▶ │ REVISIÓN │ ───────▶ │ DOCUMENTO │
    └────────┘ ◀─ «no aplica» ─ └────────┘                └────────────┘ ◀── corregir ── └──────────┘ ◀─ editar ─ └───────────┘
        ▲                                                   │  ▲ duda legal: responde con el RAG
        └──────────────────────── reiniciar (desde cualquier estado) ───┘  y vuelve a la misma pregunta

Reglas de diseño:
  · El ESTADO lo controla este código, nunca el LLM. Las transiciones válidas están en TRANSICIONES.
  · El LLM (forms/ia.py) solo hace tres cosas: elegir el formulario a partir de lo que cuenta la
    persona, extraer datos de sus respuestas libres y detectar si lo que escribió es una duda.
  · El documento lo arma forms/plantilla.py con la plantilla revisada (sin LLM).
  · No se guarda nada en el servidor: el borrador (estado + respuestas) viaja del navegador al
    servidor en cada turno y regresa actualizado. Por eso todo aquí es puro y fácil de probar.

El «borrador» es un dict:
    {'estado': 'ENTREVISTA', 'formulario': 'divorcio_unilateral_cdmx',
     'respuestas': {...}, 'omitidos': [...],          # campos opcionales que la persona saltó
     'corrigiendo': None | 'campo',                     # en REVISIÓN se pidió corregir este campo
     'incompleto': None | {'campo', 'valor', 'faltan'}, # respuesta a la que le faltan partes (p. ej. la colonia)
     'contexto': 'lo que contó en el chat', 'transicion': {...}}   # la última, para depurar
"""
from __future__ import annotations

import datetime as dt
import re
import unicodedata

from forms.plantilla import condition, fill

# ── Estados y transiciones ───────────────────────────────────────────────────────
INICIO, TRIAJE, ENTREVISTA, REVISION, DOCUMENTO = 'INICIO', 'TRIAJE', 'ENTREVISTA', 'REVISION', 'DOCUMENTO'
ESTADOS = (INICIO, TRIAJE, ENTREVISTA, REVISION, DOCUMENTO)

TRANSICIONES = {
    # (estado actual, evento)        → estado siguiente
    (INICIO, 'formulario_elegido'):    TRIAJE,
    (TRIAJE, 'aplica'):                ENTREVISTA,
    (TRIAJE, 'no_aplica'):             INICIO,
    (ENTREVISTA, 'completo'):          REVISION,
    (REVISION, 'corregir'):            ENTREVISTA,
    (REVISION, 'confirmar'):           DOCUMENTO,
    (DOCUMENTO, 'editar'):             REVISION,
}
# «reiniciar» vale desde cualquier estado y regresa a INICIO.


def transicion(borrador: dict, evento: str, motivo: str = '') -> dict:
    """Aplica una transición válida (o lanza ValueError) y la anota para el panel de depuración."""
    actual = borrador.get('estado', INICIO)
    nuevo = INICIO if evento == 'reiniciar' else TRANSICIONES.get((actual, evento))
    if nuevo is None:
        raise ValueError(f'transición no válida: {actual} --{evento}-->')
    return {**borrador, 'estado': nuevo,
            'transicion': {'de': actual, 'evento': evento, 'a': nuevo, 'motivo': motivo}}


def nuevo_borrador(contexto: str = '') -> dict:
    return {'estado': INICIO, 'formulario': None, 'respuestas': {}, 'omitidos': [], 'corrigiendo': None,
            'incompleto': None, 'contexto': contexto, 'transicion': None}


# ── Campos: cuáles aplican, cuál sigue, cómo se normaliza una respuesta ──────────
def campos_aplicables(spec: dict, respuestas: dict) -> list[dict]:
    """Campos que se deben preguntar con las respuestas actuales (su `si:` se cumple)."""
    return [c for c in spec.get('campos', [])
            if not c.get('automatico') and (not c.get('si') or condition(c['si'], respuestas))]


def pendientes(spec: dict, borrador: dict) -> list[dict]:
    """Campos aplicables sin respuesta (ni omitidos a propósito), en el orden del formulario."""
    r, omit = borrador['respuestas'], set(borrador.get('omitidos', []))
    return [c for c in campos_aplicables(spec, r) if c['id'] not in omit and _vacio(r.get(c['id']))]


def siguiente_campo(spec: dict, borrador: dict) -> dict | None:
    if borrador.get('corrigiendo'):
        return next((c for c in spec['campos'] if c['id'] == borrador['corrigiendo']), None)
    p = pendientes(spec, borrador)
    return p[0] if p else None


def _vacio(v) -> bool:
    return v is None or v == '' or v == []


def _fold(s: str) -> str:
    s = unicodedata.normalize('NFD', str(s)).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9 ]+', ' ', s).strip()


SI = {'si', 'sí', 'claro', 'correcto', 'afirmativo', 'asi es', 'si es', 'por supuesto', 'yes'}
NO = {'no', 'ninguno', 'ninguna', 'nada', 'negativo', 'no tengo', 'no tenemos', 'nop'}
OMITIR = {'omitir', 'saltar', 'paso', 'no se', 'no lo se', 'prefiero no decir', 'n a', 'ninguno', 'no tengo',
          'no', 'no me acuerdo', 'no recuerdo', 'no lo tengo', 'no lo recuerdo', 'no aplica', 'ninguna', 'nada'}
_PREGUNTA = re.compile(r'^(que|como|cual|cuales|cuando|donde|quien|por que|puedo|debo|tengo que|es necesario|necesito)\b')


def respuesta_rapida(campo: dict, texto: str):
    """Respuesta que se entiende sin LLM (sí/no, número de opción). None si hay que preguntarle a Gemma."""
    t = _fold(texto)
    if campo.get('tipo') == 'si_no':
        if t in {_fold(x) for x in SI}:
            return True
        if t in {_fold(x) for x in NO}:
            return False
    if campo.get('tipo') == 'opcion':
        opciones = campo.get('opciones') or {}
        for clave, etiqueta in opciones.items():
            if t in (_fold(clave), _fold(etiqueta)):
                return clave
    return None


def quiere_omitir(campo: dict, texto: str) -> bool:
    """En un campo opcional, «no», «no me acuerdo», «no lo tengo»… significan saltarlo."""
    return campo.get('obligatorio') is False and _fold(texto) in {_fold(x) for x in OMITIR}


# ── ¿Está completa la respuesta? ─────────────────────────────────────────────────
# Dos fuentes: `formato:` (lo revisa el código: teléfono, correo, fecha con año) y `requiere:`
# (partes que debe traer, p. ej. un domicilio: calle y número, colonia, alcaldía, código postal;
# lo revisa Gemma en la misma llamada en la que extrae el dato y lo devuelve en «_faltan»).
_MESES_RX = r'(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)'


def faltan_formato(campo: dict, valor) -> list[str]:
    v = str(valor or '')
    fmt = campo.get('formato')
    if fmt == 'telefono':
        digitos = re.sub(r'\D', '', v)
        if digitos.startswith('52') and len(digitos) == 12:
            digitos = digitos[2:]
        return [] if len(digitos) == 10 else ['el número completo a 10 dígitos']
    if fmt == 'correo':
        return [] if re.search(r'^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$', v.strip()) else ['un correo válido (por ejemplo nombre@dominio.com)']
    if fmt == 'fecha_completa':
        f = _fold(v)
        tiene_anio = bool(re.search(r'\b(19|20)\d\d\b', f))
        tiene_dia_mes = bool(re.search(r'\b\d{1,2}\b.*' + _MESES_RX, f)) or bool(re.search(r'\b\d{1,2}[/-]\d{1,2}\b', v))
        return ([] if tiene_dia_mes else ['el día y el mes']) + ([] if tiene_anio else ['el año'])
    return []


# Partes conocidas que se detectan con reglas (instantáneo y confiable); las demás de `requiere`
# las revisa Gemma con una llamada corta (ia.revisar_partes).
_ALCALDIAS = ('alvaro obregon', 'azcapotzalco', 'benito juarez', 'coyoacan', 'cuajimalpa', 'cuauhtemoc',
              'gustavo a madero', 'iztacalco', 'iztapalapa', 'magdalena contreras', 'miguel hidalgo', 'milpa alta',
              'tlahuac', 'tlalpan', 'venustiano carranza', 'xochimilco')
# Cada detector devuelve True (está), False (seguro que falta) o None (no se sabe → lo revisa Gemma):
# una colonia o un municipio pueden escribirse sin la palabra «colonia» o «municipio» («Narvarte»).
DETECTORES = {
    'calle y numero': lambda f: bool(re.search(r'\d', f)) and bool(re.search(r'[a-z]{3,}', f)),
    'colonia': lambda f: True if re.search(r'\b(col|colonia|fracc|fraccionamiento|barrio|pueblo|unidad|uh|residencial|conjunto)\b', f) else None,
    'codigo postal': lambda f: bool(re.search(r'\b\d{5}\b', f)),
    'alcaldia o municipio': lambda f: True if (re.search(r'\b(alcaldia|delegacion|municipio|mpio)\b', f)
                                               or any(a in f for a in _ALCALDIAS)) else None,
}


def faltan_partes(campo: dict, valor, ia=None) -> tuple[list[str], dict | None]:
    """(partes que faltan, debug de Gemma). Formato y partes conocidas: código; el resto: Gemma."""
    faltan, f = faltan_formato(campo, valor), _fold(valor)
    desconocidas = []
    for parte in campo.get('requiere') or []:
        detector = DETECTORES.get(_fold(parte))
        hay = detector(f) if detector else None
        if hay is False:
            faltan.append(parte)
        elif hay is None:
            desconocidas.append(parte)
    debug = None
    if desconocidas and ia is not None:
        faltan_ia, debug = ia.revisar_partes(campo, str(valor), desconocidas)
        norm = {_fold(p): p for p in desconocidas}
        faltan += [norm[_fold(x)] for x in faltan_ia if _fold(x) in norm]
    orden = {p: i for i, p in enumerate(campo.get('requiere') or [])}   # en el orden en que se declararon
    return sorted(dict.fromkeys(faltan), key=lambda p: orden.get(p, -1)), debug


def _lista(xs: list[str]) -> str:
    return xs[0] if len(xs) == 1 else ', '.join(xs[:-1]) + ' y ' + xs[-1]


def parece_pregunta(texto: str) -> bool:
    """«¿…?» o empieza con qué/cómo/cuál/puedo… y es más que una frase corta («quién sabe» no cuenta)."""
    return '?' in texto or (bool(_PREGUNTA.match(_fold(texto))) and len(texto.split()) >= 4)


def normalizar(campo: dict, valor):
    """Ajusta el valor al tipo del campo. (valor, error) — error es texto para la persona."""
    tipo = campo.get('tipo')
    if tipo == 'si_no':
        if isinstance(valor, bool):
            return valor, None
        rapida = respuesta_rapida(campo, str(valor))
        return (rapida, None) if rapida is not None else (None, 'Responde «sí» o «no», por favor.')
    if tipo == 'opcion':
        opciones = campo.get('opciones') or {}
        if valor in opciones:
            return valor, None
        rapida = respuesta_rapida(campo, str(valor))
        return (rapida, None) if rapida else (None, 'Elige una de las opciones: ' + ' / '.join(opciones.values()) + '.')
    if tipo == 'lista':
        if isinstance(valor, dict):
            valor = [valor]
        if not isinstance(valor, list) or not all(isinstance(x, dict) for x in valor):
            return None, None
        subs = campo.get('subcampos') or []
        limpio = [{s['id']: str(x.get(s['id'], '') or '').strip() for s in subs} for x in valor]
        return [x for x in limpio if any(x.values())], None
    texto = str(valor).strip().rstrip('.').strip() if valor is not None else ''   # el punto lo pone la plantilla
    return (texto or None), None


# ── Un turno de la conversación ──────────────────────────────────────────────────
def turno(borrador: dict | None, catalogo: dict, ia, *, mensaje: str = '', evento: str = '',
          campo: str = '') -> tuple[dict, dict]:
    """Avanza la conversación un paso. Devuelve (borrador nuevo, respuesta para la UI).

    `catalogo`: {id: spec} de los formularios disponibles para esta persona.
    `ia`: objeto con elegir_formulario(catalogo, texto), extraer(spec, campos, texto, actual, conocidas) y
          responder_duda(spec, texto) — ver forms/ia.py. Los tests usan uno falso.
    `evento`: botón que presionó la persona (elegir:<id>, aplica, no_aplica, confirmar,
              corregir + campo, editar, reiniciar, omitir).
    """
    b = dict(borrador or nuevo_borrador())
    b.setdefault('respuestas', {}), b.setdefault('omitidos', [])
    b['transicion'] = None
    debug = {'llm': None}

    if evento == 'reiniciar':
        b = transicion(nuevo_borrador(b.get('contexto', '')), 'reiniciar', 'la persona reinició')
        return b, _vista(b, catalogo, debug, 'Empecemos de nuevo. ¿Qué trámite necesitas?')

    estado = b.get('estado', INICIO)
    spec = catalogo.get(b.get('formulario')) if b.get('formulario') else None

    # ── INICIO: elegir el formulario (botón o descripción libre) ─────────────────
    if estado == INICIO:
        elegido = evento.split(':', 1)[1] if evento.startswith('elegir:') else None
        if not elegido and mensaje.strip():
            elegido, debug['llm'] = ia.elegir_formulario(catalogo, mensaje)
            b['contexto'] = (b.get('contexto', '') + '\n' + mensaje).strip()
        if elegido in catalogo:
            b['formulario'] = elegido
            b = transicion(b, 'formulario_elegido', 'botón' if evento else 'Gemma lo eligió por lo que contaste')
            return b, _vista(b, catalogo, debug)
        return b, _vista(b, catalogo, debug, 'No encontré un formulario para eso. Elige uno de la lista o cuéntame con otras palabras qué necesitas.'
                         if mensaje.strip() else None)

    if spec is None:   # el formulario dejó de estar disponible
        b = transicion(nuevo_borrador(), 'reiniciar', 'el formulario ya no está disponible')
        return b, _vista(b, catalogo, debug, 'Ese formulario ya no está disponible. Elige otro.')

    # ── TRIAJE: confirmar que el formulario aplica a su caso ─────────────────────
    if estado == TRIAJE:
        if evento == 'no_aplica':
            b = transicion({**b, 'formulario': None}, 'no_aplica', 'la persona dijo que no es su caso')
            return b, _vista(b, catalogo, debug, 'De acuerdo. Revisa las alternativas de arriba o elige otro trámite.')
        if evento == 'aplica' or _fold(mensaje) in {_fold(x) for x in SI}:
            b = transicion(b, 'aplica', 'la persona confirmó que es su caso')
            if b.get('contexto'):   # aprovecha lo que ya contó en el chat
                datos, debug['llm'] = ia.extraer(spec, campos_aplicables(spec, b['respuestas']), b['contexto'], None, b['respuestas'])
                b = _guardar(spec, b, datos)
            return b, _vista(b, catalogo, debug)
        return b, _vista(b, catalogo, debug)

    # ── ENTREVISTA: preguntar campo por campo ────────────────────────────────────
    if estado == ENTREVISTA:
        actual = siguiente_campo(spec, b)
        aviso = None
        inc = b.get('incompleto') if actual and (b.get('incompleto') or {}).get('campo') == actual['id'] else None
        if inc and evento == 'aceptar_incompleto':
            # La persona prefiere dejar la respuesta como está.
            b = {**b, 'respuestas': {**b['respuestas'], actual['id']: inc['valor']}, 'incompleto': None}
        elif actual and evento == 'omitir' and actual.get('obligatorio') is False:
            b['omitidos'] = sorted(set(b['omitidos']) | {actual['id']})
            b['incompleto'] = None
        elif actual and mensaje.strip():
            if inc and actual.get('requiere'):   # completa las partes que faltaban: se junta con lo anterior
                mensaje = f"{inc['valor']}, {mensaje.strip()}"
            # (con `formato` —teléfono, correo, fecha— la nueva respuesta reemplaza a la anterior)
            if quiere_omitir(actual, mensaje):
                b['omitidos'] = sorted(set(b['omitidos']) | {actual['id']})
            else:
                rapida = respuesta_rapida(actual, mensaje)
                if rapida is not None:
                    datos = {actual['id']: rapida}
                else:
                    pend = [actual] + [c for c in pendientes(spec, b) if c['id'] != actual['id']]
                    datos, debug['llm'] = ia.extraer(spec, pend, mensaje, actual['id'], b['respuestas'])
                sin_datos = not any(k for k in datos if not k.startswith('_'))
                if sin_datos and (datos.get('_es_duda') or parece_pregunta(mensaje)):
                    respuesta, debug['rag'] = ia.responder_duda(spec, mensaje)
                    return b, _vista(b, catalogo, debug, respuesta, repetir=True)
                antes = dict(b['respuestas'])
                ya = {c['id'] for c in pendientes(spec, b)}
                b = _guardar(spec, b, datos)
                # La respuesta pudo abrir campos nuevos («sí, tenemos dos: Ana… y Luis…»): se le
                # vuelve a pedir a Gemma que busque en el MISMO mensaje los datos de esos campos.
                nuevos = [c for c in pendientes(spec, b) if c['id'] not in ya]
                if nuevos and len(mensaje.split()) > 3:
                    extra, debug['llm_campos_nuevos'] = ia.extraer(spec, nuevos, mensaje, None, b['respuestas'])
                    b = _guardar(spec, b, extra)
                if b['respuestas'] == antes and actual['id'] not in datos:
                    # Gemma no encontró el dato: se toma el texto tal cual si el campo es de texto.
                    if actual.get('tipo') in ('texto', 'texto_largo', 'fecha'):
                        b = _guardar(spec, b, {actual['id']: mensaje.strip()})
                    else:
                        aviso = normalizar(actual, mensaje)[1] or 'No entendí tu respuesta.'
                # ¿Le faltan partes a la respuesta de ESTE campo? Se aparta (no cuenta como contestada)
                # y se pide completarla o dejarla así.
                valor = b['respuestas'].get(actual['id'])
                faltan = []
                if not _vacio(valor):
                    faltan, debug['llm_partes'] = faltan_partes(actual, valor, ia)
                if faltan:
                    r = dict(b['respuestas']); r.pop(actual['id'])
                    b = {**b, 'respuestas': r, 'incompleto': {'campo': actual['id'], 'valor': valor, 'faltan': faltan}}
                    aviso = f'Anoté: «{valor}». Me falta {_lista(faltan)}. ¿Me lo das, o prefieres dejarlo así?'
                else:
                    b['incompleto'] = None
            if b.get('corrigiendo') and not _vacio(b['respuestas'].get(b['corrigiendo'])):
                b['corrigiendo'] = None
                if not pendientes(spec, b):
                    b = transicion(b, 'completo', 'se corrigió el dato')
                    return b, _vista(b, catalogo, debug)
        if not pendientes(spec, b) and not b.get('corrigiendo'):
            b = transicion(b, 'completo', 'ya no faltan datos')
        return b, _vista(b, catalogo, debug, aviso)

    # ── REVISIÓN: la persona revisa todos los datos ──────────────────────────────
    if estado == REVISION:
        if evento == 'confirmar':
            b = transicion(b, 'confirmar', 'la persona confirmó sus datos')
            return b, _vista(b, catalogo, debug)
        if evento == 'corregir' and campo:
            b = transicion({**b, 'corrigiendo': campo}, 'corregir', f'corregir «{campo}»')
            return b, _vista(b, catalogo, debug)
        if mensaje.strip():   # «cambia la fecha a …»
            datos, debug['llm'] = ia.extraer(spec, campos_aplicables(spec, b['respuestas']), mensaje, None, b['respuestas'])
            b = _guardar(spec, b, datos)
            if pendientes(spec, b):   # el cambio abrió preguntas nuevas (p. ej. ahora sí hay hijos)
                b = transicion(b, 'corregir', 'el cambio requiere datos nuevos')
        return b, _vista(b, catalogo, debug)

    # ── DOCUMENTO: el escrito generado ───────────────────────────────────────────
    if estado == DOCUMENTO and evento == 'editar':
        b = transicion(b, 'editar', 'la persona quiere cambiar algo')
    return b, _vista(b, catalogo, debug)


def _guardar(spec: dict, b: dict, datos: dict) -> dict:
    """Guarda los datos extraídos que correspondan a campos del formulario (ya normalizados)."""
    por_id = {c['id']: c for c in spec.get('campos', [])}
    r = dict(b['respuestas'])
    for k, v in (datos or {}).items():
        if k in por_id and not por_id[k].get('automatico') and not _vacio(v):
            limpio, _ = normalizar(por_id[k], v)
            if not _vacio(limpio):
                r[k] = limpio
    return {**b, 'respuestas': r}


# ── Lo que ve la persona en cada estado ──────────────────────────────────────────
def _vista(b: dict, catalogo: dict, debug: dict, mensaje: str | None = None, repetir: bool = False) -> dict:
    spec = catalogo.get(b.get('formulario')) if b.get('formulario') else None
    v = {'estado': b['estado'], 'mensaje': mensaje, 'botones': [], 'documento': None}
    if b['estado'] == INICIO:
        v['pregunta'] = '¿Qué trámite necesitas? Elige uno o cuéntame tu situación.'
        v['botones'] = [{'evento': f'elegir:{fid}', 'texto': s['titulo'],
                         'borrador': s.get('estado') != 'publicado'} for fid, s in catalogo.items()]
    elif b['estado'] == TRIAJE:
        v['triaje'] = {k: spec.get(k) for k in ('titulo', 'descripcion', 'cuando_aplica', 'cuando_no_aplica', 'avisos')}
        v['pregunta'] = '¿Es tu caso?'
        v['botones'] = [{'evento': 'aplica', 'texto': 'Sí, es mi caso'}, {'evento': 'no_aplica', 'texto': 'No es mi caso'}]
    elif b['estado'] == ENTREVISTA:
        c = siguiente_campo(spec, b)
        if c:
            v['pregunta'] = c['pregunta']
            v['campo'] = {k: c.get(k) for k in ('id', 'tipo', 'ayuda', 'opciones', 'subcampos', 'obligatorio')}
            if c.get('tipo') == 'si_no':
                v['botones'] = [{'enviar': 'Sí', 'texto': 'Sí'}, {'enviar': 'No', 'texto': 'No'}]
            elif c.get('tipo') == 'opcion':
                v['botones'] = [{'enviar': clave, 'texto': t} for clave, t in (c.get('opciones') or {}).items()]
            if (b.get('incompleto') or {}).get('campo') == c['id']:
                v['botones'].append({'evento': 'aceptar_incompleto', 'texto': 'Dejarlo así'})
            if c.get('obligatorio') is False:
                v['botones'].append({'evento': 'omitir', 'texto': 'Saltar'})
        v['repetir'] = repetir
    elif b['estado'] == REVISION:
        v['pregunta'] = 'Revisa tus datos. Puedes corregir cualquiera o escribirme qué cambiar.'
        v['resumen'] = [{'id': c['id'], 'pregunta': c['pregunta'], 'valor': b['respuestas'].get(c['id']),
                         'omitido': c['id'] in b.get('omitidos', [])}
                        for c in campos_aplicables(spec, b['respuestas'])]
        v['botones'] = [{'evento': 'confirmar', 'texto': 'Todo está bien, generar el escrito'}]
    elif b['estado'] == DOCUMENTO:
        datos = {**b['respuestas'], 'fecha_firma': fecha_larga(dt.date.today())}
        doc, faltan = fill(spec['_plantilla'], datos)
        v['documento'], v['faltan'] = doc, faltan
        v['pregunta'] = 'Este es tu borrador. Revísalo con tu abogada o abogado (o con la Defensoría Pública) antes de presentarlo.'
        v['botones'] = [{'evento': 'editar', 'texto': 'Cambiar datos'}]
    v['debug'] = {
        'estado': b['estado'], 'transicion': b.get('transicion'), 'formulario': b.get('formulario'),
        'formulario_estado': spec.get('estado') if spec else None,
        'siguiente_campo': (siguiente_campo(spec, b) or {}).get('id') if spec and b['estado'] == ENTREVISTA else None,
        'pendientes': [c['id'] for c in pendientes(spec, b)] if spec else [],
        'omitidos': b.get('omitidos', []), 'respuestas': b.get('respuestas', {}),
        'corrigiendo': b.get('corrigiendo'), 'incompleto': b.get('incompleto'), **debug}
    return v


MESES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre',
         'octubre', 'noviembre', 'diciembre')


def fecha_larga(d: dt.date) -> str:
    return f'{d.day} de {MESES[d.month - 1]} de {d.year}'
