"""Compuerta de jurisdicción: decide, ANTES de buscar, de qué estado(s) puede ver leyes el LLM.

Problema que resuelve (estudio con usuarios, ronda 1): si la persona no dice dónde ocurrieron los
hechos, el buscador trae artículos de varios códigos penales estatales y el LLM los cita; la persona
cree que esa ley le aplica. Un system prompt que pide «no cites estados» no basta: con los artículos
en el contexto, el LLM los usa igual (set 14 del benchmark: 7 de 12).

Pasos:
  1. ¿Qué lugares menciona la pregunta? Un LLM extrae los lugares y el estado de México al que
     pertenece cada uno («Toluca» → Estado de México). Respaldo sin LLM: los nombres de estado que
     ya reconoce shared/code_routes (`codes_in`).
  2. Cada estado se normaliza a uno de los 32 nombres oficiales (ESTADOS).
  3. ¿Tenemos su código penal? Lo dice la etiqueta `jurisdiction` de los fragmentos en la base
     (lo que se pasa como `disponibles`), no una lista escrita aquí.

Resultado (`decidir`): los lugares (`jurisdictions`) que puede usar la búsqueda —siempre los que no
son estatales (nacional, federal, general/doctrina) más los estados pedidos que sí están— y una nota
para el LLM que dice qué lugar se detectó y qué hacer si no hay lugar o si el estado no está.
"""
from __future__ import annotations

import json
import re

from shared.code_routes import codes_in, fold

# Las 32 entidades federativas (nombre oficial abreviado, como lo escribe la gente) y otras formas
# comunes de nombrarlas. Es la división política del país, no una lista del corpus.
ESTADOS = {
    'Aguascalientes': [], 'Baja California': [], 'Baja California Sur': [], 'Campeche': [],
    'Chiapas': [], 'Chihuahua': [], 'Ciudad de México': ['cdmx', 'distrito federal', 'df', 'd f'],
    'Coahuila': ['coahuila de zaragoza'], 'Colima': [], 'Durango': [],
    'Estado de México': ['edomex', 'mexico', 'edo mex', 'estado de mexico'], 'Guanajuato': [],
    'Guerrero': [], 'Hidalgo': [], 'Jalisco': [], 'Michoacán': ['michoacan de ocampo'], 'Morelos': [],
    'Nayarit': [], 'Nuevo León': [], 'Oaxaca': [], 'Puebla': [], 'Querétaro': ['queretaro de arteaga'],
    'Quintana Roo': [], 'San Luis Potosí': [], 'Sinaloa': [], 'Sonora': [], 'Tabasco': [],
    'Tamaulipas': [], 'Tlaxcala': [], 'Veracruz': ['veracruz de ignacio de la llave'], 'Yucatán': [],
    'Zacatecas': [],
}
_POR_NOMBRE = {fold(n): n for n in ESTADOS} | {fold(a): n for n, als in ESTADOS.items() for a in als}

# Etiquetas de code_routes que son códigos estatales → estado (respaldo sin LLM).
_RUTA_ESTADO = {'CDMX': 'Ciudad de México', 'CPEM': 'Estado de México', 'Morelos': 'Morelos',
                'Querétaro': 'Querétaro'}

EXTRAER_SYSTEM = """Lee una consulta jurídica escrita por una persona en México y extrae los LUGARES de México que menciona (estado, ciudad, municipio, alcaldía, colonia, o una institución de un estado como «Fiscalía de Querétaro»).
Para cada lugar, escribe el ESTADO al que pertenece (una de las 32 entidades federativas; la capital es «Ciudad de México»). Si el lugar no está en México o no sabes a qué estado pertenece, pon null.
Reglas:
- Solo lugares que la consulta MENCIONA. No adivines un estado si no hay lugar.
- «federal», «nacional», «México» como país, y nombres de leyes nacionales (CNPP, Código Penal Federal) NO son lugares.
- «Estado de México», «Edomex» o un municipio mexiquense → «Estado de México».
- «comparar» es true si la consulta pide comparar o contrastar dos o más estados.
Devuelve SOLO JSON, sin texto antes ni después:
{"lugares": [{"texto": "<como aparece>", "estado": "<estado o null>"}], "comparar": true|false}"""


def normalizar_estado(nombre) -> str | None:
    """«queretaro», «CDMX», «Edo. Mex.» → nombre oficial; None si no es una entidad federativa."""
    return _POR_NOMBRE.get(fold(nombre or ''))


def _json(raw: str) -> dict | None:
    m = re.search(r'\{.*\}', raw or '', re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except ValueError:
        return None
    return d if isinstance(d, dict) else None


def extraer_lugares(texto: str, llm) -> dict:
    """{'lugares': [{'texto', 'estado'}], 'comparar': bool, 'fuente': 'llm'|'regex', 'raw': str}.
    Si el LLM falla o devuelve algo ilegible, queda solo el respaldo por regex (codes_in)."""
    out = {'lugares': [], 'comparar': False, 'fuente': 'regex', 'raw': ''}
    if llm is not None:
        try:
            raw = llm.chat(EXTRAER_SYSTEM, f'CONSULTA:\n{texto}', temperature=0.0, max_tokens=300, timeout=60)
            out['raw'] = raw
            d = _json(raw)
            if d is not None:
                lugares = [{'texto': str(x.get('texto') or ''), 'estado': normalizar_estado(x.get('estado'))}
                           for x in (d.get('lugares') or []) if isinstance(x, dict)]
                out.update(lugares=lugares, comparar=bool(d.get('comparar')), fuente='llm')
        except Exception as e:  # noqa: BLE001 — sin LLM, el respaldo por regex sigue funcionando
            out['raw'] = f'error: {type(e).__name__}: {e}'
    # Respaldo y complemento: los nombres de estado que reconoce code_routes (sin LLM).
    ya = {x['estado'] for x in out['lugares']}
    for h in codes_in(texto):
        est = _RUTA_ESTADO.get(h['label'])
        if est and est not in ya:
            out['lugares'].append({'texto': h['match'], 'estado': est, 'regex': True})
            ya.add(est)
    return out


def decidir(texto: str, llm, disponibles: dict[str, str], no_estatales: list[str]) -> dict:
    """Qué lugares puede usar la búsqueda y qué nota recibe el LLM.

    `disponibles`: estado oficial → id de jurisdicción en la base (p. ej. {'Querétaro': 'queretaro'}),
    solo los estados cuyo código penal está en el corpus. `no_estatales`: ids que no son de un
    estado (nacional, federal, general) y que siempre se incluyen."""
    ex = extraer_lugares(texto, llm)
    estados = []
    for x in ex['lugares']:
        if x['estado'] and x['estado'] not in estados:
            estados.append(x['estado'])
    en_base = [e for e in estados if e in disponibles]
    faltan = [e for e in estados if e not in disponibles]
    sin_estado = [x['texto'] for x in ex['lugares'] if not x['estado']]
    jur = list(no_estatales) + [disponibles[e] for e in en_base]
    menciona = lambda e: ', '.join(f'«{x["texto"]}»' for x in ex['lugares'] if x['estado'] == e)  # noqa: E731
    if not estados:
        nota = ('LUGAR: la persona no dijo en qué estado ocurrieron los hechos. Los fragmentos del CONTEXTO solo '
                'incluyen leyes nacionales, federales y doctrina, a propósito. No menciones ni cites artículos de '
                'códigos penales de ningún estado. Explica que la respuesta depende del estado, di qué tipo de '
                'delito podría ser y qué dicen las leyes nacionales si aplican, y pregunta en qué estado ocurrieron '
                'los hechos.')
        if sin_estado:
            nota += f' (Mencionó {", ".join("«" + s + "»" for s in sin_estado)}, pero no se pudo saber de qué estado es: pregúntalo.)'
    else:
        partes = []
        if en_base:
            partes.append('LUGAR: ' + '; '.join(f'{e} (la persona mencionó {menciona(e)})' for e in en_base) + '.')
            if len(en_base) > 1:
                partes.append('La persona pregunta por varios estados: responde para CADA uno de ellos, con su '
                              'propio código penal, y no agregues estados que no pidió.')
            else:
                partes.append('Responde con el código penal de ese estado y las leyes nacionales o federales que '
                              'apliquen. No cites códigos penales de otros estados. No vuelvas a preguntar el estado.')
        if faltan:
            partes.append(f'La persona mencionó {", ".join(faltan)}, pero el código penal de '
                          f'{"ese estado" if len(faltan) == 1 else "esos estados"} NO está en los documentos. Dilo '
                          'claramente, no uses el código de otro estado en su lugar, explica lo que sí aplica en todo '
                          'el país (leyes nacionales o federales) y recomienda consultar a una persona abogada de ese estado.')
        nota = ' '.join(partes)
    return {'lugares': ex['lugares'], 'comparar': ex['comparar'], 'fuente': ex['fuente'], 'raw': ex['raw'],
            'estados': estados, 'en_base': en_base, 'faltan': faltan, 'jurisdictions': jur, 'nota': nota}
