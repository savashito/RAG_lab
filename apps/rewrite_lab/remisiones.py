"""Remisiones entre artículos: «además de las penas previstas en el artículo 220 de este Código».

Un artículo a veces no se entiende solo: el 224 de la CDMX suma pena a la del 220; el 182 del Estado de México toma la
pena del 181. Este módulo DETECTA esas remisiones en el texto de un artículo (sin LLM: regex) y dice, para cada una, a
qué artículo apunta, si es del mismo código o de otra ley, y si la rechaza (y por qué). Seguirlas (traer el artículo
remitido al contexto) es otro paso que todavía no está conectado al buscador.

Lo que más hay que rechazar no son remisiones mal leídas sino menciones que no son remisiones: en los códigos del
corpus, la mayoría de las palabras «artículo» dentro de un artículo son notas de reforma («Reformado por Artículo
Primero del Decreto…», «Se reforman los artículos 29 y 222…», «Antes decía:») o decretos pegados al final del texto.

Cada remisión:
  articulo   etiqueta normalizada («220», «211 Ter», «2o»)
  fraccion   «VI» si dice «fracción VI del artículo 127»; None si no
  ambito     'mismo' (dice «de este Código / del presente Código / de este ordenamiento»), 'otra_ley' (nombra otra ley)
             o 'mismo_supuesto' (no nombra ley: se SUPONE del mismo código, hipótesis a verificar contra el índice)
  ley        nombre de la otra ley si ambito == 'otra_ley'
  tipo       'directa' | 'multiple' (lista «220 y 224») | 'rango' («220 a 225») | 'relativa' («el artículo anterior»)
  materia    'pena' (habla de penas o sanciones), 'calificativa' (agravantes, calificativas) u 'otra'
  rechazo    None si es una remisión a seguir; si no: 'encabezado_pegado' (el encabezado de otro artículo quedó dentro de
             este fragmento), 'nota_reforma', 'transitorio', 'otra_ley', 'rango_amplio'
  texto      el fragmento donde se detectó (para revisar a mano)
"""
from __future__ import annotations

import re

# Sufijos latinos y numerales de los artículos: «211 Ter», «199 Octies», «11 Quinquies 1», «2o».
_SUF = (r'(?:o\b|\s*[º°]|\s*(?:bis|ter|qu[aá]ter|quater|quintus|quinquies|sextus|sexies|septimus|septies|octies|'
        r'nonies|decies)\b)?(?:\s+[1-9]\b(?!\s*(?:a[ñn]os?|d[ií]as?|meses|veces)))?')
_NUM = r'\d{1,4}' + _SUF
_SEP = r'\s*(?:,|\by\b|\be\b|\bo\b)\s*(?:(?:los|el|del)\s+)?(?:art[íi]culos?\s+)?'
_RANGO = r'\s+(?:a|al|hasta(?:\s+el)?)\s+'
_PALABRA = r'(?:art[íi]culos?|arts?\.|numerales?|preceptos?|diversos?)'
REMISION_RE = re.compile(
    r'(?i)\b' + _PALABRA + r'\s+(' + _NUM + r'(?:(?:' + _SEP + r'|' + _RANGO + r')' + _NUM + r')*)')
RELATIVA_RE = re.compile(r'(?i)\b(?:art[íi]culos?|preceptos?|numerales?)\s+(?:inmediat[oa]s?\s+)?(anteriores|anterior|precedentes?|siguientes?|que antecede|que precede)\b'
                         r'|\ben\s+los\s+(?:dos|tres)\s+(siguientes|anteriores)\b')
_RELATIVA_NORM = {'anterior': 'anterior', 'precedente': 'anterior', 'que antecede': 'anterior', 'que precede': 'anterior',
                  'anteriores': 'anteriores', 'precedentes': 'anteriores', 'siguiente': 'siguiente', 'siguientes': 'siguientes'}
# Anotaciones de reforma pegadas al texto vigente: «_Párrafo reformado DOF 05-12-1979_», «(Ref. P. O. No. 41, 25-VII-08)».
_ANOTACION = re.compile(r'(?i)_[^_\n]{0,160}?(?:reformad|adicionad|derogad|fe de erratas|[úu]ltima\s+reforma)[^_\n]{0,160}_|'
                        r'<u>\s*C[ÓO]DIGO PENAL[^<]{0,60}</u>|'
                        r'\((?:ref|adic|derog)[^)]{0,100}\)')
_FRACCION_ANTES = re.compile(r'(?i)\b(?:fracci[oó]n(?:es)?|inciso|apartado)\s+([IVXLC]+|[a-z]\)|[A-Z])\b[^.;]{0,40}?\b(?:del|de los)\s*$')
_FRACCION_DESPUES = re.compile(r'(?i)^\s*,?\s*(?:fracci[oó]n|inciso|apartado)\s+([IVXLC]+|[a-z]\)|[A-Z])\b')
# Después del número: ¿dice de qué ley es?
_MISMO = re.compile(r'(?i)^[^.;]{0,40}?\b(?:de\s+(?:este|éste|esta|ésta)|del\s+(?:presente|mismo|propio))\s+(?:c[oó]digo|ordenamiento|ley|cuerpo legal)\b')
_OTRA = re.compile(r'(?i)^[^.;]{0,120}?\b(?:del|de la|de los)\s+((?:c[oó]digo|ley|constituci[oó]n|reglamento|decreto|estatuto)\b[^.;,()]{0,90})')
# Notas de reforma y decretos: la mención de «artículo» no es una remisión.
_NOTA = re.compile(r'(?i)reforma vigente|antes dec[ií]a|\b(?:reformad|adicionad|derogad|recorrid)[oa]s?\b|\bdecreto\b|\bDOF\b|'
                   r'\b(?:las|la)\s+(?:reformas?|adici[oó]n|adiciones|derogaci[oó]n)\b|'
                   r'diario oficial|peri[oó]dico oficial|gaceta|\bPOGG\b|\bPOEM\b|\bP\.\s*O\.|publicad[oa] en|entrar[aá] en vigor|transitori')
# Verbos de decreto: se buscan en la oración LARGA (sin cortar en «;»), porque los decretos enumeran «se reforman los
# artículos 29…; 222…; se adicionan…». «Se deroga» en singular NO: en una lista de fracciones es texto vigente.
_DECRETO = re.compile(r'(?i)\bse\s+(?:reforma|reforman|adiciona|adicionan|derogan|abroga|abrogan)\b|para quedar como sigue|'
                      r'\bexpido el presente\b|\bpresente decreto\b')
# «de dicho ordenamiento», «de la citada ley»: es la ley que la oración nombró antes, si nombró alguna.
_DICHO = re.compile(r'(?i)^[^.;]{0,40}?\b(?:de\s+)?(?:dich[oa]|citad[oa]|referid[oa])\s+(?:ordenamiento|ley|c[oó]digo)\b')
_LEY_NOMBRADA = re.compile(r'(?-i:\b(?:Ley|C[oó]digo|Constituci[oó]n|Reglamento)\s+(?:General|Federal|Nacional|Org[aá]nica|de|del|Pol[ií]tica)\b)')
# Desde un encabezado de transitorios («TRANSITORIOS», «T R A N S I T O R I O S», «ARTÍCULOS TRANSITORIOS…») lo que sigue
# son artículos de decretos, no del código vigente: no se siguen.
_TRANSITORIOS = re.compile(r'(?-i:\bT\s?R\s?A\s?N\s?S\s?I\s?T\s?O\s?R\s?I\s?O\s?S\b)')
_PENA = re.compile(r'(?i)\bpenas?\b|\bsanci[oó]n|\bsancionar|\bprisi[oó]n|\bmulta|\bse\s+impondr|\bpunibilidad|\bpunible')
_CALIF = re.compile(r'(?i)\bcalificad|\bcalificativ|\bagravant|\batenuant|\bagravad')
# Rangos de más de estos artículos no se siguen (son referencias a capítulos enteros).
RANGO_MAX = 3


def _oracion(texto: str, ini: int, fin: int, larga: bool = False) -> str:
    """La oración que contiene [ini, fin). Corta: termina en «.», salto de línea o «;». Larga: no corta en «;» (para
    los decretos, que separan con «;» la lista «se reforman los artículos 29…; 222…; se adicionan…»)."""
    seps = ('. ', '\n') if larga else ('. ', '\n', ';')
    a = max(texto.rfind(x, 0, ini) for x in seps)
    b = min([y for y in (texto.find(x, fin) for x in seps) if y >= 0] or [len(texto)])
    return texto[a + 1:b + 1]


def normalizar(etiqueta: str) -> str:
    """«211 ter», «2 o», «2°» → «211 Ter», «2o», «2o»."""
    t = re.sub(r'\s+', ' ', etiqueta.strip())
    t = re.sub(r'(?i)^(\d+)\s*(?:o|º|°)\b', r'\1o', t)
    t = re.sub(r'(?i)qu[aá]ter', 'Quáter', t)
    return re.sub(r'(?i)\b(bis|ter|quintus|quinquies|sextus|sexies|septimus|septies|octies|nonies|decies)\b',
                  lambda m: m.group(1).capitalize(), t)


def _numeros(lista: str) -> tuple[list[str], str]:
    """«220 y 224» → (['220', '224'], 'multiple'); «220 a 222» → (['220', '221', '222'], 'rango')."""
    m = re.search(r'(?i)(' + _NUM + r')' + _RANGO + r'(' + _NUM + r')', lista)
    if m and m.group(1).strip().isdigit() and m.group(2).strip().isdigit():
        a, b = int(m.group(1)), int(m.group(2))
        if 0 < b - a < 50:
            return [str(n) for n in range(a, b + 1)], 'rango'
    nums = [normalizar(x) for x in re.findall(r'(?i)' + _NUM, lista)]
    return nums, ('multiple' if len(nums) > 1 else 'directa')


def detectar(texto: str) -> list[dict]:
    """Todas las menciones de otros artículos en el texto de UN artículo, con su clasificación (ver arriba)."""
    texto = _ANOTACION.sub(' ', texto or '')   # antes de quitar los «_» que las delimitan
    texto = re.sub(r'</?(?:mark|u|b|i|strong|em)>|[*_]{1,3}', '', texto)
    texto = re.sub(r'[ \t]+', ' ', texto)
    # El fragmento trae su ruta («Fuente: … / Sección: … > Artículo 224») y su propio encabezado («Artículo 224.-»):
    # no son remisiones a sí mismo.
    texto = '\n'.join(l for l in texto.split('\n') if not re.match(r'\s*(?:Fuente|Secci[oó]n):', l))
    texto = re.sub(r'(?i)^\W*art[íi]culo\s+' + _NUM + r'\s*[.\-–:]+', '', texto.lstrip())
    out = []
    tr = _TRANSITORIOS.search(texto)
    desde_transitorios = tr.start() if tr else len(texto)
    for m in REMISION_RE.finditer(texto):
        nums, tipo = _numeros(m.group(1))
        despues, antes = texto[m.end():m.end() + 140], texto[max(0, m.start() - 80):m.start()]
        oracion, larga = _oracion(texto, m.start(), m.end()), _oracion(texto, m.start(), m.end(), larga=True)
        fr = _FRACCION_ANTES.search(antes) or _FRACCION_DESPUES.search(despues)
        ley = None
        if _DICHO.search(despues) and (ln := _LEY_NOMBRADA.search(texto[max(0, m.start() - 300):m.start()])):
            ambito, ley = 'otra_ley', 'la ley nombrada antes: «' + ln.group(0) + '…»'
        elif _MISMO.search(despues):
            ambito = 'mismo'
        elif (o := _OTRA.search(despues)):
            ambito, ley = 'otra_ley', re.sub(r'\s+', ' ', o.group(1)).strip()
        else:
            ambito = 'mismo_supuesto'
        # Encabezado de OTRO artículo pegado en este fragmento (el separador no lo cortó): «ARTÍCULO 214.- Al que…».
        encabezado = bool(re.match(r'\s*\.?\s*[-–]', texto[m.end():m.end() + 4])) or (
            m.group(0).split()[0].isupper() and len(nums) == 1 and re.match(r'\s*[.:]', texto[m.end():m.end() + 2]))
        rechazo = ('encabezado_pegado' if encabezado else 'transitorio' if m.start() >= desde_transitorios
                   else 'nota_reforma' if _NOTA.search(oracion) or _DECRETO.search(larga) else 'otra_ley' if ambito == 'otra_ley'
                   else 'rango_amplio' if tipo == 'rango' and len(nums) > RANGO_MAX else None)
        materia = 'pena' if _PENA.search(oracion) else 'calificativa' if _CALIF.search(oracion) else 'otra'
        for n in nums:
            out.append({'articulo': n, 'fraccion': fr.group(1) if fr else None, 'ambito': ambito, 'ley': ley,
                        'tipo': tipo, 'materia': materia, 'rechazo': rechazo, 'texto': m.group(0)})
    for m in RELATIVA_RE.finditer(texto):
        oracion, larga = _oracion(texto, m.start(), m.end()), _oracion(texto, m.start(), m.end(), larga=True)
        out.append({'articulo': None, 'relativa': _RELATIVA_NORM.get((m.group(1) or m.group(2)).lower(), 'anterior'), 'fraccion': None, 'ambito': 'mismo', 'ley': None,
                    'tipo': 'relativa', 'materia': 'pena' if _PENA.search(oracion) else 'otra',
                    'rechazo': 'transitorio' if m.start() >= desde_transitorios else
                               'nota_reforma' if _NOTA.search(oracion) or _DECRETO.search(larga) else None, 'texto': m.group(0)})
    return out


def a_seguir(texto: str) -> list[dict]:
    """Solo las remisiones que se seguirían (sin rechazo), sin repetir el mismo artículo."""
    vistos, out = set(), []
    for r in detectar(texto):
        k = (r['articulo'], r.get('relativa'), r['fraccion'])
        if r['rechazo'] is None and k not in vistos:
            vistos.add(k)
            out.append(r)
    return out
