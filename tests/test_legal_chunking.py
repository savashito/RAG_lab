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
