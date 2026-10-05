"""
shared/legal_chunking.py — chunking por estructura para el corpus jurídico.

Extraído del notebook `exploracion_datos/exploracion_chunking_corpus.ipynb` una vez
validado (limpieza + clasificación + fusión + partición, con pruebas y guardas de
regresión). Vive aquí para que el notebook de exploración, el de recuperación y —a
futuro— la ingestión importen EXACTAMENTE la misma lógica, sin duplicarla.

Pipeline:
    raw markdown ──clean_document──▶ texto limpio
                 ──document_strategy──▶ 'article' | 'heading' | 'paragraph'
                 ──semantic_units──▶ unidades (artículo / bloque de encabezado)
                 ──merge_small_siblings──▶ sin fragmentos huérfanos
                 ──make_chunks──▶ chunks (parte los > MAX_WORDS por párrafos)

Las pruebas viven en `tests/test_legal_chunking.py` (pytest).
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from pathlib import Path

import pandas as pd

# ── Presupuesto de tamaño (palabras) ────────────────────────────────────────────
TARGET_WORDS = 500
MAX_WORDS = 800
MIN_WORDS = 80
OVERLAP_WORDS = 80

# ── Limpieza conservadora ────────────────────────────────────────────────────────
PAGE_RE = re.compile(r'^(?:\d+|[IVXLCDM]+|\d+\s+de\s+\d+|\d+\s*/\s*\d+)$', re.I)  # 12 · XII · 12 de 15 · 12/15
INSTITUTIONAL_RE = re.compile(
    r'(CÁMARA DE DIPUTADOS DEL H\. CONGRESO|SECRETAR[IÍ]A GENERAL|SECRETAR[IÍ]A DE SERVICIOS PARLAMENTARIOS)',
    re.I,
)
EDITORIAL_RE = re.compile(
    r'^DR\s*[©@]|^ISBN\b|^DOI\s*:|^https?://doi\.org|^Primera edici[oó]n:|^Impreso y hecho en|Prohibida la reproducci[oó]n|Esta obra forma parte del acervo|Libro completo en:|Biblioteca Jur[ií]dica Virtual|Todos los derechos reservados',
    re.I,
)
CATALOG_RECORD_RE = re.compile(r'catalogaci[oó]n en la publicaci[oó]n', re.I)
CATALOG_RECORD_END_RE = re.compile(r'^esta edici[oó]n', re.I)
CONTENTS_HEADING_RE = re.compile(r'^#{1,6}\s+(?:\*\*)?(?:contenido|[ií]ndice|table of contents)(?:\*\*)?\s*$', re.I)
PICTURE_TEXT_MARKER_RE = re.compile(r'<!--\s*(?:Start|End) of picture text\s*-->', re.I)
# Encabezado cuyo texto es sólo un número o romano: es el folio de página que el
# conversor dejó con formato de título (sobrevive a PAGE_RE porque conserva los '#').
HEADING_PAGE_RE = re.compile(r'^#{1,6}[ \t]+(?:\d+|[ivxlcdm]+)[ \t]*$', re.I)

REMOVAL_REASONS = [
    'catalog_record', 'contents_table', 'repeated_heading', 'heading_page_marker',
    'editorial_watermark', 'page_number', 'institutional_header', 'repeated_block',
]
# Encabezado/pie de página en TEXTO normal (no '#'): el PDF reimprime en cada hoja un bloque
# de varias líneas —p. ej. Morelos: "Código Penal para el Estado de Morelos" / "Consejería
# Jurídica del Poder Ejecutivo…" / "Última Reforma: 02-09-2026" / "Aprobación … Vigencia …"—.
# Una línea se descarta si (a) se repite idéntica ≥ BLOCK_MIN_REPEATS veces en el documento,
# (b) es corta (3–40 palabras, no tabla, no inicio de artículo) y (c) su vecina no vacía de
# arriba o de abajo también cumple (a)+(b). La condición (c) es la que protege al texto legal
# que se repite suelto ("Este delito se perseguirá por querella."): el mobiliario de página
# viene en BLOQUE, una frase de ley repetida no.
BLOCK_MIN_REPEATS = 5
# Nunca es mobiliario lo que EMPIEZA como texto jurídico, aunque se repita en bloque: los
# transitorios de cada decreto ("SEGUNDA. El presente Decreto entrará en vigor…", "Artículo
# Primero. La presente Ley…"), la estructura ("Capítulo Único Disposiciones Generales") y las
# notas de reforma ("Artículo reformado DOF…", "REFORMA VIGENTE.-"). Medido en el corpus: sin
# esta exclusión la regla de bloques borraba transitorios de Morelos/Querétaro y capítulos del CNPCF.
_LEGAL_START_RE = re.compile(
    r'(?i)^(?:art[íi]?c?u?lo\b|libro\b|subt[íi]tulo\b|t[íi]tulo\b|cap[íi]tulo\b|secci[óo]n\b|'
    r'(?:primer|segund|tercer|cuart|quint|sext|s[ée]ptim|octav|noven|d[ée]cim|und[ée]cim|duod[ée]cim|[úu]nic)\w*\b|'
    r'reforma\b|nota\b|notas\b|fe de erratas\b|transitori)')


def normalize_line(line: str) -> str:
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>|[*_]', '', line)).strip()


# Reglas de una sola línea: la primera coincidencia define la razón de descarte.
LINE_NOISE_PATTERNS = {
    'page_number': PAGE_RE,
    'institutional_header': INSTITUTIONAL_RE,
    'editorial_watermark': EDITORIAL_RE,
}
# Tope de palabras para que una línea cuente como ruido. El mobiliario de página es
# corto (el encabezado de Diputados tiene 15 palabras; la marca de agua de la BJV más
# larga, 35), pero un conversor puede entregar un párrafo entero como UNA línea, y el
# cuerpo también menciona "la Secretaría General de la OEA / de Gobierno / del Consejo".
# Sin tope, una sola mención borraba el párrafo completo (medido: desde 19 palabras
# hasta páginas enteras de un acuerdo OCReado).
NOISE_MAX_WORDS = {'institutional_header': 16, 'editorial_watermark': 40}
# Encabezado de Diputados PEGADO al inicio de un párrafo largo (pasa cuando el conversor
# une el corredor de página con el cuerpo): se recorta el encabezado y el resto se queda.
DIPUTADOS_HEADER_PREFIX_RE = re.compile(
    r'^C[ÁA]MARA DE DIPUTADOS DEL H\. CONGRESO DE LA UNI[ÓO]N\s+'
    r'(?:[ÚU]ltima Reforma DOF [\d-]+\s+)?'
    r'Secretar[ií]a General\s+Secretar[ií]a de Servicios Parlamentarios\s*'
    r'(?:[ÚU]ltima Reforma DOF [\d-]+\s*)?',
    re.I,
)


def line_noise_reason(plain: str) -> str | None:
    n_words = len(plain.split())
    for reason, pattern in LINE_NOISE_PATTERNS.items():
        if n_words <= NOISE_MAX_WORDS.get(reason, n_words) and pattern.search(plain):
            return reason
    return None


def _furniture_key(line: str) -> str:
    return re.sub(r'^#+\s*', '', normalize_line(line))


def _repeated_block_lines(lines: list[str], min_repeats: int = BLOCK_MIN_REPEATS) -> set[int]:
    """Índices de líneas que forman bloques repetidos de encabezado/pie de página."""
    keys = [_furniture_key(ln) for ln in lines]
    freq = Counter(k for k in keys if k)

    def candidate(i: int) -> bool:
        k = keys[i]
        return (bool(k) and freq[k] >= min_repeats and 3 <= len(k.split()) <= 40
                and not lines[i].lstrip().startswith('|') and not ARTICLE_RE.match(lines[i])
                and not _LEGAL_START_RE.match(k))

    nonblank = [i for i, k in enumerate(keys) if k]
    cand = {i for i in nonblank if candidate(i)}
    out = set()
    for j, i in enumerate(nonblank):
        if i not in cand:
            continue
        prev_i = nonblank[j - 1] if j else None
        next_i = nonblank[j + 1] if j + 1 < len(nonblank) else None
        if (prev_i in cand) or (next_i in cand):
            out.add(i)
    return out


def clean_document(text: str, min_heading_repeats: int = 6) -> dict:
    """Elimina paratextos editoriales, no contenido jurídico ni bibliografía académica."""
    # Los marcadores del conversor delimitan OCR de imágenes; no son parte del texto.
    text = PICTURE_TEXT_MARKER_RE.sub('', text)
    lines = text.splitlines()
    # Pre-pase: cuenta encabezados idénticos. El mobiliario de página (título del
    # libro, nombre del autor) se reimprime como encabezado en cada hoja, así que
    # se repite muchas veces —muy por encima de cualquier sección legítima—.
    heading_freq = Counter(
        normalize_line(line) for line in lines if line.lstrip().startswith('#')
    )
    furniture = _repeated_block_lines(lines)
    kept, removed = [], []
    removed_by_reason: Counter = Counter()
    in_catalog_record = False
    in_contents_table = False

    def discard(line: str, reason: str) -> None:
        removed.append(line)
        removed_by_reason[reason] += 1

    for idx, line in enumerate(lines):
        plain = normalize_line(line)
        if idx in furniture:
            discard(line, 'repeated_block')
            continue
        # La ficha va desde ‘Catalogación en la publicación’ hasta ‘Esta edición’.
        if in_catalog_record:
            discard(line, 'catalog_record')
            if CATALOG_RECORD_END_RE.match(plain):
                in_catalog_record = False
            continue
        if CATALOG_RECORD_RE.search(plain):
            in_catalog_record = True
            discard(line, 'catalog_record')
            continue
        if CONTENTS_HEADING_RE.match(line.strip()):
            in_contents_table = True
            discard(line, 'contents_table')
            continue
        if in_contents_table:
            if not plain or line.lstrip().startswith('|'):
                discard(line, 'contents_table')
                continue
            in_contents_table = False
        # Mobiliario de página con forma de encabezado: folios sueltos y
        # títulos-corredor repetidos. Sólo se aplica a encabezados, de modo que
        # nunca borra una línea de cuerpo aunque coincida por casualidad.
        if line.lstrip().startswith('#'):
            if HEADING_PAGE_RE.match(line.strip()):
                discard(line, 'heading_page_marker')
                continue
            if plain and heading_freq[plain] >= min_heading_repeats:
                discard(line, 'repeated_heading')
                continue
        noise_reason = line_noise_reason(plain)
        if noise_reason:
            discard(line, noise_reason)
            continue
        header = DIPUTADOS_HEADER_PREFIX_RE.match(plain)
        if header:
            removed_by_reason['institutional_header'] += 1
            removed.append(header.group(0))
            line = plain[header.end():]
        kept.append(line)
    text = '\n'.join(kept)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return {
        'clean_text': text.strip(),
        'removed_by_reason': dict(removed_by_reason),
    }


# ── Clasificación estructural ────────────────────────────────────────────────────
HEADING_RE = re.compile(r'(?m)^(#{1,6})[ \t]+(.+?)[ \t]*$')
# Inicio de artículo al principio de la línea, tolerando el markup que dejó el
# conversor PDF→MD (#, **, _, >, <u>). Los códigos rara vez marcan el artículo como
# encabezado Markdown: casi siempre es negrita en línea (**Artículo 1o** .-). Exigir
# un DÍGITO tras "Artículo" descarta las referencias en prosa ("del artículo Cuarto
# Transitorio") y las notas de reforma ("Artículo reformado DOF 1999"), que no lo
# llevan. Se captura la ETIQUETA completa (número + ordinal + sufijos) para el título.
#
# Los códigos mexicanos numeran las adiciones de tres formas, a veces mezcladas en el
# mismo código: (a) adverbios latinos —bis, ter, quáter, quinquies… decies…—; (b)
# ordinales latinos —quintus, sextus, septimus…—; (c) sufijo con guion —215-A, 246-D—.
# Un artículo "246-A" es una norma DISTINTA del "246"; si no se captura el sufijo, todos
# colapsan al mismo número y el tagueo/recuperación se confunde. `_ARTICLE_SUFFIX` lista
# los latinos; el guion+letra/número cubre (c). Cada token exige separador propio para no
# tragarse palabras del cuerpo ("Artículo 5 bis Del homicidio" → etiqueta "5 bis").
# 'quarter' es errata de 'quáter' en el Código Penal de Morelos ("ARTÍCULO *148 quarter").
_ARTICLE_LATIN = (
    r'bis|ter|qu[aá]ter|quarter|quinquies|quintus|sexies|sextus|septies|septimus|octies|octavus|'
    r'nonies|nonus|decies|decimus|undecies|duodecies|terdecies|quaterdecies|quindecies|'
    r'sexdecies|septendecies|octodecies|novodecies|vicies'
)
# Subíndice OPCIONAL tras un latino: número ("211 bis 1", "127 bis-1"), palabra española
# ("150 BIS UNO") o una sola letra ("221 bis-A"). Separado por espacio, punto o guion.
_ARTICLE_SUBINDEX = (
    # Separador SIN punto: en "148 bis.- A la persona…" la "A" es texto, no subíndice.
    r'(?:(?:[ \t]*-[ \t]*|[ \t]+)(?:\d+|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|'
    r'[A-Za-z](?![A-Za-z])))?'
)
# El TOKEN-NÚMERO tolera letras que el OCR confunde con dígitos cuando van PEGADAS a
# dígitos (sin separador): I l | → 1, O → 0, S → 5, Z → 2. Así "22I" (mala lectura de
# "221") se captura entero y se corrige en `_article_label`. Se exige ≥1 dígito real y se
# desactiva ignorecase con (?-i:…) para NO tragarse la "o" ordinal ("1o") ni minúsculas.
_ARTICLE_NUM = r'(?-i:[\dIl|OSZ]*\d[\dIl|OSZ]*)'
_OCR_TO_DIGIT = str.maketrans({'I': '1', 'l': '1', '|': '1', 'O': '0', 'S': '5', 'Z': '2'})
# Etiqueta = número + ordinal + cadena de sufijos (cada uno con su separador propio):
#   · latino (+ subíndice):  bis · ter · quintus · "bis 1" · "bis uno" · "bis-A"
#   · guion + letra:         -A · -B
#   · guion + número:        -1 · -2
_ARTICLE_LABEL = (
    r'(' + _ARTICLE_NUM
    + r'(?:[ \t]*[ºo°](?![a-záéíóú]))?'   # ordinal "1o"/"1 o", pero NO la "O" de "Octies"/"Octavus"
    + r'(?:'
    + r'[ \t.\-]+(?:' + _ARTICLE_LATIN + r')' + _ARTICLE_SUBINDEX
    + r'|-[A-Za-z](?![A-Za-z])'
    + r'|-\d+'
    # Cualquier palabra pegada al número y seguida del delimitador del artículo (".-") es
    # su sufijo, aunque sea una errata del documento: "148 séptimus.-", "356 CUARTER.-",
    # "455 osties.-" (Morelos, CDMX). Sin esto colapsan con el artículo base (148, 356, 455).
    + r'|[ \t]+[A-Za-zÁÉÍÓÚáéíóú]{3,14}(?=[ \t]*\.?[ \t]*\**[ \t]*[-–])'
    # Una sola MAYÚSCULA separada por espacio y seguida del delimitador, del fin de la línea
    # o de una nota entre paréntesis: "24 A. -", "## ARTÍCULO 737 A" (texto en la línea de
    # abajo), "737 F (DEROGADO…" (Códigos Civil y de Procedimientos Civiles del DF). Exigirlo
    # evita tomar como sufijo la "A" de "Artículo 5.- A la persona…" (delimitador ANTES).
    + r'|[ \t]+(?-i:[A-Z])(?=[ \t]*\.?[ \t]*\**[ \t]*(?:[-–(]|$))'
    + r')*'
    + r')'
)
# Variantes reales que también abren artículo (medido en los códigos de Morelos, donde sin
# esto ~2/3 de los artículos del Código Penal quedaban pegados al anterior):
#   · asterisco de "artículo reformado": "**ARTÍCULO *35.-**" (convención de la Consejería
#     Jurídica de Morelos; el '*' va entre la palabra y el número);
#   · erratas del documento fuente: "ARTÍULO", "ARTCULO", "ARTICULO" (sin acento);
#   · viñeta de lista que dejó el conversor: "- **Artículo 167.-**" (CPF, CDMX, Querétaro);
#   · fila de tabla: "|**ARTÍCULO 68.-**Se deroga.|" (LGEEPA).
_ARTICLE_WORD = r'art(?:[íi]culo|[íi]ulo|culo)'
ARTICLE_RE = re.compile(
    r'(?im)^[ \t#>*_|]*(?:[-•·][ \t]+[ \t#>*_]*)?(?:<u>[ \t#>*_]*)?' + _ARTICLE_WORD + r'(?:[ \t]+\*?|[ \t]*\*)[ \t]*' + _ARTICLE_LABEL,
)
# Igual que ARTICLE_RE pero SIN anclar a inicio de línea: para detectar en una PREGUNTA
# ("¿qué dice el artículo 167 de…?") a qué artículo se refiere y hacer búsqueda directa.
ARTICLE_QUERY_RE = re.compile(r'(?i)art[íi]culo[ \t]+' + _ARTICLE_LABEL)


def _article_label_parts(raw: str) -> tuple[str, str]:
    """(etiqueta_final, ocr_fix). `ocr_fix` es '' salvo que la autocorrección OCR cambiara
    el token-número, en cuyo caso trae 'antes→después' para poder AVISAR y que un humano lo
    revise. Normaliza markup y separadores (puntos/guiones → espacio) para etiquetas únicas
    y legibles: '246-A'→'246 A', '127 BIS-1'→'127 BIS 1', '22I BIS'→'221 BIS' (ocr_fix='22I→221')."""
    s = normalize_line(raw)
    s = re.sub(r'[.\-]+', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    head, sep, rest = s.partition(' ')
    ocr_fix = ''
    # Corrige OCR solo en el token-número (dígitos + confusiones + posible ordinal o/º/°).
    if re.fullmatch(r'[\dIl|OSZ]+[ºo°]?', head):
        fixed = head.translate(_OCR_TO_DIGIT)
        if fixed != head:
            ocr_fix = f'{head}→{fixed}'
        head = fixed
    return (head + sep + rest).strip(), ocr_fix


def _article_label(raw: str) -> str:
    """Etiqueta canónica del artículo (sin el detalle de autocorrección). Ver `_article_label_parts`."""
    return _article_label_parts(raw)[0]


# Palabras que delatan un artículo TRANSITORIO (de un decreto de reforma): su número se
# reinicia por decreto, así que "Artículo 2" puede repetirse legítimamente. Se usa para no
# marcar esos como duplicados sospechosos en `article_label_issues`.
_TRANSITORIO_HINT = re.compile(
    r'entrar[áa] en vigor|se reforma|se deroga|se adiciona|public|decreto|vigencia|'
    r'transitori|iniciar[áa] su vigencia|abrogad|d[ií]a siguiente', re.I)


def article_label_issues(units) -> list[dict]:
    """Chequeo de calidad del tagueo para AVISAR al ingerir (no corrige, solo reporta):
      · 'ocr_autofixed': el número tenía una letra OCR pegada y se corrigió sola
                         (antes→después). Se muestra para que un humano confirme que estuvo bien.
      · 'ocr_suspect':   el token-número aún tiene una letra tras normalizar (OCR no resuelto).
      · 'duplicate':     misma etiqueta en >1 artículo del CUERPO (no explicado por transitorios),
                         señal de que el regex colapsó designadores distintos o hay basura.
    Devuelve lista de dicts con {type, title, positions, [detail]}."""
    arts = [u for u in units if u.get('unit_type') == 'article']
    issues: list[dict] = []
    for u in arts:
        if u.get('ocr_fix'):
            issues.append({'type': 'ocr_autofixed', 'title': u['title'],
                           'positions': [u['position']], 'detail': u['ocr_fix']})
    for u in arts:
        num = re.sub(r'[ºo°]$', '', u['title'].replace('Artículo', '').strip().split(' ')[0])
        if re.search(r'[A-Za-z]', num):
            issues.append({'type': 'ocr_suspect', 'title': u['title'], 'positions': [u['position']]})
    by: dict[str, list] = {}
    for u in arts:
        by.setdefault(u['title'], []).append(u)
    n = len(arts) or 1
    for title, us in by.items():
        if len(us) < 2:
            continue
        body = [u for u in us if not _TRANSITORIO_HINT.search(u['text'][:220]) and u['position'] <= 0.7 * n]
        if len(body) > 1:
            issues.append({'type': 'duplicate', 'title': title,
                           'positions': sorted(u['position'] for u in us)})
    return issues


def find_article_ref(question: str) -> str | None:
    """Si la PREGUNTA cita un artículo ('¿qué dice el artículo 167?'), devuelve su etiqueta
    canónica ('Artículo 167') para hacer una búsqueda directa por metadata; si no, None.
    Las búsquedas por número exacto no son semánticas: el denso las falla, así que conviene
    resolverlas por `title`. Ignora coincidencias que sean parte de un rango ('del 10 al 20')."""
    m = ARTICLE_QUERY_RE.search(question or '')
    if not m:
        return None
    return 'Artículo ' + _article_label(m.group(1))


# Un código está HECHO de artículos (densos, seguidos); un libro de doctrina sólo
# los CITA de pasada. Contar artículos no basta —una obra que discute 30 artículos
# no es un código—: se exige además densidad (artículos por cada 1000 palabras).
# En este corpus los dos códigos están en ~4–6 y ningún libro pasa de ~0.9.
ARTICLE_DENSITY_MIN = 2.0


def words(text: str) -> int:
    return len(re.findall(r'\S+', text))


def article_density(text: str) -> float:
    return 1000 * len(ARTICLE_RE.findall(text)) / max(words(text), 1)


def document_strategy(text: str) -> str:
    articles = len(ARTICLE_RE.findall(text))
    headings = len(HEADING_RE.findall(text))
    if articles >= 10 and article_density(text) >= ARTICLE_DENSITY_MIN:
        return 'article'
    if headings >= 3:
        return 'heading'
    return 'paragraph'


# ── Extracción de unidades semánticas ────────────────────────────────────────────
# Encabezados estructurales de un código: LIBRO ⊃ TÍTULO ⊃ CAPÍTULO ⊃ SECCIÓN. En el
# Markdown salido del PDF casi todos son "# ..." (mismo nivel Markdown), así que NO se
# puede anidar por número de '#'; se clasifican por su palabra clave y se anidan por ese
# rango. El PDF→MD, además, rompe los encabezados de tres formas que hay que reparar
# (medido en CDMX, CPF y Edomex; sin esto el capítulo se pierde y, p. ej., el chunk del
# art. 179 CDMX no contenía la palabra "acoso" → BM25/híbrido no lo encontraba):
#   1. Encabezado "desnudo" + nombre aparte: "# CAPITULO IV" y luego "# Causas de
#      exclusión del delito" (o "TÍTULO PRIMERO" + "LA LEY PENAL"). El nombre se une.
#   2. Capítulo sin la palabra clave: "# VIOLACIÓN", "# ACOSO SEXUAL", "# TENTATIVA" (el
#      conversor perdió "CAPÍTULO I"). Un encabezado huérfano en MAYÚSCULAS dentro de un
#      TÍTULO se toma como capítulo.
#   3. Estructura en negritas sin '#': "**CAPÍTULO VIII**" + "**DISPOSICIONES GENERALES**";
#      además de contarla, se quita del final del artículo anterior, donde quedaba pegada.
# Lo que NO es estructura y se ignora: fracciones con forma de encabezado ("I. Dolosos;"),
# corredores de página ("CÓDIGO PENAL FEDERAL", "Nuevo Código Publicado en el DOF…").
_STRUCT_RANK = [
    (re.compile(r'(?i)\bLIBRO\b'), 0),
    (re.compile(r'(?i)\bT[ÍI]TULO\b'), 1),
    (re.compile(r'(?i)\bSUBT[ÍI]TULO\b'), 2),
    (re.compile(r'(?i)\bCAP[ÍI]TULO\b'), 3),
    (re.compile(r'(?i)\bSECCI[ÓO]N\b'), 4),
]
CHAPTER_RANK = 3
_TITLE_RANK = 1
# "CAPÍTULO IV", "TITULO SEGUNDO", "CAPITULO III BIS", "SECCIÓN ÚNICA": palabra clave +
# numeral y nada más → su nombre viene en el encabezado siguiente.
_BARE_STRUCT_RE = re.compile(
    r'(?i)^(?:LIBRO|SUBT[ÍI]TULO|T[ÍI]TULO|CAP[ÍI]TULO|SECCI[ÓO]N)\s+'
    r'(?:[IVXLC]+|\d+|[ÚU]NIC[OA]|PRIMER[OA]|SEGUND[OA]|TERCER[OA]|CUART[OA]|QUINT[OA]|SEXT[OA]|'
    r'S[ÉE]PTIM[OA]|OCTAV[OA]|NOVEN[OA]|D[ÉE]CIM[OA](?:\s+\w+)?|[A-ZÁÉÍÓÚ]+(?:GÉSIM|CENTÉSIM)\w*(?:\s+\w+)?)'
    r'(?:\s+(?:BIS|TER|QU[ÁA]TER|QUINQUIES))?\.?$'
)
# Línea completa en negritas (candidata a encabezado sin '#'): "**CAPÍTULO VIII**".
_BOLD_LINE_RE = re.compile(r'(?m)^[ \t]*\*\*([^*\n]{2,160})\*\*[ \t]*$')
_REFORM_NOTE_RE = re.compile(r'\s*\((?:ref|adici|reforma|derog|p\.?\s*o\.?|dof|decreto)[^)]*\)\s*$', re.I)
_FRACTION_RE = re.compile(r'(?i)^(?:[IVXLC]+|\d+|[a-z])[.)]\s')
_RUNNING_HEADER_RE = re.compile(
    r'(?i)^C[ÓO]DIGO\b|diario oficial|publicad[oa] en|[úu]ltima reforma|peri[óo]dico oficial|gaceta')


def _heading_rank(title: str):
    for rx, rank in _STRUCT_RANK:
        if rx.search(title):
            return rank
    return None


def _clean_heading(raw: str) -> str:
    # Quita la nota de reforma que a veces cierra el título ("CAPÍTULO IV … (Ref. P.O…)").
    return _REFORM_NOTE_RE.sub('', normalize_line(raw)).strip()


def _is_structural_noise(title: str) -> bool:
    """Encabezado sin palabra clave que NO es un nombre de capítulo/título."""
    return (not title or bool(_FRACTION_RE.match(title)) or bool(_RUNNING_HEADER_RE.search(title))
            or bool(re.search(r'(?i)\bart[íi]culo\s+\d', title)))


def _is_orphan_chapter(title: str) -> bool:
    """¿Un encabezado huérfano (sin palabra clave ni encabezado desnudo antes) es un
    capítulo al que el conversor le quitó "CAPÍTULO N"? Sólo nombres cortos en MAYÚSCULAS
    y sin puntuación final: los rubros en minúsculas o las oraciones no cuentan."""
    letters = [c for c in title if c.isalpha()]
    if not letters or len(title.split()) > 14 or title[-1] in '.;:,':
        return False
    return sum(c.isupper() for c in letters) / len(letters) >= 0.85


def _structure_events(text: str):
    """Encabezados en orden de lectura: '#…' siempre; líneas en negritas sólo como
    candidatas (se aceptan si llevan palabra clave o si nombran un encabezado desnudo)."""
    ev = [(m.start(), '#', m.group(2)) for m in HEADING_RE.finditer(text)]
    ev += [(m.start(), '**', m.group(1)) for m in _BOLD_LINE_RE.finditer(text)
           if not HEADING_RE.match(text[m.start():m.end()])]
    return sorted(ev, key=lambda e: e[0])


def _apply_heading(stack: dict, pending, kind: str, raw: str):
    """Actualiza la pila con un encabezado; devuelve el nuevo `pending` (rango de un
    encabezado desnudo que espera su nombre en el siguiente encabezado) o None."""
    title = _clean_heading(raw)
    rank = _heading_rank(title)
    if rank is not None and not (kind == '**' and not re.match(r'(?i)^(?:LIBRO|SUBT[ÍI]TULO|T[ÍI]TULO|CAP[ÍI]TULO|SECCI[ÓO]N)\b', title)):
        for deeper in [r for r in stack if r >= rank]:
            del stack[deeper]
        stack[rank] = title
        return rank if _BARE_STRUCT_RE.match(title) else None
    if _is_structural_noise(title):
        return pending                                   # no rompe la espera del nombre
    if pending is not None and pending in stack:         # patrón 1: nombre del desnudo
        stack[pending] = f'{stack[pending]} {title}'
        return None
    if kind == '#' and _TITLE_RANK in stack and _is_orphan_chapter(title):   # patrón 2
        for deeper in [r for r in stack if r >= CHAPTER_RANK]:
            del stack[deeper]
        stack[CHAPTER_RANK] = title
    return None


def _is_bold_struct(line: str) -> bool:
    m = _BOLD_LINE_RE.match(line)
    return bool(m and re.match(r'(?i)^\s*(?:LIBRO|SUBT[ÍI]TULO|T[ÍI]TULO|CAP[ÍI]TULO|SECCI[ÓO]N)\b', normalize_line(m.group(1))))


def _strip_trailing_headings(body: str) -> str:
    """Quita del FINAL del chunk las líneas de encabezado (y blancos): un header al final
    de un artículo siempre introduce la SIGUIENTE sección, no la actual (así el
    '# CAPÍTULO III ESTUPRO' deja de contaminar el chunk del 166 BIS). Incluye la
    estructura en negritas ("**CAPÍTULO VIII**" + "**DISPOSICIONES GENERALES**")."""
    lines = body.rstrip().split('\n')
    while lines:
        last = lines[-1]
        if not last.strip() or HEADING_RE.match(last) or _is_bold_struct(last):
            lines.pop()
            continue
        # Nombre en negritas cuyo encabezado desnudo (en negritas) está justo arriba.
        prev = next((ln for ln in reversed(lines[:-1]) if ln.strip()), '')
        if _BOLD_LINE_RE.match(last) and _is_bold_struct(prev):
            lines.pop()
            continue
        break
    return '\n'.join(lines).strip()


# Título de estructura y artículo en la MISMA línea (el conversor unió dos líneas):
#   "## **CAPÍTULO II DEL DIVORCIO ARTÍCULO *174.-** DEL DIVORCIO. El divorcio…"
#   "**CAPITULO IV Adulterio** (Se deroga) … **Artículo 273.-** (Se deroga)."
# Se parte la línea antes del artículo. Solo si el artículo lleva forma de encabezado
# ("ARTÍCULO N.-" / "Artículo N.-"); una cita en prosa ("del artículo 174") no la lleva.
_GLUED_ARTICLE_RE = re.compile(
    r'(?im)^([ \t#>*_]*(?:LIBRO|SUBT[ÍI]TULO|T[ÍI]TULO|CAP[ÍI]TULO|SECCI[ÓO]N)\b[^\n]*?)[ \t]*'
    r'((?:\*\*)?(?-i:ART[ÍI]CULO|Art[íi]culo)[ \t]*\*?[ \t]*\d+[^\n]{0,24}?[ \t]*\.?[ \t]*\**[ \t]*[-–])')


# Artículo en NEGRITAS que empieza a mitad de línea tras el fin de una oración: varios
# derogados en una línea ("**Artículo 268** .- (Se deroga). **Artículo 269** .- (Se deroga).")
# o un artículo vigente pegado al anterior ("…en favor de la comunidad. **ARTÍCULO 234.** -
# Cuando se cause…", Código Penal de Morelos). Negritas + delimitador ".-" tras un punto es
# forma de encabezado; una cita en prosa no lleva ninguna de las dos.
_MIDLINE_BOLD_ARTICLE_RE = re.compile(
    r'([.;:)\]])[ \t]+(\*\*(?:ART[ÍI]CULO|Art[íi]culo)[ \t]*\*?[ \t]*\d+'
    r'(?:[^*\n]{0,30}?[-–][^*\n]{0,4}\*\*'                 # "**ARTÍCULO 178.-** Derogado"
    r'|[^*\n]{0,30}?\.\*\*(?=[ \t]+[A-ZÁÉÍÓÚ(])'             # "**Artículo 130.** Derogado"
    r'|[^*\n]{0,30}\*\*[ \t]*\.?[ \t]*[-–]))')           # "**Artículo 269** .- (Se deroga)"


def split_glued_articles(text: str) -> str:
    text = _GLUED_ARTICLE_RE.sub(lambda m: m.group(1).rstrip() + '\n\n' + m.group(2), text)
    return _MIDLINE_BOLD_ARTICLE_RE.sub(lambda m: m.group(1) + '\n\n' + m.group(2), text)


def article_units(text: str):
    text = split_glued_articles(text)
    matches = list(ARTICLE_RE.finditer(text))
    heads = _structure_events(text)
    stack: dict[int, str] = {}   # rango estructural → título vigente (LIBRO/TÍTULO/SUBTÍTULO/CAPÍTULO/SECCIÓN)
    pending = None               # rango de un encabezado desnudo que espera su nombre
    hi = 0                       # cursor sobre `heads`, avanza en orden de lectura
    for i, match in enumerate(matches):
        # Consume los encabezados que aparecen ANTES del inicio de este artículo, para
        # dejar la pila con la sección en vigor. Un rango nuevo descarta los más profundos.
        while hi < len(heads) and heads[hi][0] < match.start():
            pending = _apply_heading(stack, pending, heads[hi][1], heads[hi][2])
            hi += 1
        pending = None   # el nombre de un encabezado desnudo nunca va después de un artículo
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        label, ocr_fix = _article_label_parts(match.group(1))
        title = 'Artículo ' + label
        path = [stack[r] for r in sorted(stack)]
        yield {
            'unit_type': 'article',
            'title': title,
            'level': 2,
            'text': _strip_trailing_headings(text[match.start():end]),
            # Ruta legible que TERMINA en el artículo; se antepone al texto embebido
            # (make_chunks), así el capítulo —p. ej. "ESTUPRO"— se vuelve buscable.
            'hierarchy': ' > '.join(path + [title]) if path else '',
            'ocr_fix': ocr_fix,   # '' o 'antes→después' si se autocorrigió el número (OCR)
        }


def heading_units(text: str):
    matches = list(HEADING_RE.finditer(text))
    hierarchy: list[tuple[int, str]] = []
    for i, match in enumerate(matches):
        level = len(match.group(1))
        title = normalize_line(match.group(2))
        hierarchy = [item for item in hierarchy if item[0] < level] + [(level, title)]
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        yield {
            'unit_type': 'heading',
            'title': title,
            'level': level,
            'text': text[match.start():end].strip(),
            'hierarchy': ' > '.join(item[1] for item in hierarchy),
        }


def paragraph_units(text: str):
    for i, paragraph in enumerate(re.split(r'\n\s*\n', text), start=1):
        if words(paragraph) >= 20:
            yield {'unit_type': 'paragraph', 'title': f'Bloque {i}', 'level': 0, 'text': paragraph, 'hierarchy': ''}


def semantic_units(name: str, text: str):
    strategy = document_strategy(text)
    extractor = {'article': article_units, 'heading': heading_units, 'paragraph': paragraph_units}[strategy]
    for position, unit in enumerate(extractor(text), start=1):
        yield {'document': name, 'strategy': strategy, 'position': position, **unit, 'words': words(unit['text'])}


# ── Fusión de bloques pequeños ───────────────────────────────────────────────────
def merge_small_siblings(units: pd.DataFrame, min_words: int = MIN_WORDS) -> pd.DataFrame:
    """Fusiona bloques demasiado cortos con el siguiente del mismo documento.

    Un encabezado con muy poco cuerpo (un subtítulo casi vacío, una definición de
    una línea, o el ruido de encabezados de página que sobrevive a la limpieza) no
    merece un chunk propio: se recupera mal y fragmenta el contexto. Se acumulan
    bloques consecutivos en orden de lectura mientras el acumulado no alcance
    `min_words`; al alcanzarlo se cierra el grupo. Un resto final corto se une hacia
    atrás para no dejar una cola huérfana.

    Las leyes (`article`) NO se tocan: un artículo es la unidad jurídica aunque sea
    breve; la gente lo pide por número. Para el bloque fusionado, la metadata
    (título, jerarquía, nivel) se toma del sub-bloque con más palabras —el más
    representativo—, mientras que `position` conserva el orden de lectura. Se
    registra en `merged_units`/`merged_titles` cuántos bloques y cuáles se unieron.

    Nota deliberada: se fusiona con "el siguiente bloque en el documento", no con el
    hermano estricto del mismo padre. Exigir mismo padre deja más colas huérfanas y,
    para recuperación, unir una subsección minúscula al bloque contiguo es inocuo.
    """
    ATOMIC = {'article'}

    def combine(group: list[dict]) -> dict:
        anchor = max(group, key=lambda u: u['words'])   # etiqueta = bloque dominante
        merged = dict(anchor)
        merged['position'] = group[0]['position']        # ancla al orden de lectura
        merged['text'] = '\n\n'.join(u['text'] for u in group)
        merged['words'] = words(merged['text'])
        merged['merged_units'] = len(group)
        merged['merged_titles'] = ' + '.join(u['title'] for u in group)
        return merged

    merged_rows: list[dict] = []
    for document, doc_units in units.groupby('document', sort=False):
        rows = doc_units.sort_values('position').to_dict('records')
        if rows and rows[0]['strategy'] in ATOMIC:
            merged_rows.extend({**row, 'merged_units': 1, 'merged_titles': row['title']} for row in rows)
            continue
        buffer, buffer_words, closed = [], 0, []
        for row in rows:
            buffer.append(row)
            buffer_words += row['words']                 # '\n\n' es whitespace: la suma == words(join)
            if buffer_words >= min_words:
                closed.append(combine(buffer))
                buffer, buffer_words = [], 0
        if buffer:                                       # resto corto: fusiónalo hacia atrás
            tail = combine(buffer)
            if closed:
                prev = closed[-1]
                prev['text'] += '\n\n' + tail['text']
                prev['words'] = words(prev['text'])
                prev['merged_units'] += tail['merged_units']
                prev['merged_titles'] += ' + ' + tail['merged_titles']
            else:
                closed.append(tail)                      # documento entero < min_words: queda solo
        merged_rows.extend(closed)
    return pd.DataFrame(merged_rows)


# ── Partición de bloques grandes y armado de chunks ──────────────────────────────
def split_long_paragraph(paragraph: str, limit: int):
    """Parte un párrafo largo por oraciones y, como último recurso, por palabras."""
    sentences = re.split(r'(?<=[.!?;:])\s+', paragraph)
    fragments, current = [], []
    for sentence in sentences:
        sentence_words = sentence.split()
        # Una oración muy larga se corta sólo cuando no hay límite semántico menor.
        while len(sentence_words) > limit:
            if current:
                fragments.append(' '.join(current))
                current = []
            fragments.append(' '.join(sentence_words[:limit]))
            sentence_words = sentence_words[limit:]
        candidate = current + sentence_words
        if current and len(candidate) > limit:
            fragments.append(' '.join(current))
            current = sentence_words
        else:
            current = candidate
    if current:
        fragments.append(' '.join(current))
    return fragments


def split_by_paragraphs(text: str, max_words: int = MAX_WORDS, overlap_words: int = OVERLAP_WORDS):
    # Reservar espacio para el solapamiento garantiza que ningún chunk rebase max_words.
    limit = max_words - overlap_words
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    paragraphs = [fragment for p in paragraphs for fragment in split_long_paragraph(p, limit)]
    chunks, current = [], []
    for paragraph in paragraphs:
        candidate = '\n\n'.join(current + [paragraph])
        if current and words(candidate) > max_words:
            chunks.append('\n\n'.join(current))
            tail = ' '.join(chunks[-1].split()[-overlap_words:])
            current = [tail, paragraph] if tail else [paragraph]
        else:
            current.append(paragraph)
    if current:
        chunks.append('\n\n'.join(current))
    return chunks


# ── Título del documento ─────────────────────────────────────────────────────────
# El prefijo "Fuente:" de cada chunk llevaba solo el nombre del ARCHIVO. Para "Código Penal
# de la Ciudad de México.md" basta, pero "CPROFAMEM.md" no dice qué ley es: las preguntas
# ("el Código Procesal Familiar de Morelos…") no encontraban sus artículos salvo en los
# chunks donde, por accidente, quedaba pegado el encabezado de página con el nombre (medido:
# al limpiar ese encabezado el art. 493 cayó del rank 33 al 377). Las leyes abren con su
# nombre como primer título ("# **CÓDIGO FAMILIAR PARA EL ESTADO LIBRE Y SOBERANO DE
# MORELOS**"); se toma de ahí y va en TODOS los chunks del documento.
_DOC_TITLE_RE = re.compile(r'(?m)^#{1,2}[ \t]+(.+?)[ \t]*$')


def document_title(text: str, max_chars: int = 4000) -> str | None:
    """Nombre de la ley según su primer título (en los primeros `max_chars`), o None."""
    for m in _DOC_TITLE_RE.finditer(text[:max_chars]):
        # "SE EXPIDE EL CÓDIGO NACIONAL…" (decreto de expedición) → "CÓDIGO NACIONAL…"
        title = re.sub(r'(?i)^(?:decreto\s+por\s+el\s+que\s+)?se\s+expide\s+(?:el|la)\s+', '', _clean_heading(m.group(1)))
        n = len(title.split())
        # Debe EMPEZAR con el tipo de norma: "LA LEY PENAL" o "TÍTULO PRIMERO" son títulos internos.
        if 2 <= n <= 30 and re.match(r'(?i)(c[óo]digo|ley|reglamento|constituci[óo]n|estatuto)\b', title):
            return title
    return None


def _fold(s: str) -> str:
    return unicodedata.normalize('NFKD', normalize_line(s)).encode('ascii', 'ignore').decode().lower()


def _source_label(document: str, title: str | None) -> str:
    """'CÓDIGO PROCESAL FAMILIAR … DE MORELOS (CPROFAMEM.md)'; si el archivo ya se llama
    como la ley ('Código Penal Federal.md'), solo el archivo."""
    stem = re.sub(r'\.md$', '', document, flags=re.I)
    if not title or _fold(title) == _fold(stem):
        return document
    return f'{title} ({document})'


def make_chunks(units: pd.DataFrame, titles: dict[str, str | None] | None = None) -> pd.DataFrame:
    rows = []
    titles = titles or {}
    for unit in units.itertuples(index=False):
        parts = [unit.text] if unit.words <= MAX_WORDS else split_by_paragraphs(unit.text)
        source_label = _source_label(unit.document, titles.get(unit.document))
        for part_number, part in enumerate(parts, start=1):
            prefix = f'Fuente: {source_label}\nSección: {unit.hierarchy or unit.title}\n\n'
            rows.append({
                'source': unit.document, 'unit_type': unit.unit_type, 'title': unit.title,
                'hierarchy': unit.hierarchy, 'position': unit.position,
                'part': part_number, 'words': words(part), 'text_for_embedding': prefix + part,
            })
    return pd.DataFrame(rows)


# ── Conveniencias de alto nivel ──────────────────────────────────────────────────
def read_markdown_dir(corpus_path: str | Path) -> dict[str, str]:
    """Lee todos los .md de un directorio → {nombre: texto crudo}."""
    paths = sorted(Path(corpus_path).glob('*.md'))
    if not paths:
        raise FileNotFoundError(f'No encontré archivos Markdown en {corpus_path}')
    return {p.name: p.read_text(encoding='utf-8') for p in paths}


def clean_corpus(raw_documents: dict[str, str]) -> dict[str, str]:
    """{nombre: texto crudo} → {nombre: texto limpio}."""
    return {name: clean_document(text)['clean_text'] for name, text in raw_documents.items()}


def extract_units(documents: dict[str, str]) -> pd.DataFrame:
    """{nombre: texto limpio} → DataFrame de unidades semánticas."""
    return pd.DataFrame(unit for name, text in documents.items() for unit in semantic_units(name, text))


def chunk_documents(documents: dict[str, str]) -> pd.DataFrame:
    """Pipeline completo sobre texto YA limpio: unidades → fusión → chunks."""
    units = extract_units(documents)
    merged = merge_small_siblings(units)
    # Solo las leyes/códigos: en un libro el primer título suele ser un capítulo, no la obra.
    titles = {name: document_title(text) for name, text in documents.items()
              if document_strategy(text) == 'article'}
    return make_chunks(merged, titles)
