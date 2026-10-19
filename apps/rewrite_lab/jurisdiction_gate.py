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
- Si una palabra parece un lugar pero no la reconoces (una sigla o un nombre que no conoces), inclúyela con estado null.
- «federal», «nacional», «México» como país, y nombres de leyes nacionales (CNPP, Código Penal Federal) NO son lugares.
- «Estado de México», «Edomex» o un municipio mexiquense → «Estado de México».
- «rol» de cada lugar: «hechos» si ahí ocurrió lo que se pregunta, o si la consulta pregunta por la ley de ese lugar («¿qué dice el código de Querétaro?»); «otro» si es solo donde la persona vive, trabaja o de donde es, sin decir que ahí ocurrieron los hechos. Si algo pasó en su casa, su trabajo o su colonia, ese lugar es de los «hechos».
- «comparar» es true si la consulta pide comparar o contrastar dos o más estados.
- «tipo»: qué clase de asunto es, uno de:
  «delito_comun»: cualquier conducta que sea o pueda ser un delito común, aunque ocurra por internet, por teléfono o con tarjeta: robo, fraude, abuso de confianza, lesiones, homicidio, amenazas, daño a la propiedad, despojo, allanamiento, violencia familiar, abuso o acoso sexual, hechos de tránsito, maltrato animal, sustracción de menores, etc. Cada estado los define en su propio código penal.
  «delito_federal»: delitos que persigue la Fiscalía General de la República: lavado de dinero, narcotráfico, armas de uso exclusivo del Ejército, contrabando, delitos fiscales federales, delitos de o contra servidores públicos federales, delitos electorales federales.
  «ley_general»: delitos definidos en una ley general que aplica igual en todo el país: secuestro, extorsión (incluido el cobro de piso y el secuestro virtual), trata de personas, desaparición de personas, tortura, delincuencia organizada.
  «procedimiento»: cómo funciona el proceso penal, sin preguntar qué delito es: detención, flagrancia, derechos de la persona detenida o de la víctima, audiencias, plazos, medidas cautelares, prisión preventiva, acuerdos reparatorios, criterio de oportunidad, procedimiento abreviado, reparación del daño.
  «otro»: nada de lo anterior.
Devuelve SOLO JSON, sin texto antes ni después:
{"lugares": [{"texto": "<como aparece>", "estado": "<estado o null>", "rol": "hechos"|"otro"}], "comparar": true|false, "tipo": "delito_comun"|"delito_federal"|"ley_general"|"procedimiento"|"otro"}"""


TIPOS = ('delito_comun', 'delito_federal', 'ley_general', 'procedimiento', 'otro')


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
    # Sin LLM no se sabe si la respuesta depende del estado: se supone que sí (lo seguro es preguntar).
    out = {'lugares': [], 'comparar': False, 'tipo': None, 'depende_del_estado': True, 'delito_federal': False,
           'fuente': 'regex', 'raw': ''}
    if llm is not None:
        try:
            raw = llm.chat(EXTRAER_SYSTEM, f'CONSULTA:\n{texto}', temperature=0.0, max_tokens=300, timeout=60)
            out['raw'] = raw
            d = _json(raw)
            if d is not None:
                lugares = [{'texto': str(x.get('texto') or ''), 'estado': normalizar_estado(x.get('estado')),
                            'rol': 'otro' if x.get('rol') == 'otro' else 'hechos'}
                           for x in (d.get('lugares') or []) if isinstance(x, dict)]
                out.update(lugares=lugares, comparar=bool(d.get('comparar')), fuente='llm',
                           tipo=d.get('tipo') if d.get('tipo') in TIPOS else 'otro')
                # Lo que el filtro necesita sale del tipo, no de un «sí/no» del LLM (que resultó inestable):
                # los delitos comunes y lo que no se reconoce dependen del estado (lo seguro es preguntar).
                out['depende_del_estado'] = out['tipo'] in ('delito_comun', 'otro')
                out['delito_federal'] = out['tipo'] == 'delito_federal'
        except Exception as e:  # noqa: BLE001 — sin LLM, el respaldo por regex sigue funcionando
            out['raw'] = f'error: {type(e).__name__}: {e}'
    # Respaldo y complemento: los nombres de estado que reconoce code_routes (sin LLM).
    ya = {x['estado'] for x in out['lugares']}
    for h in codes_in(texto):
        est = _RUTA_ESTADO.get(h['label'])
        if est and est not in ya:
            out['lugares'].append({'texto': h['match'], 'estado': est, 'rol': 'hechos', 'regex': True})
            ya.add(est)
    return out


def decidir(texto: str, llm, disponibles: dict[str, str], no_estatales: list[str], federal: str = 'federal') -> dict:
    """Qué lugares puede usar la búsqueda y qué nota recibe el LLM.

    `disponibles`: estado oficial → id de jurisdicción en la base (p. ej. {'Querétaro': 'queretaro'}),
    solo los estados cuyo código penal está en el corpus. `no_estatales`: ids que no son de un
    estado (nacional, federal, general); se incluyen todos salvo `federal` (el Código Penal Federal),
    que solo entra si el delito es federal: también define delitos comunes (fraude, violencia
    familiar…) que en un caso común NO aplican, y el LLM lo usaba en lugar del código del estado
    (corridas 52–55)."""
    ex = extraer_lugares(texto, llm)
    estados, otros = [], []   # estados donde ocurrieron los hechos · estados mencionados por otra razón (vive, trabaja)
    for x in ex['lugares']:
        lista = estados if x.get('rol', 'hechos') == 'hechos' else otros
        if x['estado'] and x['estado'] not in lista:
            lista.append(x['estado'])
    otros = [e for e in otros if e not in estados]
    en_base = [e for e in estados if e in disponibles]
    faltan = [e for e in estados if e not in disponibles]
    sin_estado = [x['texto'] for x in ex['lugares'] if not x['estado']]
    jur = [j for j in no_estatales if j != federal or ex['delito_federal']] + [disponibles[e] for e in en_base]
    menciona = lambda e: ', '.join(f'«{x["texto"]}»' for x in ex['lugares'] if x['estado'] == e)  # noqa: E731
    if not estados and otros and ex['depende_del_estado']:
        # Solo se sabe dónde vive o trabaja la persona, no dónde ocurrió: ese código puede servir como hipótesis,
        # pero no se puede dar por hecho (set 12 de Karen, caso de Carlos).
        jur += [disponibles[e] for e in otros if e in disponibles]
        nota = (f'LUGAR: la persona mencionó {", ".join(f"{e} ({menciona(e)})" for e in otros)}, pero como lugar donde '
                'vive, trabaja o de donde es; NO dijo dónde ocurrieron los hechos. No des por hecho que ocurrieron ahí. '
                'Puedes explicar qué diría el código penal de ese estado SI los hechos ocurrieron ahí, dejando claro que es '
                'una suposición, y pregunta en qué estado ocurrieron. No cites códigos de otros estados.')
    elif not estados and not ex['depende_del_estado']:
        nota = ('LUGAR: la persona no dijo un estado, y no hace falta: la pregunta se responde con leyes que aplican en '
                'todo el país (nacionales, generales o federales). Responde directamente con ellas, sin preguntar el '
                'estado. No cites códigos penales de ningún estado.')
    elif not estados:
        nota = ('LUGAR: la persona no dijo en qué estado ocurrieron los hechos. No menciones ni cites artículos de '
                'códigos penales de ningún estado. Explica que la respuesta depende del estado, di qué tipo de '
                'delito podría ser y qué dicen las leyes nacionales si aplican, y pregunta en qué estado ocurrieron '
                'los hechos.')
        if sin_estado:
            nota += (f' La persona escribió {", ".join("«" + s + "»" for s in sin_estado)}, que podría ser un lugar, '
                     'pero no se reconoció: pregúntale a qué lugar se refiere y en qué estado ocurrió.')
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
    # La nota es una instrucción interna: la persona no debe leer sobre «la nota» ni «el CONTEXTO».
    nota += ' (Instrucción interna: no menciones esta nota, el CONTEXTO ni los fragmentos en tu respuesta.)'
    return {'lugares': ex['lugares'], 'comparar': ex['comparar'], 'fuente': ex['fuente'], 'raw': ex['raw'],
            'tipo': ex['tipo'], 'depende_del_estado': ex['depende_del_estado'], 'delito_federal': ex['delito_federal'], 'estados': estados,
            'otros': otros, 'en_base': en_base, 'faltan': faltan, 'jurisdictions': jur, 'nota': nota}
