"""
Pruebas de shared/chunk_diagnostics.py: los avisos que se muestran al ingerir y en
«🔍 Revisar chunking» (Ingesta → Corpus actual).

    uv run --all-extras --with pytest python -m pytest tests/test_chunk_diagnostics.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.chunk_diagnostics import body_of, diagnose_chunks  # noqa: E402


def art(n, text=None, part=1, pos=None, title=None):
    body = text if text is not None else f'**ARTÍCULO {n}.-** ' + 'palabra ' * 30
    return {'title': title or f'Artículo {n}', 'unit_type': 'article', 'part': part, 'position': pos or int(str(n).split()[0]),
            'text': f'Fuente: x.md\nSección: LIBRO > Artículo {n}\n\n{body}'}


def check(d, cid):
    return next(c for c in d['checks'] if c['id'] == cid)


def test_body_of_strips_embedding_prefix():
    assert body_of('Fuente: a.md\nSección: X > Y\n\nTexto') == 'Texto'


def test_healthy_code_is_ok():
    d = diagnose_chunks([art(n) for n in range(1, 15)])
    assert d['status'] == 'ok' and d['stats']['looks_like_code']


def test_glued_asterisk_article_is_detected_with_gap():
    # El 35 ("ARTÍCULO *35") quedó dentro del chunk del 34: el chunker viejo no lo reconocía.
    glued = art(34, '**ARTÍCULO 34.-** Texto.\n\n**ARTÍCULO *35.-** ORIGEN. ' + 'palabra ' * 30)
    d = diagnose_chunks([art(n) for n in range(20, 34)] + [glued] + [art(n) for n in range(36, 40)])
    assert check(d, 'pegados')['level'] == 'bad'
    assert check(d, 'pegados')['examples'][0]['article'] == '35'
    gap = check(d, 'secuencia')['examples'][0]
    assert gap['article'] == 35 and 'Artículo 34' in gap['detail']
    assert any('35' in m for msgs in d['flags'].values() for m in msgs)   # chunk marcado para revisar


def test_code_split_by_headings_is_bad():
    text = '\n\n'.join(f'**ARTÍCULO {n}.-** texto corto.' for n in range(1, 40))
    chunks = [{'title': 'VIOLACIÓN', 'unit_type': 'heading', 'part': 1, 'position': 1, 'text': text}]
    assert check(diagnose_chunks(chunks), 'estrategia')['level'] == 'bad'


def test_label_mismatch_and_duplicates():
    chunks = [art(n) for n in range(1, 15)] + [art(16, title='Artículo 15'), art(16), art(17), art(17, pos=18)]
    d = diagnose_chunks(chunks)
    assert check(d, 'etiqueta')['examples'][0]['label'] == 'Artículo 15'
    assert [e['article'] for e in check(d, 'duplicados')['examples']] == ['17']


def test_ordinals_and_suffixes_match_titles():
    chunks = [art(n) for n in range(1, 12)] + [
        art('12', '**Artículo 12o.-** ' + 'p ' * 30, title='Artículo 12o'),
        art('12 Bis', '**Artículo 12 Bis.-** ' + 'p ' * 30, title='Artículo 12 Bis', pos=12),
        art('12 Octies', '**Artículo 12 Octies.-** ' + 'p ' * 30, title='Artículo 12 Octies', pos=12),
        art('148 séptimus', '## **ARTÍCULO *13 séptimus.-** Derogado.', title='Artículo 13 séptimus', pos=13)]
    d = diagnose_chunks(chunks)
    assert check(d, 'etiqueta')['level'] == 'ok', check(d, 'etiqueta')
    assert check(d, 'pegados')['level'] == 'ok'
    assert check(d, 'duplicados')['level'] == 'ok'


def test_repeated_header_lines_warn_but_reform_notes_do_not():
    hdr = 'Consejería Jurídica del Poder Ejecutivo del Estado de Morelos'
    chunks = [art(n, f'**ARTÍCULO {n}.-** texto\n\n{hdr}\n\nPárrafo reformado DOF 03-01-2017') for n in range(1, 15)]
    rep = check(diagnose_chunks(chunks), 'repetido')
    assert rep['level'] == 'warn'
    assert [e['line'] for e in rep['examples']] == [hdr]


def test_transitorio_restart_is_not_a_gap():
    chunks = [art(n) for n in range(1, 15)] + [art(1, pos=100), art(2, pos=101)]
    assert check(diagnose_chunks(chunks), 'secuencia')['level'] == 'ok'
