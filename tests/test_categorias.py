"""
Pruebas de la validación de 👤 Categorías de la persona (apps/rewrite_lab/categorias.py), sin base de datos.

    uv run --all-extras --with pytest python -m pytest tests/test_categorias.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps' / 'rewrite_lab'))

import categorias as ct  # noqa: E402


def test_normaliza_nombre_y_valores():
    c = ct.normalizar_categoria({'nombre': '  Sexo   de la persona ', 'valores': 'mujer, hombre, , Mujer, No lo dijo',
                                 'descripcion': ' La persona lo dice. '})
    assert c == {'nombre': 'Sexo de la persona', 'descripcion': 'La persona lo dice.', 'valores': ['mujer', 'hombre']}
    assert ct.normalizar_categoria({'nombre': 'Edad', 'valores': ['menor de 18', '18 o más']})['valores'] == ['menor de 18', '18 o más']


@pytest.mark.parametrize('b, motivo', [
    ({'nombre': '', 'valores': ['a']}, 'nombre'),
    ({'nombre': 'Sexo', 'valores': []}, 'al menos un valor'),
    ({'nombre': 'Sexo', 'valores': ['no lo dijo']}, 'al menos un valor'),   # implícito: no cuenta como valor
    ({'nombre': 'Sexo', 'valores': ['x' * 61]}, 'muy largo'),
    ({'nombre': 'Sexo', 'valores': [str(i) for i in range(21)]}, 'Máximo 20'),
])
def test_rechaza_categorias_invalidas(b, motivo):
    with pytest.raises(ValueError, match=motivo):
        ct.normalizar_categoria(b)


def test_etiquetas_solo_valores_existentes_y_sin_repetir():
    cats = {1: {'nombre': 'Sexo', 'valores': ['mujer', 'hombre']}, 2: {'nombre': 'Edad', 'valores': ['menor de 18']}}
    pares = ct.normalizar_etiquetas([{'categoria_id': 1, 'valor': 'mujer'}, {'categoria_id': '1', 'valor': 'mujer'},
                                     {'categoria_id': 2, 'valor': 'menor de 18'}], cats)
    assert pares == [(1, 'mujer'), (2, 'menor de 18')]
    assert ct.normalizar_etiquetas([], cats) == []   # sin marcas = aplica a todas las personas
    with pytest.raises(ValueError, match='no es un valor'):
        ct.normalizar_etiquetas([{'categoria_id': 1, 'valor': 'no lo dijo'}], cats)
    with pytest.raises(ValueError, match='No existe'):
        ct.normalizar_etiquetas([{'categoria_id': 9, 'valor': 'mujer'}], cats)
