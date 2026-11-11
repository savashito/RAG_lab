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
Si una regla está marcada como incierta, di qué dato falta para saber si aplica."""


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


def orientar(*, cur, table: str, salida: dict, expediente: dict, catalogo: dict, conversacion: str,
             contexto: str, embed, chat, system: str, tope: int | None = None) -> dict:
    """Salida 'orientar' de la máquina → {respuesta, contexto: [artículos con entra/distancia/tokens], ...}.
    `embed(texto) → vector` y `chat(system, user) → str` los pone quien llama."""
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
    t_contexto = round(time.time() - t0, 2)
    datos = '\n'.join(f'- {k}: {v}' for k, v in (expediente.get('datos') or {}).items()) or '(ninguno)'
    lista = '\n'.join(f'- {r["delito"]}' + (f' — {r["condicion"]}' if r.get('condicion') else '')
                      + (' [INCIERTA: falta un dato]' if r['incierta'] else '') for r in reglas) or '(ninguna)'
    texto = '\n\n'.join(f'[{a["orden"]}] {NOMBRES.get(a["codigo"], a["codigo"])} — {a["ruta"]}\n{a["texto"]}'
                        for a in elegidos)
    user = ORIENTAR_USER.format(conversacion=conversacion, datos=datos, reglas=lista, contexto=texto or '(vacío)')
    t1 = time.time()
    respuesta = chat(system, user)
    return {'respuesta': respuesta, 'modo_contexto': contexto, 'tope_tokens': tope or TOPE[contexto],
            'tokens_contexto': sum(tokens(a['texto']) for a in elegidos),
            'contexto': [{'codigo': a['codigo'], 'num': a['num'], 'entra': a['entra'], 'orden': a.get('orden'),
                          'distancia': a.get('distancia'), 'tokens': tokens(a['texto'])} for a in arts],
            'no_encontrados': sorted({f'{k} {n}' for k, ns in (salida.get('articulos') or {}).items() for n in ns}
                                     - {f'{a["codigo"]} {a["num"]}' for a in arts}),
            'segundos': {'contexto': t_contexto, 'respuesta': round(time.time() - t1, 2)}}
