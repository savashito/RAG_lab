"""
Pruebas de shared/legal_chunking.py.

Antes vivían como asserts dentro del notebook de exploración; aquí protegen la
librería de forma independiente. Dos niveles:

  * unitarias sintéticas (rápidas, sin corpus) — limpieza y clasificación;
  * de corpus (marcadas `corpus`) — invariantes y guardas de regresión sobre los
    .md reales; se saltan solas si el corpus no está presente.

    uv run pytest tests/test_legal_chunking.py
    uv run pytest tests/test_legal_chunking.py -m "not corpus"   # sólo las rápidas
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

LABS = Path(__file__).resolve().parents[1]
if str(LABS) not in sys.path:
    sys.path.insert(0, str(LABS))

from shared import legal_chunking as lc  # noqa: E402

CORPUS_PATH = LABS / 'ingestion' / 'out' / 'Sistema Penal Acusatorio'


# ── Unitarias de limpieza (sintéticas) ───────────────────────────────────────────
CLEANING_CASES = [
    ('conserva contenido jurídico',
     '# Artículo 10\n\nLa autoridad debe fundar y motivar su acto.',
     ['Artículo 10', 'fundar y motivar'], []),
    ('elimina ficha catalográfica completa',
     '#### Catalogación en la publicación UNAM\nNombres: Persona autora.\nIdentificadores: ISBN 123.\nEsta edición es propiedad de la UNAM.\n\n# Introducción\n\nContenido jurídico.',
     ['Introducción', 'Contenido jurídico'], ['Catalogación', 'Nombres:', 'Identificadores:', 'Esta edición']),
    ('elimina tabla de contenido',
     '## CONTENIDO\n|Capítulo primero|1|\n|---|---|\n\n# Capítulo primero\n\nTexto sustantivo.',
     ['Capítulo primero', 'Texto sustantivo'], ['|Capítulo primero|1|']),
    ('elimina ruido editorial sin borrar el cuerpo',
     'DR © 2023. Universidad Nacional Autónoma de México\n\nArgumento jurídico relevante.',
     ['Argumento jurídico relevante'], ['DR ©']),
    ('elimina delimitadores de imagen y conserva su OCR',
     '<!-- Start of picture text -->\nDiagrama: audiencia inicial.\n<!-- End of picture text -->',
     ['Diagrama: audiencia inicial'], ['<!-- Start of picture text -->', '<!-- End of picture text -->']),
    ('elimina folio de página con forma de encabezado',
     '#### 154\n\nTexto sustantivo del artículo.\n\n#### XVIII\n\nMás cuerpo doctrinal.',
     ['Texto sustantivo del artículo', 'Más cuerpo doctrinal'], ['#### 154', '#### XVIII']),
    ('elimina título-corredor repetido, conserva el único',
     '\n\n'.join(['### La formulación de imputación'] * 6)
     + '\n\n### Capítulo único\n\nCuerpo del capítulo con contenido sustantivo.',
     ['Capítulo único', 'Cuerpo del capítulo'], ['formulación de imputación']),
    ('no confunde una referencia en prosa con título-corredor',
     '# Sección\n\nEl artículo 5o. del código se cita muchas veces: art. 5o, art. 5o, art. 5o.\n\nTexto.',
     ['El artículo 5o. del código', 'Sección', 'Texto'], []),
    ('elimina el encabezado de Diputados en su propia línea',
     'CÁMARA DE DIPUTADOS DEL H. CONGRESO DE LA UNIÓN Secretaría General Secretaría de Servicios Parlamentarios\n\n'
     '**Artículo 1o.-** Texto del artículo.',
     ['Artículo 1o.', 'Texto del artículo'], ['CÁMARA DE DIPUTADOS', 'Servicios Parlamentarios']),
    # Regresión: un párrafo que MENCIONA a la Secretaría General es cuerpo, no encabezado.
    # Antes se borraba entero (así se perdieron las págs. 11–14 de un acuerdo OCReado).
    ('conserva un párrafo que menciona a la Secretaría General',
     'Comuníquese el contenido del presente acuerdo a las y los integrantes de la Comisión, '
     'por conducto de la Secretaría General de este Consejo, para los efectos de su '
     'respectiva competencia, y publíquese en el Boletín Judicial.',
     ['Comuníquese el contenido', 'Boletín Judicial'], []),
    ('conserva una cláusula convencional que cita a la Secretaría General de la OEA',
     'Los instrumentos de ratificación y adhesión se depositarán en la Secretaría General de '
     'la Organización de los Estados Americanos.',
     ['Los instrumentos de ratificación'], []),
    ('recorta el encabezado de Diputados pegado a un párrafo y conserva el resto',
     'CÁMARA DE DIPUTADOS DEL H. CONGRESO DE LA UNIÓN Última Reforma DOF 13-03-2026 Secretaría General '
     'Secretaría de Servicios Parlamentarios Artículo 352.- (Se deroga). ' + 'texto del artículo ' * 20,
     ['Artículo 352.- (Se deroga)', 'texto del artículo'], ['CÁMARA DE DIPUTADOS', 'Servicios Parlamentarios']),
    ('elimina folio de página con formato N/M',
     'Texto del acuerdo.\n\n13/15\n\nMás texto del acuerdo.',
     ['Texto del acuerdo', 'Más texto del acuerdo'], ['13/15']),
    ('no borra una fracción dentro de una línea de cuerpo',
     'Se aprobó por 3/4 partes del pleno.',
     ['3/4 partes'], []),
    ('no borra un párrafo largo por citar la Biblioteca Jurídica Virtual',
     'Como explica el autor en la obra disponible en la Biblioteca Jurídica Virtual, ' + 'el debido proceso exige ' * 12,
     ['Como explica el autor', 'el debido proceso exige'], []),
]


@pytest.mark.parametrize('name,text,must_keep,must_remove', CLEANING_CASES,
                         ids=[c[0] for c in CLEANING_CASES])
def test_clean_document(name, text, must_keep, must_remove):
    clean = lc.clean_document(text)['clean_text']
    for expected in must_keep:
        assert expected in clean, f'{name}: faltó conservar {expected!r}'
    for unexpected in must_remove:
        assert unexpected not in clean, f'{name}: faltó eliminar {unexpected!r}'


# ── Unitarias de clasificación (sintéticas) ──────────────────────────────────────
def test_strategy_code_vs_doctrine():
    # Código: muchos artículos densos (negrita en línea, no encabezado).
    code = '\n\n'.join(f'**Artículo {i}o** .- Disposición número {i}.' for i in range(1, 16))
    assert lc.document_strategy(code) == 'article'
    # Doctrina que CITA artículos de pasada pero es mayormente prosa → NO 'article'
    # (las citas van a mitad de línea, así que ARTICLE_RE no las cuenta como inicio).
    prose = ('# Capítulo\n\n' + 'La doctrina discute el punto con amplitud. ' * 400
             + '\n\n' + '\n'.join(f'Véase el artículo {i}o del código.' for i in range(1, 16)))
    assert lc.document_strategy(prose) != 'article'


def test_article_regex_ignores_prose_references():
    # "artículo Cuarto Transitorio" y "Artículo reformado DOF" no llevan dígito → no matchean.
    assert lc.ARTICLE_RE.search('del artículo Cuarto Transitorio de la Ley') is None
    assert lc.ARTICLE_RE.search('_Artículo reformado DOF 23-12-1974_') is None
    assert lc.ARTICLE_RE.match('**Artículo 11 Bis.-** Para los efectos') is not None


# ── De corpus (invariantes y guardas de regresión) ───────────────────────────────
requires_corpus = pytest.mark.skipif(
    not CORPUS_PATH.exists(), reason=f'corpus ausente en {CORPUS_PATH}')


@pytest.fixture(scope='module')
def documents():
    return lc.clean_corpus(lc.read_markdown_dir(CORPUS_PATH))


@pytest.mark.corpus
@requires_corpus
def test_merge_preserves_all_text(documents):
    units = lc.extract_units(documents)
    merged = lc.merge_small_siblings(units)
    assert int(merged.words.sum()) == int(units.words.sum()), 'la fusión perdió o duplicó texto'


@pytest.mark.corpus
@requires_corpus
def test_no_orphan_blocks_after_merge(documents):
    merged = lc.merge_small_siblings(lc.extract_units(documents))
    orphans = merged.query("unit_type != 'article' and words < @lc.MIN_WORDS")
    assert orphans.empty, f'quedaron bloques huérfanos < MIN_WORDS: {len(orphans)}'


@pytest.mark.corpus
@requires_corpus
def test_no_chunk_exceeds_max_words(documents):
    chunks = lc.chunk_documents(documents)
    assert (chunks.words <= lc.MAX_WORDS).all(), 'hay chunks que rebasan MAX_WORDS'


@pytest.mark.corpus
@requires_corpus
def test_no_residual_page_furniture(documents):
    """Ni folios ni títulos-corredor con forma de encabezado sobreviven a la limpieza."""
    from collections import Counter
    for name, text in documents.items():
        numeric = [l for l in text.splitlines() if lc.HEADING_PAGE_RE.match(l.strip())]
        assert not numeric, f'{name}: sobrevivieron encabezados-folio: {numeric[:3]}'
        heads = Counter(lc.normalize_line(l) for l in text.splitlines() if l.lstrip().startswith('#'))
        repeated = [h for h, n in heads.items() if h and n >= 6]
        assert not repeated, f'{name}: sobrevivieron títulos-corredor repetidos: {repeated[:3]}'


@pytest.mark.corpus
@requires_corpus
def test_classification_consistent_both_directions(documents):
    """Ningún código queda como 'heading' ni prosa de baja densidad como 'article'."""
    for name, text in documents.items():
        strat = lc.document_strategy(text)
        n_art = len(lc.ARTICLE_RE.findall(text))
        dens = lc.article_density(text)
        looks_like_code = n_art >= 10 and dens >= lc.ARTICLE_DENSITY_MIN
        assert not (looks_like_code and strat != 'article'), f'{name}: código no enrutado a article'
        assert not (strat == 'article' and dens < lc.ARTICLE_DENSITY_MIN), f'{name}: prosa enrutada como code'


# ── Jerarquía con encabezados rotos por el PDF→MD (caso real: acoso sexual CDMX) ──

def _hier(md):
    return {u['title']: u['hierarchy'] for u in lc.article_units(md)}


def test_orphan_chapter_without_keyword_is_kept():
    # El conversor perdió "CAPÍTULO III": sin esto el art. 179 no contenía "acoso".
    md = ('# **TÍTULO QUINTO DELITOS CONTRA LA LIBERTAD SEXUAL**\n\n# **VIOLACIÓN**\n\n'
          '**ARTÍCULO 174.-** Al que por medio de la violencia realice cópula…\n\n'
          '# **ACOSO SEXUAL**\n\n**ARTÍCULO 179.-** A quien solicite favores sexuales…\n\n'
          '# **CAPÍTULO IV ESTUPRO**\n\n**ARTÍCULO 180.-** Al que tenga cópula…\n')
    h = _hier(md)
    assert h['Artículo 174'].endswith('> VIOLACIÓN > Artículo 174')
    assert h['Artículo 179'].endswith('> ACOSO SEXUAL > Artículo 179')
    assert h['Artículo 180'].endswith('> CAPÍTULO IV ESTUPRO > Artículo 180')


def test_bare_heading_takes_name_from_next_heading():
    md = ('# TITULO PRIMERO\n\n# Responsabilidad Penal\n\n# CAPITULO IV\n\n'
          '# Causas de exclusión del delito\n\n**Artículo 15** .- El delito se excluye cuando…\n')
    assert _hier(md)['Artículo 15'] == ('TITULO PRIMERO Responsabilidad Penal > '
                                        'CAPITULO IV Causas de exclusión del delito > Artículo 15')


def test_bold_structure_counts_and_is_stripped_from_previous_article():
    md = ('# **TÍTULO QUINTO DELITOS SEXUALES**\n\n# **CAPÍTULO VII CONTRA LA INTIMIDAD SEXUAL**\n\n'
          '**ARTÍCULO 181 QUINTUS.-** Comete el delito… Este delito se perseguirá por querella. \n\n'
          '**CAPÍTULO VIII** \n\n**DISPOSICIONES GENERALES**\n\n**ARTÍCULO 182.-** Cuando resulten hijos…\n')
    units = {u['title']: u for u in lc.article_units(md)}
    assert units['Artículo 182']['hierarchy'].endswith('> CAPÍTULO VIII DISPOSICIONES GENERALES > Artículo 182')
    assert 'CAPÍTULO VIII' not in units['Artículo 181 QUINTUS']['text']
    assert units['Artículo 181 QUINTUS']['text'].endswith('por querella.')


def test_fractions_and_running_headers_are_not_chapters():
    md = ('# TITULO SEGUNDO\n\n# CAPITULO I EL DELITO Y SUS CLASES\n\n**Artículo 8.-** Los delitos pueden ser:\n\n'
          '# **I.** Dolosos;\n\nEl delito es doloso cuando…\n\n# CÓDIGO PENAL FEDERAL\n\n'
          '# Nuevo Código Publicado en el Diario Oficial de la Federación\n\n**Artículo 9.-** Texto.\n')
    h = _hier(md)
    assert h['Artículo 9'] == 'TITULO SEGUNDO > CAPITULO I EL DELITO Y SUS CLASES > Artículo 9'


def test_lowercase_orphan_heading_is_not_promoted():
    # Un rubro en minúsculas suelto (sin encabezado desnudo antes) no se inventa como capítulo.
    md = ('# TÍTULO TERCERO Aplicación de las Sanciones\n\n# CAPITULO I Reglas generales\n\n'
          '**Artículo 51.-** Texto.\n\n# Otras reglas del juzgador\n\n**Artículo 52.-** Texto.\n')
    assert _hier(md)['Artículo 52'].endswith('> CAPITULO I Reglas generales > Artículo 52')


# ── Variantes reales de inicio de artículo (Morelos, CPF, CDMX, Querétaro, LGEEPA) ──
def _titles(md):
    return [u['title'] for u in lc.article_units(md)]


def test_asterisk_and_typo_articles_open_their_own_unit():
    md = ('**ARTÍCULO 34.-** RECIPROCIDAD ALIMENTARIA. Texto.\n\n'
          '**ARTÍULO *35.-** ORIGEN DE LA OBLIGACIÓN. Texto.\n\n'
          'ARTCULO 36.- Texto.\n\nARTICULO *37.- Texto.\n')
    assert _titles(md) == ['Artículo 34', 'Artículo 35', 'Artículo 36', 'Artículo 37']


def test_bullet_and_table_row_articles():
    md = '- **Artículo 167.-** Se impondrán…\n\n|**ARTÍCULO 68.-**Se deroga.|\n'
    assert _titles(md) == ['Artículo 167', 'Artículo 68']


def test_octies_is_a_suffix_not_an_ordinal():
    md = '**Artículo 374.-** Texto.\n\n**Artículo 374 Octies.-** Texto.\n\n**ARTÍCULO 5o.-** Texto.\n'
    assert _titles(md) == ['Artículo 374', 'Artículo 374 Octies', 'Artículo 5o']


def test_letter_after_delimiter_is_text_not_subindex():
    assert _titles('ARTÍCULO 148 bis.- A quien cometa…\n') == ['Artículo 148 bis']


def test_unknown_suffix_word_before_delimiter_is_kept():
    # Erratas reales: "quarter" (quáter), "osties" (octies), "CUARTER", "séptimus".
    md = ('**ARTÍCULO *148 quarter.-** Texto.\n\n**Artículo *455 osties.-** Texto.\n\n'
          '**ARTÍCULO 356 CUARTER.-** Texto.\n\n## **ARTÍCULO *148 séptimus.-** Derogado.\n')
    assert _titles(md) == ['Artículo 148 quarter', 'Artículo 455 osties', 'Artículo 356 CUARTER',
                           'Artículo 148 séptimus']


def test_article_glued_to_structure_heading_is_split():
    md = ('**ARTÍCULO *173.-** ILICITUD. Texto.\n\n'
          '## **CAPÍTULO II DEL DIVORCIO ARTÍCULO *174.-** DEL DIVORCIO. El divorcio disuelve…\n')
    units = {u['title']: u for u in lc.article_units(md)}
    assert list(units) == ['Artículo 173', 'Artículo 174']
    assert units['Artículo 174']['hierarchy'].startswith('CAPÍTULO II DEL DIVORCIO')
    assert 'DIVORCIO' not in units['Artículo 173']['text']


def test_several_bold_articles_in_one_line_are_split():
    md = ('**Artículo 268** .- (Se deroga). **Artículo 269** .- (Se deroga). **Artículo 270** .- (Se deroga).\n\n'
          '**ARTÍCULO 233.-** Texto… en favor de la comunidad. **ARTÍCULO 234.** - Cuando se cause algún daño…\n\n'
          '**Artículo 129.** Derogado. **Artículo 130.** Derogado.\n')
    assert _titles(md) == ['Artículo 268', 'Artículo 269', 'Artículo 270', 'Artículo 233', 'Artículo 234',
                           'Artículo 129', 'Artículo 130']


def test_prose_citations_are_not_split():
    md = ('**Artículo 5.-** Conforme a lo dispuesto en el **artículo 4** del reglamento. '
          'CAPÍTULO I. De conformidad con el artículo 5 de la ley.\n')
    assert _titles(md) == ['Artículo 5']


# ── Encabezado/pie de página repetido en bloque (texto normal, no '#') ──
_MORELOS_HEADER = ('Código Penal para el Estado de Morelos\n\n'
                   'Consejería Jurídica del Poder Ejecutivo del Estado de Morelos. Dirección General de Normatividad.\n\n'
                   'Última Reforma: 02-09-2026\n\n')


def test_repeated_page_header_block_is_removed():
    body = ''.join(f'{_MORELOS_HEADER}**ARTÍCULO {n}.-** Texto del artículo {n}.\n\n' for n in range(1, 8))
    out = lc.clean_document(body)
    assert 'Consejería Jurídica' not in out['clean_text'] and 'Última Reforma' not in out['clean_text']
    assert out['removed_by_reason']['repeated_block'] == 21
    assert all(f'ARTÍCULO {n}.-' in out['clean_text'] for n in range(1, 8))


def test_repeated_legal_sentence_alone_is_kept():
    # Frase de ley repetida SUELTA (no en bloque) no es mobiliario.
    body = ''.join(f'**ARTÍCULO {n}.-** Texto {n}.\n\nEste delito se perseguirá por querella.\n\n' for n in range(1, 9))
    assert lc.clean_document(body)['clean_text'].count('se perseguirá por querella') == 8


def test_repeated_transitorios_block_is_kept():
    # Los transitorios de cada decreto se repiten en bloque, pero son texto legal.
    dec = ('PRIMERA. Remítase el presente Decreto al Titular del Poder Ejecutivo para su publicación.\n\n'
           'SEGUNDA. El presente Decreto entrará en vigor al día siguiente de su publicación.\n\n')
    out = lc.clean_document(dec * 6)['clean_text']
    assert out.count('SEGUNDA. El presente Decreto') == 6


# ── Título del documento en el prefijo "Fuente:" ──
def test_document_title_from_first_heading():
    assert lc.document_title('# **CÓDIGO FAMILIAR PARA EL ESTADO LIBRE Y SOBERANO DE MORELOS**\n\ntexto') == \
        'CÓDIGO FAMILIAR PARA EL ESTADO LIBRE Y SOBERANO DE MORELOS'
    assert lc.document_title('# SE EXPIDE EL CÓDIGO NACIONAL DE PROCEDIMIENTOS PENALES\n') == \
        'CÓDIGO NACIONAL DE PROCEDIMIENTOS PENALES'
    # Títulos internos no son el nombre de la ley.
    assert lc.document_title('# LA LEY PENAL\n\n# TÍTULO PRIMERO\n') is None


def test_source_label_adds_title_only_when_filename_is_not_the_name():
    assert lc._source_label('CPROFAMEM.md', 'CÓDIGO PROCESAL FAMILIAR DE MORELOS') == \
        'CÓDIGO PROCESAL FAMILIAR DE MORELOS (CPROFAMEM.md)'
    assert lc._source_label('Código Penal Federal.md', 'CÓDIGO PENAL FEDERAL') == 'Código Penal Federal.md'
    assert lc._source_label('LEY GENERAL DEL EQUILIBRIO ECOLÓGICO.md', 'LEY GENERAL DEL EQUILIBRIO ECOLOGICO') == \
        'LEY GENERAL DEL EQUILIBRIO ECOLÓGICO.md'   # sin acentos también es el mismo nombre


def test_chunks_of_a_code_carry_the_law_name():
    md = ('# **CÓDIGO PENAL PARA EL ESTADO DE MORELOS**\n\n'
          + ''.join(f'**ARTÍCULO {n}.-** Texto del artículo {n} con varias palabras.\n\n' for n in range(1, 30)))
    df = lc.chunk_documents({'Código PENALEM.md': md})
    assert df.text_for_embedding.str.startswith('Fuente: CÓDIGO PENAL PARA EL ESTADO DE MORELOS (Código PENALEM.md)\n').all()
