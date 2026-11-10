"""
Máquina de estados de la consulta (ronda 3): no se orienta hasta tener los datos del expediente de los que depende
qué ley aplica.

    ┌───────────────────┐  ya están todos los datos   ┌─────────────┐
    │ LLENAR_EXPEDIENTE │ ──────────────────────────▶ │ ORIENTACION │ ◀─┐ pregunta de seguimiento
    └───────────────────┘ ◀── falta un dato nuevo ─── └─────────────┘ ──┘
       ▲            │  falta un dato: pregunta (texto del catálogo)
       └────────────┘  tipo de caso dudoso: botones para elegir

Reglas de diseño (06_evaluation/estudio_ronda3_2026-11-10/diseno_maquina_estados.md):
  · El ESTADO lo decide este código, nunca el LLM. Las transiciones válidas están en TRANSICIONES.
  · El LLM (consulta/ia.py) solo clasifica el tipo de caso y extrae datos de lo que escribe la persona.
  · `turno()` es pura: no toca la base ni el buscador. Devuelve qué hacer; quien la llama (el estudio) ejecuta la
    orientación con el buscador y el LLM, y guarda el registro.
  · REDACTAR_DOCUMENTO no está aquí: no entra en la ronda 3 (trabajo_futuro.md, C6).

Evento (lo que hizo la persona):
    {'tipo': 'mensaje', 'texto': '...', 'historial': [{'role': 'user'|'assistant', 'content': '...'}, ...]}
    {'tipo': 'elegir_tipo', 'valor': 'imagenes_intimas'}      # botón de «¿a qué se parece más?»
    {'tipo': 'reiniciar'}

Salida (qué le toca hacer al asistente):
    {'tipo': 'pregunta', 'dato': 'lugar_hechos', 'texto': '¿En qué estado pasó?'}
    {'tipo': 'elegir_tipo', 'texto': '...', 'opciones': [{'id', 'titulo'}]}
    {'tipo': 'orientar', 'reglas': [...], 'inciertas': [...], 'codigos': ['queretaro'], 'articulos': {...},
     'fuera_de_corpus': bool, 'sin_reglas': bool}
"""
from __future__ import annotations

from consulta import expediente as E

LLENAR_EXPEDIENTE, ORIENTACION = 'LLENAR_EXPEDIENTE', 'ORIENTACION'
ESTADOS = (LLENAR_EXPEDIENTE, ORIENTACION)

TRANSICIONES = {
    # (estado actual, evento interno)          → estado siguiente
    (LLENAR_EXPEDIENTE, 'tipo_dudoso'):          LLENAR_EXPEDIENTE,
    (LLENAR_EXPEDIENTE, 'falta_dato'):           LLENAR_EXPEDIENTE,
    (LLENAR_EXPEDIENTE, 'expediente_completo'):  ORIENTACION,
    (ORIENTACION, 'seguimiento'):                ORIENTACION,
    (ORIENTACION, 'falta_dato'):                 LLENAR_EXPEDIENTE,
}
# «reiniciar» vale desde cualquier estado: expediente nuevo y LLENAR_EXPEDIENTE.

MAX_PREGUNTAS = 2    # un dato no obligatorio que se preguntó 2 veces sin respuesta cuenta como «no sé»
OTRO = 'otro'


def _siguiente(estado: str, evento: str) -> str:
    nuevo = TRANSICIONES.get((estado, evento))
    if nuevo is None:
        raise ValueError(f'transición no válida: {estado} --{evento}-->')
    return nuevo


def _texto_usuario(evento: dict) -> str:
    """Todos los mensajes de la persona, del primero al actual (el LLM extrae de toda la conversación)."""
    previos = [m['content'] for m in evento.get('historial', []) if m.get('role') == 'user']
    return '\n'.join(previos + [evento.get('texto', '')])


def _ultima_pregunta(evento: dict) -> str:
    """Lo último que preguntó el asistente: para entender respuestas cortas («sí», «24»)."""
    for m in reversed(evento.get('historial', [])):
        if m.get('role') == 'assistant':
            return m.get('content', '')
    return ''


def turno(estado: str | None, expediente: dict | None, evento: dict, catalogo: dict, ia,
          solo_confirmadas: bool = False) -> tuple[str, dict, dict, dict]:
    """Un mensaje (o botón) de la persona → (estado nuevo, expediente nuevo, salida, registro del mensaje)."""
    estado = estado or LLENAR_EXPEDIENTE
    exp = expediente or E.nuevo()
    registro = {'estado_antes': estado, 'evento': evento.get('tipo'), 'llamadas': [], 'cambios': []}

    if evento.get('tipo') == 'reiniciar':
        estado, exp = LLENAR_EXPEDIENTE, E.nuevo()
    elif evento.get('tipo') == 'elegir_tipo':
        ids = {t['id'] for t in catalogo.get('tipos_caso', [])} | {OTRO}
        if evento.get('valor') in ids:
            exp = {**exp, 'tipos_caso': [evento['valor']]}
            registro['cambios'].append('tipos_caso')
    elif evento.get('tipo') == 'mensaje':
        texto, pregunta = _texto_usuario(evento), _ultima_pregunta(evento)
        dudoso = None
        if not exp.get('tipos_caso'):
            c = ia.clasificar_caso(texto, catalogo)
            registro['llamadas'].append(c.get('_llamada'))
            if c.get('tipos'):
                exp = {**exp, 'tipos_caso': c['tipos']}
                registro['cambios'].append('tipos_caso')
            elif c.get('opciones'):
                dudoso = c['opciones']
        # Se extrae aunque el tipo de caso sea dudoso, para no perder lo que la persona ya contó.
        buscar = E.datos_necesarios(exp, catalogo) if exp.get('tipos_caso') else list(catalogo.get('datos', []))
        x = ia.extraer_hechos(texto, pregunta, [d for d in buscar if d.get('preguntar', True)])
        registro['llamadas'].append(x.get('_llamada'))
        exp, cambios = E.combinar(exp, x.get('datos', {}), catalogo)
        registro['cambios'] += cambios
        if dudoso:
            titulos = {t['id']: t['titulo'] for t in catalogo.get('tipos_caso', [])}
            salida = {'tipo': 'elegir_tipo', 'texto': '¿Lo que te pasó se parece más a alguna de estas opciones?',
                      'opciones': [{'id': o, 'titulo': titulos.get(o, o)} for o in dudoso] +
                                  [{'id': OTRO, 'titulo': 'Ninguna de estas'}]}
            return _cerrar(registro['estado_antes'], _siguiente(estado, 'tipo_dudoso'), exp, salida, registro)

    # ¿Falta algún dato? Un dato no obligatorio que ya se preguntó MAX_PREGUNTAS veces sin respuesta cuenta como «no sé»:
    # la persona no queda atrapada. El lugar de los hechos (obligatorio) se sigue preguntando.
    while True:
        faltan = E.datos_faltantes(exp, catalogo)
        agotado = next((d for d in faltan if not d.get('obligatorio')
                        and exp.get('preguntas', {}).get(d['id'], 0) >= MAX_PREGUNTAS), None)
        if not agotado:
            break
        exp = {**exp, 'no_sabe': exp.get('no_sabe', []) + [agotado['id']]}
    registro['faltan'] = [d['id'] for d in faltan]

    if faltan:
        d = faltan[0]
        exp = {**exp, 'preguntas': {**exp.get('preguntas', {}), d['id']: exp.get('preguntas', {}).get(d['id'], 0) + 1}}
        salida = {'tipo': 'pregunta', 'dato': d['id'], 'texto': d['pregunta']}
        return _cerrar(registro['estado_antes'], _siguiente(estado, 'falta_dato'), exp, salida, registro)

    reglas = E.reglas_aplicables(exp, catalogo, solo_confirmadas=solo_confirmadas)
    codigos = E.codigos_del_caso(exp, reglas)
    salida = {'tipo': 'orientar', 'reglas': [r['id'] for r in reglas],
              'inciertas': [r['id'] for r in reglas if r['incierta']],
              'codigos': codigos, 'articulos': E.articulos_del_caso(exp, reglas),
              'fuera_de_corpus': exp['datos'].get('lugar_hechos') not in E.CODIGO_DE_ESTADO and 'federal' not in codigos,
              'sin_reglas': not reglas}
    evento_interno = 'expediente_completo' if estado == LLENAR_EXPEDIENTE else 'seguimiento'
    return _cerrar(registro['estado_antes'], _siguiente(estado, evento_interno), exp, salida, registro)


def _cerrar(antes: str, despues: str, exp: dict, salida: dict, registro: dict):
    registro.update({'estado_antes': antes, 'estado_despues': despues, 'salida': salida.get('tipo')})
    registro['llamadas'] = [x for x in registro['llamadas'] if x]
    return despues, exp, salida, registro
