"""
Orientación de la consulta (ronda 3): cuando la máquina de estados llega a ORIENTACION, el LLM escribe la respuesta
con el texto de los artículos que el catálogo dice que aplican (no con lo que trae el buscador).

Qué artículos entran al contexto (CONTEXTO, se elige en cada consulta para poder compararlos en el benchmark):
  · 'todos'      todos los artículos de las reglas que aplican, en el orden del catálogo (primero las reglas que no son
                 inciertas), hasta TOPE['todos'] tokens;
  · 'embedding'  los mismos candidatos, ordenados por parecido con el caso (distancia de embeddings entre lo que contó la
                 persona y cada artículo); primero el más parecido de cada regla (ninguna regla queda fuera) y luego
                 el resto, hasta TOPE['embedding'] tokens.

Las funciones reciben lo que necesitan (conexión, embeddings, LLM): main.py las conecta y las pruebas usan falsos.
"""
from __future__ import annotations

import re
import time
import unicodedata

from consulta.leyes import CODIGOS, NOMBRES

CONTEXTOS = ('todos', 'embedding')
TOPE = {'todos': 22000, 'embedding': 6000}   # tokens de artículos; el LLM de la app tiene 32,768 de contexto
CHARS_POR_TOKEN = 3.5                        # aproximado para español

ORIENTAR_USER = """CASO (lo que contó la persona y lo que le preguntó el asistente):
{conversacion}

DATOS DEL EXPEDIENTE:
{datos}

REGLAS DEL CATÁLOGO QUE APLICAN (delito y cuándo aplica):
{reglas}

CONTEXTO (artículos que el catálogo relaciona con el caso):
{contexto}

Orienta a la persona sobre su caso con base solo en estos artículos. Cita cada artículo que uses con su ley y número.
Si una regla está marcada como incierta, di qué dato falta para saber si aplica.
No supongas el género de la persona: usa lenguaje neutro («no te encuentras sin apoyo», «cuentas con apoyo»; nunca «no
estás sola» o «no estás solo»), salvo que la persona haya dicho su género."""

# Un mensaje que llega cuando ya se orientó (seguimiento en ORIENTACION): sin esto, el LLM recibe la misma instrucción y
# los mismos artículos y repite la orientación completa (y las preguntas que la persona ya contestó).
SEGUIMIENTO = """

YA ORIENTASTE a la persona: tu orientación anterior está en el CASO. Su ÚLTIMO MENSAJE es:
«{ultimo}»
Responde a ese mensaje: qué aporta de nuevo y si cambia algo de lo que ya dijiste, con los artículos que correspondan.
No repitas lo que ya explicaste ni la estructura completa de la orientación, y no vuelvas a preguntar lo que la persona
ya contestó. Si no cambia nada, dilo en pocas palabras y responde su duda."""

# Después de orientar, la máquina pregunta los datos complementarios (los que el tipo de caso lista y ninguna regla
# usa). El LLM no los pregunta: si lo hiciera, la persona vería la misma pregunta dos veces.
POR_PREGUNTAR = """

Después de tu respuesta, el asistente le hará a la persona estas preguntas, una por una:
{preguntas}
No hagas tú esas preguntas ni otras sobre lo mismo. Si alguna cambia la orientación (por ejemplo, una agravante),
explica cómo la cambia y termina con una frase que diga que le harás unas preguntas para precisarla."""

# Al terminar los complementarios: una actualización corta, no la orientación completa otra vez.
ACTUALIZACION = """

YA ORIENTASTE a la persona: tu orientación anterior está en el CASO. Después le preguntaste unos datos y contestó:
{datos}
Su ÚLTIMO MENSAJE es: «{ultimo}»
En pocas líneas di qué cambia con esos datos (qué artículos o agravantes aplican ahora y cuáles no), con su ley y
número, y responde lo que haya preguntado. Si un dato es «no sabe», di qué cambiaría según la respuesta. No repitas la
orientación completa ni vuelvas a preguntar lo que ya contestó."""


# Con «preguntas redactadas por el LLM»: la máquina decide QUÉ dato falta; el LLM solo decide CÓMO pedirlo.
PREGUNTAR_SYSTEM = """Eres Tlacua, un asistente que orienta a personas en México sobre problemas legales. Hablas como una
persona cercana y tranquila, en español de México, tuteando y con lenguaje cotidiano. Estás reuniendo los datos que
necesitas para orientar a la persona; todavía no la orientas.

Escribe UN mensaje breve (1 a 3 oraciones) que haga dos cosas:

1. Responder a lo que la persona acaba de decir, de forma concreta. Nombra lo que contó, no un sentimiento genérico:
   - si cuenta algo grave (amenazas, que le piden dinero, que es menor de edad, que tiene miedo), muestra que lo
     entendiste y, si ayuda, dale tranquilidad: que cuenta con apoyo, que no es su culpa, que hay forma de actuar;
   - si solo dio un dato (un estado, una edad, un «sí»), agradécelo en pocas palabras o pasa directo a la pregunta.
   No uses fórmulas ni frases de cajón: nada de «Lamento mucho que estés pasando por esto», «Siento mucho que estés
   pasando por esta situación», «Entiendo, gracias por la información». No repitas nada que el asistente ya dijo en la
   CONVERSACIÓN. No juzgues ni culpes («¿por qué mandaste las fotos?»), no exageres y no prometas resultados.
2. Hacer la PREGUNTA que falta. Puedes cambiar las palabras, pero no el sentido: pregunta exactamente lo mismo que la
   PREGUNTA DEL CATÁLOGO. Para el lugar, pregunta dónde pasó; nunca dónde vive o dónde se encuentra la persona. Si
   ayuda, di en pocas palabras para qué la necesitas. Pregunta solo eso: ningún otro dato.
   Si en la CONVERSACIÓN el asistente ya hizo esa pregunta y la persona contestó otra cosa, no la entendió: pregúntala
   de otra forma, sin la palabra que causó la confusión y con ejemplos. Para el lugar, «estado» puede entenderse como
   estado de ánimo o de ebriedad: pregunta «¿en qué ciudad o parte de México pasó? (por ejemplo, CDMX o Querétaro)».

Además:
- Si hay un AVISO, dilo con tus palabras. Sin AVISO, no digas que supones o que tomas como base algún dato.
- No supongas su género: usa lenguaje neutro («cuentas con apoyo», nunca «no estás sola» o «no estás solo»), salvo que
  la persona lo haya dicho.
- Si la persona dijo que le pasó a ella (papel: victima), háblale de tú sobre lo que le pasó: «¿qué edad tienes?», nunca
  «la víctima».
- Si el DATO QUE FALTA es «relato», la persona todavía no ha contado qué le pasó: invítala a contar su situación. Si
  en la CONVERSACIÓN el asistente no ha dicho nada todavía, empieza presentándote: «Hola, soy Tlacua, tu asistente jurídico».
- No des orientación legal ni cites artículos: eso viene después, cuando tengas los datos.

Ejemplos del tono (no los copies):
- Persona: «no aun no, pero si no les pago lo van a hacer» → «Que te presionen así es muy angustiante, y lo que te
  están haciendo es un delito. ¿Qué edad tienes?»
- Persona: «17» → «Gracias por decírmelo; que seas menor de edad importa, porque la ley te protege de forma especial.
  ¿Estuviste de acuerdo en que se compartieran o publicaran?»
- Persona: «CDMX» → «Gracias. ¿Te pasó a ti, te acusan a ti, o le pasó a otra persona?»"""

PREGUNTAR_USER = """CONVERSACIÓN:
{conversacion}

DATOS QUE YA DIO:
{datos}

{aviso}DATO QUE FALTA: {dato}
PREGUNTA DEL CATÁLOGO: {pregunta}
PARA QUÉ SE PREGUNTA: {para_que}{opciones}"""


def mensajes_pregunta(conversacion: str, salida: dict, catalogo: dict, expediente: dict | None = None,
                      system: str | None = None) -> list[dict]:
    """Salida 'pregunta' de la máquina → mensajes para que el LLM redacte la pregunta. `system`: el prompt guardado o el
    que la persona escribió en Preguntar (Catálogo); sin él, PREGUNTAR_SYSTEM (la versión inicial)."""
    d = next((x for x in catalogo.get('datos', []) if x['id'] == salida.get('dato')), {})
    datos = '\n'.join(f'- {k}: {v}' for k, v in ((expediente or {}).get('datos') or {}).items()) or '(ninguno)'
    user = PREGUNTAR_USER.format(conversacion=conversacion, datos=datos, dato=salida.get('dato', ''),
                                 aviso=f'AVISO: {salida["aviso"]}\n' if salida.get('aviso') else '',
                                 pregunta=salida.get('texto', ''), para_que=d.get('para_que') or '(no dice)',
                                 opciones=f'\nOPCIONES: {", ".join(d["opciones"])}' if d.get('opciones') else '')
    return [{'role': 'system', 'content': (system or '').strip() or PREGUNTAR_SYSTEM}, {'role': 'user', 'content': user}]


def _norm(s: str) -> str:
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+', ' ', s).strip().lower()


def tokens(texto: str) -> int:
    return int(len(texto) / CHARS_POR_TOKEN) + 1


def leer_articulos(cur, table: str, articulos: dict[str, list[str]]) -> list[dict]:
    """{código: [números]} → [{codigo, num, ruta, texto, ids}] con el texto de cada artículo (sus fragmentos juntos) y
    los ids de sus fragmentos (para la distancia de embeddings). Los que no están en el corpus no se devuelven."""
    out = []
    for codigo, nums in articulos.items():
        source = CODIGOS.get(codigo)
        for num in nums:
            objetivo = _norm('Artículo ' + num)
            primero = re.split(r'\s+', num.strip())[0]
            cur.execute(f"SELECT id, hierarchy, text FROM {table} WHERE source = %s AND hierarchy ILIKE %s "
                        f"ORDER BY position, part", (source, f'%Artículo {primero}%'))
            filas = [(i, h, t) for i, h, t in cur.fetchall() if _norm(h.split(' > ')[-1]) == objetivo]
            if not filas:
                continue
            partes = [t[t.find(h) + len(h):].strip() if t.find(h) >= 0 else t for _, h, t in filas]
            out.append({'codigo': codigo, 'num': num, 'ruta': filas[0][1], 'texto': '\n\n'.join(partes),
                        'ids': [i for i, _, _ in filas]})
    return out


def distancias(cur, table: str, vector, ids: list) -> dict:
    """{id de fragmento: distancia coseno con el vector del caso}."""
    if not ids:
        return {}
    cur.execute(f"SELECT id, embedding <=> %s FROM {table} WHERE id = ANY(%s)", (vector, list(ids)))
    return {i: float(d) for i, d in cur.fetchall()}


def elegir(arts: list[dict], reglas: list[dict], contexto: str, tope: int | None = None) -> list[dict]:
    """Marca en cada artículo `entra` (va al contexto) y `orden`. Un artículo citado por varias reglas cuenta una vez.
    `arts` trae `distancia` si contexto == 'embedding'."""
    tope = tope or TOPE[contexto]
    clave = {(a['codigo'], _norm(a['num'])): a for a in arts}
    por_regla = []                                    # (regla, [artículos]) con las inciertas al final
    for r in sorted(reglas, key=lambda r: bool(r.get('incierta'))):
        xs = [clave[(k, _norm(n))] for k, ns in (r.get('articulos') or {}).items() for n in ns if (k, _norm(n)) in clave]
        por_regla.append((r, xs))
    if contexto == 'todos':
        orden = [a for _, xs in por_regla for a in xs]
    else:
        lejos = lambda a: a.get('distancia', 9.0)   # noqa: E731
        mejores = [min(xs, key=lejos) for _, xs in por_regla if xs]
        orden = mejores + sorted(arts, key=lejos)
    usados, total, n = set(), 0, 0
    for a in arts:
        a['entra'] = False
    for a in orden:
        k = (a['codigo'], _norm(a['num']))
        if k in usados:
            continue
        usados.add(k)
        t = tokens(a['texto'])
        if total + t > tope and n:                    # el primero entra siempre (aunque sea largo)
            continue
        n, total = n + 1, total + t
        a.update({'entra': True, 'orden': n})
    return sorted([a for a in arts if a['entra']], key=lambda a: a['orden'])


def preparar(*, cur, table: str, salida: dict, expediente: dict, catalogo: dict, conversacion: str,
             contexto: str, embed, tope: int | None = None, seguimiento: str | None = None) -> dict:
    """Salida 'orientar' de la máquina → {user: el mensaje para el LLM, y qué artículos entraron al contexto}.
    `embed(texto) → vector` lo pone quien llama. La respuesta la pide quien llama (orientar() o en streaming).
    `seguimiento`: el último mensaje de la persona cuando ya se había orientado (estado ORIENTACION antes del mensaje,
    o una actualización: salida['actualizacion'])."""
    if contexto not in CONTEXTOS:
        raise ValueError(f'contexto desconocido: {contexto!r} (usa {CONTEXTOS})')
    t0 = time.time()
    reglas_id = set(salida.get('reglas') or [])
    inciertas = set(salida.get('inciertas') or [])
    reglas = [{**r, 'incierta': r['id'] in inciertas} for r in catalogo.get('reglas', []) if r['id'] in reglas_id]
    arts = leer_articulos(cur, table, salida.get('articulos') or {})
    if contexto == 'embedding' and arts:
        vec = embed(conversacion)
        dist = distancias(cur, table, vec, [i for a in arts for i in a['ids']])
        for a in arts:                                # la distancia del artículo = la de su fragmento más cercano
            a['distancia'] = round(min((dist[i] for i in a['ids'] if i in dist), default=9.0), 4)
    elegidos = elegir(arts, reglas, contexto, tope)
    supuestos = set(expediente.get('supuestos') or [])
    datos = '\n'.join(f'- {k}: {v}' + (' (SUPUESTO: la persona solo dijo que vive ahí; dilo en la respuesta)'
                                       if k in supuestos else '')
                      for k, v in (expediente.get('datos') or {}).items()) or '(ninguno)'
    if expediente.get('hechos'):              # lo que contó y no cabe en ningún dato (campo «hechos» del expediente)
        datos += '\n\nOTROS HECHOS QUE CONTÓ LA PERSONA:\n' + '\n'.join(f'- {h}' for h in expediente['hechos'])
    lista = '\n'.join(f'- {r["delito"]}' + (f' — {r["condicion"]}' if r.get('condicion') else '')
                      + (' [INCIERTA: falta un dato]' if r['incierta'] else '') for r in reglas) or '(ninguna)'
    texto = '\n\n'.join(f'[{a["orden"]}] {NOMBRES.get(a["codigo"], a["codigo"])} — {a["ruta"]}\n{a["texto"]}'
                        for a in elegidos)
    user = ORIENTAR_USER.format(conversacion=conversacion, datos=datos, reglas=lista, contexto=texto or '(vacío)')
    if salida.get('actualizacion'):
        user += ACTUALIZACION.format(ultimo=seguimiento or '',
                                     datos='\n'.join(f'- {k}: {v}' for k, v in salida['actualizacion'].items()))
    elif seguimiento:
        user += SEGUIMIENTO.format(ultimo=seguimiento)
    if salida.get('por_preguntar'):
        user += POR_PREGUNTAR.format(preguntas='\n'.join(f'- {q}' for q in salida['por_preguntar']))
    return {'user': user, 'seguimiento': bool(seguimiento), 'actualizacion': bool(salida.get('actualizacion')),
            'modo_contexto': contexto, 'tope_tokens': tope or TOPE[contexto],
            'tokens_contexto': sum(tokens(a['texto']) for a in elegidos),
            'contexto': [{'codigo': a['codigo'], 'num': a['num'], 'entra': a['entra'], 'orden': a.get('orden'),
                          'distancia': a.get('distancia'), 'tokens': tokens(a['texto'])} for a in arts],
            'no_encontrados': sorted({f'{k} {n}' for k, ns in (salida.get('articulos') or {}).items() for n in ns}
                                     - {f'{a["codigo"]} {a["num"]}' for a in arts}),
            'segundos': {'contexto': round(time.time() - t0, 2)}}


def orientar(*, chat, system: str, **kw) -> dict:
    """preparar() + la respuesta completa del LLM (sin streaming). `chat(system, user) → str`."""
    o = preparar(**kw)
    t1 = time.time()
    o['respuesta'] = chat(system, o.pop('user'))
    o['segundos']['respuesta'] = round(time.time() - t1, 2)
    return o
