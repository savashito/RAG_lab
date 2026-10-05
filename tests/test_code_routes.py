"""Detección de códigos mencionados en un texto (routing por código y gold del benchmark)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.code_routes import codes_in, fold, short_label  # noqa: E402


def labels(text):
    return [h['label'] for h in codes_in(text)]


def test_fold_accents_case_and_signs():
    assert fold('¿Querétaro, CDMX?') == 'queretaro cdmx'


def test_entities_and_codes_in_order():
    assert labels('¿Qué artículos regulan el feminicidio en Ciudad de México y Querétaro?') == ['CDMX', 'Querétaro']
    assert labels('Según el CNPP y el Código Penal Federal') == ['CNPP', 'CPF']
    assert labels('Código Penal para el Distrito Federal') == ['CDMX']
    assert labels('en el Estado de México (Edomex)') == ['CPEM']


def test_accents_and_case_do_not_matter():
    assert labels('en queretaro') == ['Querétaro']
    assert labels('EN LA CIUDAD DE MEXICO') == ['CDMX']


def test_one_typo_in_long_words():
    assert labels('en Queretro') == ['Querétaro']
    assert labels('en el Distito Federal') == ['CDMX']
    assert labels('Codigo Penal Fedral') == ['CPF']


def test_no_false_positives_from_typo_tolerance():
    assert labels('los modelos de imputación') == []          # "morelos" ≈ "modelos": no, es palabra corta
    assert labels('Constitución Política de los Estados Unidos Mexicanos') == []
    assert labels('el delito de secuestro exprés') == []      # el delito no es la ley
    assert labels('CPFM y CPE') == []                          # las siglas no se aproximan (CPFM ≠ CPF)


def test_longest_alias_wins_on_overlap():
    assert labels('Código Procesal Familiar para el Estado de Morelos') == ['CPFM', 'Morelos']
    assert labels('Código Nacional de Procedimientos Civiles y Familiares') == ['CNPCF']


def test_general_laws_by_name_not_by_crime():
    assert labels('Ley General para Prevenir y Sancionar los Delitos en Materia de Secuestro') == ['LGSecuestro']
    assert labels('artículo 12 de la Ley General en Materia de Extorsión') == ['LGExtorsión']
    assert labels('la Ley Federal contra la Delincuencia Organizada') == ['LFCDO']


def test_match_keeps_original_text_and_position():
    h = codes_in('Fundamento en Querétaro')[0]
    assert h['match'] == 'Querétaro' and h['start'] == 14
    assert short_label('Código Penal Federal.md') == 'CPF' and short_label(None) == '?'
