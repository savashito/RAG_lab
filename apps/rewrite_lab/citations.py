"""
apps/rewrite_lab/citations.py — verificación de citas de una respuesta, SIN LLM (benchmark 🧪).

Para cada artículo que cita la respuesta se identifica la ley y se clasifica contra el corpus y contra
el contexto que vio el LLM:

  en_contexto   el artículo llegó al contexto → la cita está respaldada por lo recuperado
  memoria       existe en el corpus pero NO venía en el contexto → el modelo la sacó de lo que ya sabía
                (el prompt pide responder solo con el contexto); puede ser correcta, pero no está fundamentada
  cruzada       no venía con ESA ley, pero el mismo número sí venía con OTRA ley del contexto
                («art. 269 del Código Penal de la CDMX» cuando el 269 del contexto es del Estado de México)
  inexistente   la ley está en el corpus pero ese artículo no → inventado o mal numerado (alucinación)
  sin_ley       no se puede saber de qué ley es (artículo suelto en prosa comparativa): no se clasifica

Además: `otros_estados` = artículos citados de un código ESTATAL que la pregunta no menciona (si la pregunta
menciona al menos un estado). Es la métrica de jurisdicción: «dije CDMX y me citó el Edomex».

Emparejamiento artículo→ley (ver `ley_de`): la ley de la MISMA oración (en tablas, la del encabezado de la columna);
si la oración no la dice, la del encabezado de la sección o del inicio del texto. Ante la duda la cita queda `sin_ley`.
Validado contra una clasificación manual a ciegas de los 31 textos de la corrida 44 (tests/fixtures/citas_run44.json). No verifica que lo que la respuesta
DICE del artículo sea correcto: eso sigue siendo cosa del juez o de la revisión humana.
"""

from __future__ import annotations

import re
from typing import Callable

from shared.code_routes import codes_in

CLASES = ('en_contexto', 'memoria', 'cruzada', 'inexistente', 'sin_ley')
ESTADOS = {'CDMX', 'CPEM', 'Morelos', 'Querétaro'}   # etiquetas de codes_in de los códigos penales estatales

# «art. 179», «arts. 269 y 269 Bis», «artículos 161, 162 y 163», «199 Octies», «211 Quinquies 1»
_SUF = (r'(?:\s*(?:o\b|bis\b|ter\b|qu[aá]ter\b|quintus\b|quinquies\b|sextus\b|sexies\b|septimus\b|septies\b|'
        r'octies\b|nonies\b|decies\b))?(?:\s+\d\b)?')
ART_LIST_RE = re.compile(r'(?i)\bart(?:[íi]culos?|s?\.)\s*(\d+' + _SUF + r'(?:\s*(?:,|\by\b|\ba[l]?\b)\s*\d+' + _SUF + r')*)')
ART_ONE_RE = re.compile(r'(?i)\d+' + _SUF)
_FRAC = (r'(?:,?\s*[*_]*(?:(?:fracci[oó]n|frac\.|fracciones|apartado|inciso|p[aá]rrafo)\s+[\w°º]+(?:\s*(?:,|y)\s*[\w°º]+)*'
         r'(?:\s+(?:primero|segundo|tercero|cuarto|quinto))?|(?:primer|segundo|tercer|cuarto|quinto|[uú]ltimo)o?\s+p[aá]rrafo)[*_]*)*')
# Entre el artículo y la ley que lo sigue: «del/de la …» (quizá tras fracción/párrafo) o una coma («Art. 20, frac. I,
# CNPP»; «Art. 107, Código Penal CDMX»); hasta 90 caracteres del nombre de la ley antes del alias reconocido.
_NO_NOMBRE = r'(?!mientras|en cambio|por su parte|as[ií] como|frente a|\by en\b|\bo en\b)'
_CONECTOR = re.compile(r'(?i)^\.?[\s*_]*' + _FRAC + r'[\s,*_]*(?:(?:del|de la|de los|de)\s(?:' + _NO_NOMBRE + r'[^.;()\n]){0,90}|'
                       r',\s*[*_]*(?:(?:' + _NO_NOMBRE + r'[^.;()\n]){0,45}\s)?|\(\s*[*_]*|\s*[*_]*)$')
# «del citado código», «del Código Penal local»: no se sabe cuál.
_AMBIGUA = re.compile(r'(?i)^\.?[\s*_,]*' + _FRAC + r'[\s,*_]*(?:del|de la|de este|de ese)\s+(?:citad[oa]|mism[oa]|c[oó]digo local|c[oó]digo penal local|ordenamiento|ley local)')
# «Artículo 12 de *Lecciones de Derecho Penal*»: «de …» que no es una ley del corpus.
_DE_ALGO = re.compile(r'(?i)^\.?[\s*_,]*' + _FRAC + r'[\s,*_]*(?:del|de la|de los|de)\s+[*_]*(?-i:[A-ZÁÉÍÓÚ])')
_OTRA_LEY = re.compile(r'(?i)\b(?:del|de la|de los)\s+[*_]*(?:c[oó]digo|ley|constituci[oó]n|reglamento)\b')
_FIN_ORACION = re.compile(r'(?<!\bart)(?<!\barts)(?<!\bfrac)(?<!\bNo)[.;]\**\s+(?=[*_¿(]*[A-ZÁÉÍÓÚ])')
# «Al igual que en la CDMX, el Artículo 201…»: esa ley es la de la comparación, no la del artículo.
_COMPARA = re.compile(r'(?i)(al igual que|a diferencia de|igual que|como en|similar(?:es)? a(?: l[ao]s?)?(?: de)?|'
                      r'(?:distint|diferente|parecid)[oa]s? (?:a|de)(?: l[ao]s?)?(?: de)?|(?:mayor|menor|m[aá]s|menos)(?:es)?(?:\s+[a-záéíóúñ]+){0,2}\s+que)\W+(?:en\s+)?(?:(?:la|el|los|las)(?:\s+(?:legislaci[oó]n|ley|c[oó]digo|regulaci[oó]n|norma|normatividad))?(?:\s+del?)?(?:\s+la)?)?\s*$')
_DEROGADO = re.compile(r'(?i)^\W*(se deroga|derogad[oa])\b')


# Los alias de codes_in son cortos («morelos», «distrito federal», «procedimientos penales») y aparecen dentro del
# nombre de OTRAS leyes: «Código Civil para el Distrito Federal», «Código Procesal Familiar de Morelos», «Código
# Federal de Procedimientos Penales» (abrogado), «Constitución Política del Estado de Morelos». Si el nombre completo
# (desde «Código/Ley/Constitución…» hasta el alias) es de ese tipo, no es la ley penal del alias.
_PENALES = {'CDMX', 'CPEM', 'CPF', 'CNPP', 'Morelos', 'Querétaro'}
_CABEZA = re.compile(r'(?i)\b(c[oó]digo|ley|constituci[oó]n|reglamento|acuerdo)\b')
_OTRA_MATERIA = re.compile(r'(?i)civil|procesal|familiar|constituci|armas|amparo|v[ií]ctimas|electoral|trabajo|laboral|'
                           r'fiscal|salud|ambient|federal de procedimientos|tr[aá]nsito|municipal|prevenci|erradicaci|'
                           r'violencia familiar|acceso de las mujeres')
# «las dependencias del Gobierno del Estado de México», «la Fiscalía General del Estado de Querétaro»: el alias nombra
# una institución del estado, no su código penal.
_INSTITUCION = re.compile(r'(?i)\b(gobierno|fiscal[ií]a(?: general)?|poder judicial|congreso|secretar[ií]a[^,.;\n]{0,40}|'
                          r'tribunal(?: superior)?(?: de justicia)?|ayuntamiento|defensor[ií]a(?: p[uú]blica)?)\s+(?:del?|de la)\s*$')


def _leyes(t: str) -> list[dict]:
    """codes_in(t) sin los falsos positivos de alias dentro del nombre de otra ley."""
    out = []
    for h in codes_in(t):
        if h['label'] in _PENALES:
            cabezas = list(_CABEZA.finditer(t, max(0, h['start'] - 80), h['start'] + 1))
            nombre = t[cabezas[-1].start():h['start'] + len(h['match'])] if cabezas else h['match']
            if _OTRA_MATERIA.search(nombre) or (not cabezas and _INSTITUCION.search(t[max(0, h['start'] - 60):h['start']])):
                continue
            if (h['label'] == 'CNPP' and h['match'].lower().startswith('procedimientos')
                    and not re.search(r'(?i)c[oó]digo\s+nacional\s+de\s*[*_]*$', t[max(0, h['start'] - 30):h['start']])):
                continue   # «procedimientos penales» como frase genérica, no el Código Nacional
        out.append(h)
    return out


def _ultima(t: str, excluir_comparaciones: bool = False):
    """La ley mencionada MÁS CERCA del final de `t` (codes_in devuelve cada ley una sola vez, en su primera
    aparición, así que se busca la última aparición de cada una). Con `excluir_comparaciones`, no cuenta una
    mención precedida de «al igual que en…», «a diferencia de…»."""
    mejor, mejor_pos = None, -1
    for h in _leyes(t):
        pos = t.rfind(h['match'])
        while pos >= 0 and excluir_comparaciones and _COMPARA.search(t[max(0, pos - 60):pos]):
            pos = t.rfind(h['match'], 0, pos)
        if pos > mejor_pos:
            mejor, mejor_pos = h, pos
    return mejor


def _leyes_reales(t: str) -> list[dict]:
    """_leyes(t) sin las que solo aparecen como comparación («Al igual que en la CDMX…»)."""
    out = []
    for h in _leyes(t):
        pos = t.rfind(h['match'])
        while pos >= 0 and _COMPARA.search(t[max(0, pos - 60):pos]):
            pos = t.rfind(h['match'], 0, pos)
        if pos >= 0:
            out.append(h)
    return out


def _norm_art(a: str) -> str:
    return re.sub(r'\W+', ' ', a or '').strip().lower()


def _ley_en_tabla(texto: str, ini_l: int, pos: int):
    """Tabla «| Concepto | Ciudad de México | Querétaro |»: la ley de una celda es la del encabezado de su
    columna; si el encabezado no nombra una ley, la de la propia celda; si no, None."""
    lineas = texto[:ini_l].split('\n')
    k = len(lineas) - 2
    while k >= 0 and lineas[k].lstrip().startswith('|'):
        k -= 1
    fin = texto.find('\n', ini_l)
    encabezado = lineas[k + 1] if k + 1 < len(lineas) - 1 else texto[ini_l:fin if fin >= 0 else len(texto)]
    col = texto[ini_l:pos].count('|') - 1
    celdas = encabezado.strip().strip('|').split('|')
    if 0 <= col < len(celdas):
        h = _leyes(celdas[col])
        if h:
            return h[0]
    fin_c = texto.find('|', pos)
    h = _leyes(texto[texto.rfind('|', 0, pos) + 1:fin_c if fin_c > 0 else len(texto)])
    return h[0] if h else None


_VINETA = re.compile(r'^\s*(?:[*-]|\d+\.)\s')
# Nombre de una ley (con mayúscula): «Ley General de Acceso…», «Código Civil…»; no la palabra genérica «la ley».
_MISMO = re.compile(r'(?i)^[\s*_,]*' + _FRAC + r'[\s,*_]*(?:(?:del|de ese|de este)\s+(?:mismo|citado)\s+(?:c[oó]digo|ordenamiento)|'
                    r'de\s+(?:este|dicho|ese)\s+(?:c[oó]digo|ordenamiento))')
_LOCAL = re.compile(r'(?i)^[\s*_,]*' + _FRAC + r'[\s,*_]*del\s+c[oó]digo\s+penal\s+(?:local|correspondiente|estatal|'
                    r'de\s+(?:esa|dicha|esta)\s+entidad|de\s+(?:ese|dicho|este)\s+estado)')
_ESTE_CODIGO = re.compile(r'(?i)\b(?:este|dicho|ese)\s+(?:c[oó]digo|ordenamiento)\b[^.\n]*\b(?:su|el|los)\s+[*_]*$')
# «Código Penal local / correspondiente / estatal / de dicho estado»: referencia al estado ya nombrado, no otra ley.
_REFERENCIA = re.compile(r'(?i)c[oó]digo\s+penal\s+(?:local|correspondiente|estatal|de\s+(?:dicho|ese|este|esa|dicha|esta)\s+(?:estado|entidad))')
_TIPO_LEY = re.compile(r'\b(?:Ley|LEY|C[oó]digo|CÓDIGO|Constituci[oó]n|Reglamento)\s+(?:General|Federal|Nacional|Org[aá]nica|'
                       r'Civil|Penal|Procesal|Pol[ií]tica|para|de|del|contra|sobre)\b')


def _ley_por_encabezado(texto: str, pos: int):
    """Ley del texto que «encabeza» al artículo, si la oración no la dice: subiendo línea por línea, el primer título
    markdown («### En Querétaro»), línea en negritas o línea de la que cuelga la lista («**Código Penal del Estado de
    México**:») que nombre exactamente UNA ley del corpus; si no hay, la única ley que nombre el inicio del texto
    («Basado en el **Código Penal de la Ciudad de México**…»). Si el encabezado nombra una ley que NO está en el
    corpus («Según la Ley para la Prevención… del Estado de México:») o varias, se detiene: None."""
    lineas = texto[:pos].split('\n')
    actual = lineas[-1]
    sangria = len(actual) - len(actual.lstrip())
    primera = True
    for ln in reversed(lineas[:-1]):
        s = ln.strip()
        if not s:
            continue
        inmediata, primera = primera, False
        es_titulo = (s.startswith('#') or (s.startswith('**') and s.rstrip(':').endswith('**'))
                     or re.match(r'^[*-]\s+\*\*[^*]+\*\*\s*:?\s*$', s))
        # Línea de la que cuelga la lista: termina en «:» y el artículo está más sangrado, o está en una viñeta
        # justo debajo de un párrafo que no es viñeta («Según la Ley …:» + «*   … (Art. 17)»).
        es_padre = s.endswith(':') and ((len(ln) - len(ln.lstrip())) < sangria or inmediata
                                         or (_VINETA.match(actual) and not _VINETA.match(ln)))
        if es_titulo or es_padre:
            leyes = _leyes_reales(s)
            if len({h['source'] for h in leyes}) == 1:
                return leyes[0]
            if leyes or _TIPO_LEY.search(s):
                return None
    # Sin encabezado con ley: el párrafo anterior más cercano de la misma sección (desde el último título «#») que
    # nombre leyes, si nombra UNA sola, sin contar comparaciones («En primer lugar, el artículo 159 del Código Penal
    # del Estado de Querétaro…» → «En segundo lugar, el artículo 159 BIS…»); si nombra varias, no se adivina. Si no
    # hay, la única ley del inicio del texto.
    ini_s = max((mm.start() for mm in re.finditer(r'(?m)^\s*#', texto[:pos])), default=0)
    for par in reversed(re.split(r'\n\s*\n', texto[ini_s:pos])[:-1]):   # párrafos anteriores de la sección
        leyes = _leyes_reales(par)
        if leyes:
            return leyes[0] if len({h['source'] for h in leyes}) == 1 else None
    leyes = _leyes(texto[:700])
    return leyes[0] if len({h['source'] for h in leyes}) == 1 else None


def _senal_de_otra_ley(texto: str, m: re.Match) -> bool:
    """La oración del artículo dice que es de otra ley o de una referencia que no se puede resolver («del citado
    código», «de la misma Ley», «del Código Civil…», «Ley General de Acceso… (Artículo 13)»): no se sube al encabezado."""
    fin = texto.find('\n', m.end())
    tramo = texto[m.end():fin if fin > 0 else len(texto)][:200]
    antes = texto[texto.rfind('\n', 0, m.start()) + 1:m.start()]
    return bool(_AMBIGUA.match(tramo) or _OTRA_LEY.search(tramo[:80])
                or (_DE_ALGO.match(tramo) and not _leyes(tramo[:90]))
                or _ultimo_nombre_es_otra_ley(antes))


def _ultimo_nombre_es_otra_ley(antes: str) -> bool:
    """«…el CNPCF y el Código Civil para el Distrito Federal (Artículo 282 Bis)»: el último nombre de ley antes del
    artículo (en la misma línea) es una ley que no está en el corpus."""
    nombres = [x for x in re.finditer(_TIPO_LEY.pattern + r'[^.\n]{0,120}$', antes) if not _REFERENCIA.match(x.group(0))]
    if not nombres:
        return False
    pos_nombre = nombres[0].start()
    h = _ultima(antes)
    return h is None or antes.rfind(h['match']) < pos_nombre


def ley_de(texto: str, m: re.Match):
    """Ley de la cita `m` (un match de ART_LIST_RE), o None si no se puede saber: la de su oración (ver
    `_ley_en_oracion`); si la oración no la dice y no indica que es otra ley, la del encabezado (`_ley_por_encabezado`)."""
    tramo = texto[m.end():m.end() + 60]
    ini_l = texto.rfind('\n', 0, m.start()) + 1
    oracion = texto[ini_l:m.start()]
    cortes = [x.end() for x in _FIN_ORACION.finditer(oracion)]
    oracion = oracion[cortes[-1]:] if cortes else oracion
    ini_p = max(texto.rfind('\n\n', 0, m.start()), 0)
    parrafo = texto[ini_p:m.start()]
    if re.search(r'(?i)\bsu\s+[*_]*$', oracion):   # «…contempla… en su artículo 130»: la ley ya nombrada antes
        return _ultima(oracion, True) or _ultima(parrafo, True)
    if not _LOCAL.match(tramo) and not _MISMO.match(tramo):
        ley = _ley_en_oracion(texto, m)
        if ley:
            return ley
    if _LOCAL.match(tramo):   # «del Código Penal local / correspondiente / de dicho estado»: el estado de la oración
        return _ultima(oracion, True) or _ultima(parrafo, True)
    # «del mismo ordenamiento», «del citado código», «de este código», «este código contempla… en su artículo 131»: la
    # última ley nombrada antes (primero en el párrafo, si no en todo el texto).
    if _MISMO.match(tramo) or _ESTE_CODIGO.search(oracion):
        return _ultima(parrafo, True) or _ultima(texto[:m.start()], True)
    if _senal_de_otra_ley(texto, m):
        return None
    # La oración no dice la ley: la última nombrada antes en el MISMO párrafo («…tipificada en el Código Penal del
    # Estado de Querétaro. El artículo 199…»), sin contar comparaciones; si no hay, la del encabezado.
    return _ultima(parrafo, True) or _ley_por_encabezado(texto, m.start())


def _ley_en_oracion(texto: str, m: re.Match):
    """(1) la ley nombrada justo después en la misma oración («art. 179 del Código Penal de la CDMX»);
    (2) la última nombrada antes en la misma oración («**Código Penal de Querétaro:** Artículos 167 Bis y 167 Ter»),
        salvo que sea la de una comparación; (3) la primera después en la misma oración; en tablas, la de la columna."""
    ini_l = texto.rfind('\n', 0, m.start()) + 1
    fin_l = texto.find('\n', m.end())
    fin_l = len(texto) if fin_l < 0 else fin_l
    if texto[ini_l:fin_l].lstrip().startswith('|'):
        return _ley_en_tabla(texto, ini_l, m.start())
    tramo = texto[m.end():min(fin_l, m.end() + 200)]
    if _AMBIGUA.match(tramo):
        return None
    despues = _leyes(tramo)
    if despues and _CONECTOR.match(tramo[:despues[0]['start']]):
        return despues[0]
    if _DE_ALGO.match(tramo) and not _leyes(tramo[:90]):
        return None
    # «artículo 4o. de la Constitución…», «arts. 83 Bis, 84 (…) de la Ley Federal de Armas»: la oración nombra
    # enseguida una ley que no es del corpus → no se le atribuye la ley de antes.
    if _OTRA_LEY.search(tramo[:80]) and not _leyes(tramo[:120]):
        return None
    antes_txt = texto[ini_l:m.start()]
    cortes = [x.end() for x in _FIN_ORACION.finditer(antes_txt)]   # en prosa una «línea» es un párrafo entero
    if cortes:
        antes_txt = antes_txt[cortes[-1]:]
    h = _ultima(antes_txt)
    if h:
        pos = antes_txt.rfind(h['match'])
        entre = antes_txt[pos + len(h['match']):]
        if _COMPARA.search(antes_txt[max(0, pos - 60):pos]) or _TIPO_LEY.search(entre):
            return None
        # 2. «…en su artículo 130»: «su» es la ley ya nombrada en la oración (no la que viene después)
        return h
    if despues and not _FIN_ORACION.search(tramo[:despues[0]['start']]):
        return None if _COMPARA.search(tramo[:despues[0]['start']]) else despues[0]
    return None


def extract(texto: str) -> list[dict]:
    """Citas de una respuesta, sin repetir: [{'source', 'label', 'article', 'snippet'}] (source None = sin ley)."""
    out, seen = [], set()
    texto = texto or ''
    for m in ART_LIST_RE.finditer(texto):
        ley = ley_de(texto, m)
        for a in ART_ONE_RE.findall(m.group(1)):
            a = re.sub(r'\s+', ' ', a.strip())
            key = ((ley or {}).get('source'), _norm_art(a))
            if key in seen:
                continue
            seen.add(key)
            out.append({'source': (ley or {}).get('source'), 'label': (ley or {}).get('label'), 'article': a,
                        'snippet': texto[max(0, m.start() - 60):m.end() + 90].replace('\n', ' ')})
    # Una mención suelta de un artículo que la misma respuesta ya citó con su ley no es otra cita.
    con_ley = {_norm_art(c['article']) for c in out if c['source']}
    return [c for c in out if c['source'] or _norm_art(c['article']) not in con_ley]


def article_of(hierarchy: str) -> str | None:
    """«… > Artículo 167 QUINQUIES» → «167 quinquies»."""
    m = re.search(r'(?i)art[íi]culo\s+(.+?)\s*$', (hierarchy or '').split(' > ')[-1])
    return _norm_art(m.group(1)) if m else None


def classify(question: str, answer: str, chunks: list[dict], resolve: Callable[[str, str], tuple[list[int], bool]],
             corpus_sources: set[str] | None = None) -> dict:
    """Clasifica las citas de `answer`. `chunks` = contexto que vio el LLM ([{id, source, hierarchy}]);
    `resolve(source, article)` → (ids de los chunks de ese artículo en el corpus, ¿derogado?).
    `corpus_sources` (opcional): documentos del corpus; una ley fuera de él queda `sin_ley`."""
    ctx_ids = {ch.get('id') for ch in chunks or [] if ch.get('id') is not None}
    arts_ctx: dict[str, set] = {}   # número de artículo → leyes con ese artículo en el contexto
    for ch in chunks or []:
        a = article_of(ch.get('hierarchy'))
        if a:
            arts_ctx.setdefault(a, set()).add(ch.get('source'))
    items = []
    for c in extract(answer):
        it = {'label': c['label'], 'article': c['article'], 'snippet': c['snippet']}
        src = c['source']
        if src is None or (corpus_sources is not None and src not in corpus_sources):
            it['clase'] = 'sin_ley'
        else:
            ids, derogado = resolve(src, c['article'])
            if derogado:
                it['derogado'] = True
            # Por id del chunk o por (ley, artículo) de su jerarquía: los ids cambian al reingestar un documento,
            # y las corridas viejas guardan los ids de entonces.
            if ctx_ids & set(ids) or src in arts_ctx.get(_norm_art(c['article']), ()):
                it['clase'] = 'en_contexto'
            elif arts_ctx.get(_norm_art(c['article']), set()) - {src}:
                it['clase'] = 'cruzada'
            else:
                it['clase'] = 'memoria' if ids else 'inexistente'
        items.append(it)
    q_estados = sorted({h['label'] for h in codes_in(question or '') if h['label'] in ESTADOS})
    otros = sorted({f"{it['label']} {it['article']}" for it in items
                    if it['clase'] != 'sin_ley' and it['label'] in ESTADOS and it['label'] not in q_estados})
    counts = {k: sum(it['clase'] == k for it in items) for k in CLASES}
    return {'items': items, 'counts': counts, 'question_states': q_estados,
            'other_states': otros if q_estados else None,   # None = la pregunta no menciona estados: no aplica
            'derogated': sum(bool(it.get('derogado')) for it in items)}


_JUEZ_OTRO_ESTADO = re.compile(r'(?i)otra entidad|otro estado|otra jurisdicci')


def judge_other_state(verdicts: list[dict]) -> bool | None:
    """Veredicto del juez sobre un must_not de jurisdicción («presenta como aplicable … de otra entidad»), si
    la pregunta tiene uno: True = el juez dice que la respuesta cita otro estado. None = no hay ese criterio."""
    vs = [v for v in verdicts or [] if v.get('kind') == 'must_not' and _JUEZ_OTRO_ESTADO.search(v.get('text') or '')]
    return any(v.get('verdict') == 'presente' for v in vs) if vs else None


def aggregate(rows: list[dict]) -> dict:
    """Métricas de la corrida a partir de rows con 'citations' (y 'verdicts'). Vacío si ninguna fila las tiene."""
    rs = [r for r in rows if not r.get('error') and r.get('citations')]
    if not rs:
        return {}
    tot = {k: sum((r['citations'].get('counts') or {}).get(k, 0) for r in rs) for k in CLASES}
    n_cls = sum(tot[k] for k in CLASES if k != 'sin_ley')
    frac = (lambda k: round(tot[k] / n_cls, 4)) if n_cls else (lambda k: None)
    aplica = [r for r in rs if r['citations'].get('other_states') is not None]
    out = {'cit_n': n_cls, 'cit_unknown': tot['sin_ley'], 'cit_context': frac('en_contexto'),
           'cit_memory': frac('memoria'), 'cit_cross': frac('cruzada'), 'cit_missing': tot['inexistente'],
           'cit_answers': len(rs),
           'cit_answers_missing': sum(r['citations']['counts'].get('inexistente', 0) > 0 for r in rs),
           'cit_answers_ungrounded': sum(r['citations']['counts'].get('memoria', 0) + r['citations']['counts'].get('cruzada', 0) > 0 for r in rs),
           'cit_derogated': sum(r['citations'].get('derogated', 0) for r in rs)}
    if aplica:
        con = [bool(r['citations']['other_states']) for r in aplica]
        out.update(other_state_n=len(aplica), other_state_rate=round(sum(con) / len(aplica), 4))
        par = [(bool(r['citations']['other_states']), judge_other_state(r.get('verdicts'))) for r in aplica]
        par = [(a, j) for a, j in par if j is not None]
        if par:
            out.update(other_state_judge_n=len(par), other_state_judge_rate=round(sum(j for _, j in par) / len(par), 4),
                       other_state_agreement=round(sum(a == j for a, j in par) / len(par), 4))
    return out


class Resolver:
    """resolve(source, article) contra la tabla del corpus, con caché por corrida (un SELECT por documento)."""

    def __init__(self, cur, table: str):
        self.cur, self.table, self._docs, self._memo = cur, table, {}, {}
        cur.execute(f"SELECT DISTINCT source FROM {table}")
        self.sources = {r[0] for r in cur.fetchall()}

    def __call__(self, source: str, article: str) -> tuple[list[int], bool]:
        key = (source, _norm_art(article))
        if key in self._memo:
            return self._memo[key]
        if source not in self._docs:
            self.cur.execute(f"SELECT id, hierarchy, text FROM {self.table} WHERE source = %s", (source,))
            self._docs[source] = self.cur.fetchall()
        rows = self._docs[source]
        # Misma búsqueda que bench.resolve_gold: por jerarquía («> Artículo 179») y, si el documento no está
        # partido por artículo (p. ej. Morelos), donde el artículo EMPIEZA y, si no, cualquier mención.
        toks = article.split()
        rx = re.compile(r'(?i)> art[íi]culo\s+' + r'\s*'.join(map(re.escape, toks)) + r'[oº°]?\.?$')
        hits = [(i, t) for i, h, t in rows if rx.search(h or '')]
        if not hits:
            num = re.escape(toks[0])
            start = re.compile(r'(?im)^[\s#>*_]*art[íi]c?u?lo\s*\**\s*' + num + r'(?![0-9])')
            hits = [(i, t) for i, _, t in rows if start.search(t or '')]
            if not hits:
                trx = re.compile(r'(?i)art[íi]culo\W{0,4}' + num + r'(?![0-9])')
                hits = [(i, t) for i, _, t in rows if trx.search(t or '')]
        derogado = False
        if hits and len(hits) <= 3:
            cuerpo = re.sub(r'(?is)^.*?\*\*\s*art[íi]culo[^*]*\*\*', '', ' '.join(t or '' for _, t in hits), count=1)
            derogado = bool(_DEROGADO.match(cuerpo.strip(' *_.-–—:()\n')[:40]))
        self._memo[key] = ([i for i, _ in hits], derogado)
        return self._memo[key]
