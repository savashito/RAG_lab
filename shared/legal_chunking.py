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
from collections import Counter
from pathlib import Path

import pandas as pd

# ── Presupuesto de tamaño (palabras) ────────────────────────────────────────────
TARGET_WORDS = 500
MAX_WORDS = 800
MIN_WORDS = 80
OVERLAP_WORDS = 80

# ── Limpieza conservadora ────────────────────────────────────────────────────────
PAGE_RE = re.compile(r'^(?:\d+|[IVXLCDM]+|\d+\s+de\s+\d+)$', re.I)
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
    'editorial_watermark', 'page_number', 'institutional_header',
]


def normalize_line(line: str) -> str:
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>|[*_]', '', line)).strip()


# Reglas de una sola línea: la primera coincidencia define la razón de descarte.
LINE_NOISE_PATTERNS = {
    'page_number': PAGE_RE,
    'institutional_header': INSTITUTIONAL_RE,
    'editorial_watermark': EDITORIAL_RE,
}


def line_noise_reason(plain: str) -> str | None:
    for reason, pattern in LINE_NOISE_PATTERNS.items():
        if pattern.search(plain):
            return reason
    return None


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
    kept, removed = [], []
    removed_by_reason: Counter = Counter()
    in_catalog_record = False
    in_contents_table = False

    def discard(line: str, reason: str) -> None:
        removed.append(line)
        removed_by_reason[reason] += 1

    for line in lines:
        plain = normalize_line(line)
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
        else:
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
# llevan. Captura la etiqueta (número + o/º + Bis/Ter…) para el título.
ARTICLE_RE = re.compile(
    r'(?im)^[ \t#>*_]*(?:<u>[ \t#>*_]*)?art[íi]culo[ \t]+'
    r'(\d+[ \t]*[ºo]?(?:[ \t]+(?:bis|ter|qu[áa]ter|quinquies|sexies|septies))?)',
)
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
def article_units(text: str):
    matches = list(ARTICLE_RE.finditer(text))
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        yield {
            'unit_type': 'article',
            'title': 'Artículo ' + normalize_line(match.group(1)),
            'level': 2,
            'text': text[match.start():end].strip(),
            'hierarchy': '',
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


def make_chunks(units: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for unit in units.itertuples(index=False):
        parts = [unit.text] if unit.words <= MAX_WORDS else split_by_paragraphs(unit.text)
        for part_number, part in enumerate(parts, start=1):
            prefix = f'Fuente: {unit.document}\nSección: {unit.hierarchy or unit.title}\n\n'
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
    return make_chunks(merged)
