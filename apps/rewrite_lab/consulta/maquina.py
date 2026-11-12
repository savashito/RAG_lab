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
  · El LLM (consulta/ia.py) solo clasifica el tipo de caso y extrae datos de lo que escribe la persona. Clasifica en
    cada mensaje, con toda la conversación y los tipos de caso actuales, y responde qué agregar o quitar. Este código
    aplica el cambio con sus reglas (_aplicar_clasificacion): `otro` no reemplaza a un tipo real y un quitar que deja
    el expediente sin tipo no se aplica.
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
     'fuera_de_corpus': bool, 'sin_reglas': bool,
     'tipos_quitados': [...]}   # tipos de los que ya se orientó y ya no aplican: la orientación debe decirlo
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
RELATO = '¿En qué te puedo ayudar? Cuéntame tu situación.'   # sin tipo de caso todavía: se pide el relato
SALUDO = 'Hola, soy Tlacua, tu asistente jurídico.'           # antes del RELATO si es el primer mensaje del asistente
RELATO_MAS = 'Cuéntame un poco más de lo que pasó para poder orientarte.'   # si ya contó algo, pero no se reconoce el caso


def _siguiente(estado: str, evento: str) -> str:
    nuevo = TRANSICIONES.get((estado, evento))
    if nuevo is None:
        raise ValueError(f'transición no válida: {estado} --{evento}-->')
    return nuevo


def _texto_usuario(evento: dict) -> str:
    """Todos los mensajes de la persona, del primero al actual (el LLM extrae de toda la conversación)."""
    previos = [m['content'] for m in evento.get('historial', []) if m.get('role') == 'user']
    return '\n'.join(previos + [evento.get('texto', '')])


def _conversacion(evento: dict) -> str:
    """Toda la conversación con su actor, para clasificar: un «sí» suelto se entiende con la pregunta del asistente."""
    lineas = [f'{"Persona" if m.get("role") == "user" else "Asistente"}: {m.get("content", "")}'
              for m in evento.get('historial', [])]
    return '\n'.join(lineas + [f'Persona: {evento.get("texto", "")}'])


def _aplicar_clasificacion(tipos: list[str], c: dict) -> list[str]:
    """Tipos de caso del expediente + respuesta de clasificar_caso → tipos nuevos.
      · Se quita lo que el LLM pide quitar y se agrega lo que pide agregar.
      · `otro` solo entra si no hay ningún tipo real; un tipo real que entra saca a `otro`.
      · Si el resultado queda vacío, se conservan los tipos que había (quitar no deja el expediente sin tipo)."""
    reales = [t for t in c.get('agregar', []) if t != OTRO]
    nuevos = [t for t in tipos if t not in c.get('quitar', [])] + [t for t in reales if t not in tipos]
    if reales:
        nuevos = [t for t in nuevos if t != OTRO]
    elif OTRO in c.get('agregar', []) and not [t for t in nuevos if t != OTRO]:
        nuevos = [OTRO]
    return nuevos or list(tipos)


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
        # Se clasifica en CADA mensaje con toda la conversación: el LLM dice qué tipos de caso agregar o quitar. Los
        # datos ya dados se conservan (no dependen del tipo); lo que el tipo nuevo pida se pregunta.
        dudoso = None
        antes = exp.get('tipos_caso', [])
        c = ia.clasificar_caso(_conversacion(evento), antes, catalogo)
        registro['llamadas'].append(c.get('_llamada'))
        nuevos = _aplicar_clasificacion(antes, c)
        if nuevos != antes:
            registro.update({'tipos_antes': antes, 'tipos_agregados': [t for t in nuevos if t not in antes],
                             'tipos_quitados': [t for t in antes if t not in nuevos], 'por_que': c.get('por_que', '')})
            exp = {**exp, 'tipos_caso': nuevos}
            registro['cambios'].append('tipos_caso')
        elif c.get('opciones') and not antes:
            dudoso = c['opciones']        # con un tipo ya elegido, la duda no cambia nada: no se muestran botones
        # Se extrae aunque el tipo de caso sea dudoso, para no perder lo que la persona ya contó.
        buscar = E.datos_necesarios(exp, catalogo) if exp.get('tipos_caso') else list(catalogo.get('datos', []))
        if exp['datos'].get('papel') == 'victima':  # quien escribe es la víctima: «tengo 24» es la edad de la víctima
            buscar = [{**d, 'pregunta': d.get('pregunta_tu') or d.get('pregunta')} for d in buscar]
        x = ia.extraer_expediente(texto, pregunta, [d for d in buscar if d.get('preguntar', True)], evento.get('texto', ''))
        registro['llamadas'].append(x.get('_llamada'))
        exp, cambios = E.combinar(exp, x.get('datos', {}), catalogo)
        registro['cambios'] += cambios
        if x.get('residencia'):
            exp = {**exp, 'residencia': x['residencia']}
        # La persona solo dijo dónde vive («soy de CDMX»), ya se le preguntó dónde pasó y contestó sin nombrar otro
        # estado («sí», «ya te dije»): se toma donde vive como lugar de los hechos y queda marcado como supuesto.
        if ('lugar_hechos' not in exp['datos'] and exp.get('residencia')
                and exp.get('preguntas', {}).get('lugar_hechos', 0) >= 1):
            exp, cambios = E.combinar(exp, {'lugar_hechos': exp['residencia']}, catalogo)
            if cambios:
                exp = {**exp, 'supuestos': list(dict.fromkeys(exp.get('supuestos', []) + ['lugar_hechos']))}
                registro['cambios'] += cambios
                registro['aviso'] = f'Voy a asumir que lo que te pasó ocurrió en {exp["residencia"]}, donde vives.'
        if not exp.get('tipos_caso') and not dudoso:
            # Todavía no contó ninguna situación («Hola», «necesito ayuda»): primero el relato, luego los datos (los que
            # ya dio, como el estado, se guardaron arriba).
            registro['faltan'] = ['relato']
            primero = not any(m.get('role') == 'assistant' for m in evento.get('historial', []))
            # Si la persona ya escribió algo más que un saludo, no se le contesta como si no hubiera dicho nada.
            conto_algo = len(_texto_usuario(evento).split()) >= 5   # «me encontré una cartera tirada»; no «Hola, soy de Querétaro»
            pide = RELATO_MAS if conto_algo else RELATO
            salida = {'tipo': 'pregunta', 'dato': 'relato', 'texto': f'{SALUDO}\n{pide}' if primero else pide}
            return _cerrar(registro['estado_antes'], _siguiente(estado, 'falta_dato'), exp, salida, registro)
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
        texto = d['pregunta']
        if exp['datos'].get('papel') == 'victima' and d.get('pregunta_tu'):
            texto = d['pregunta_tu']      # le pasó a la persona: «¿Qué edad tienes?», no «¿Qué edad tiene la víctima?»
        if d['id'] == 'lugar_hechos' and exp.get('residencia'):
            texto = f'{exp["residencia"]} es tu lugar de residencia, ¿también ocurrieron los hechos ahí?'
        salida = {'tipo': 'pregunta', 'dato': d['id'], 'texto': texto}
        return _cerrar(registro['estado_antes'], _siguiente(estado, 'falta_dato'), exp, salida, registro)

    reglas = E.reglas_aplicables(exp, catalogo, solo_confirmadas=solo_confirmadas)
    codigos = E.codigos_del_caso(exp, reglas)
    salida = {'tipo': 'orientar', 'reglas': [r['id'] for r in reglas],
              'inciertas': [r['id'] for r in reglas if r['incierta']],
              'codigos': codigos, 'articulos': E.articulos_del_caso(exp, reglas),
              'fuera_de_corpus': exp['datos'].get('lugar_hechos') not in E.CODIGO_DE_ESTADO and not codigos,
              'sin_reglas': not reglas, 'supuestos': list(exp.get('supuestos', [])),
              'tipos_quitados': [t for t in exp.get('orientados', []) if t not in exp['tipos_caso']]}
    exp = {**exp, 'orientados': list(exp['tipos_caso'])}
    evento_interno = 'expediente_completo' if estado == LLENAR_EXPEDIENTE else 'seguimiento'
    return _cerrar(registro['estado_antes'], _siguiente(estado, evento_interno), exp, salida, registro)


def _cerrar(antes: str, despues: str, exp: dict, salida: dict, registro: dict):
    registro.update({'estado_antes': antes, 'estado_despues': despues, 'salida': salida.get('tipo')})
    if registro.get('aviso'):             # algo que el asistente le dice a la persona antes de su salida
        salida = {**salida, 'aviso': registro['aviso']}
    registro['llamadas'] = [x for x in registro['llamadas'] if x]
    return despues, exp, salida, registro
