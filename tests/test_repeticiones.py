"""
Pruebas de los cálculos de la página 🔁 Ronda 1 real (apps/rewrite_lab/repeticiones.py), sin base de datos.

    uv run --all-extras --with pytest python -m pytest tests/test_repeticiones.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps' / 'rewrite_lab'))

import repeticiones as rp  # noqa: E402


def turno(otro=(), ley=True, pide=False, filtro=None):
    return {'analisis': {'otro_codigo_estatal': list(otro), 'cita_ley_gold': ley, 'cita_articulo_gold': False,
                         'pide_lugar_estricto': pide}, 'filtro': filtro, 'segundos': 10.0}


def test_resumir_separa_primer_mensaje_y_lo_que_sabia_el_filtro():
    sin = {'estados': [], 'tipo': 'delito_comun'}
    qro = {'estados': ['Querétaro']}
    convs = [{'intento_id': 1, 'turnos': [turno(pide=True, filtro=sin), turno(filtro=qro)]},
             {'intento_id': 2, 'turnos': [turno(otro=['CDMX'], ley=False, filtro=qro)]}]
    r = rp.resumir(convs)
    assert r['primer.otro_codigo'] == {'pct': 50.0, 'n': 2} and r['primer.ley_correcta']['pct'] == 50.0
    assert r['primer.pide_sin_estado'] == {'pct': 100.0, 'n': 1}       # no sabía el estado y lo pidió
    assert r['primer.repregunta'] == {'pct': 0.0, 'n': 1}              # ya lo sabía y no lo volvió a pedir
    assert r['siguientes.otro_codigo'] == {'pct': 0.0, 'n': 1} and r['conversaciones'] == 2
    sin_filtro = rp.resumir([{'intento_id': 3, 'turnos': [turno()]}])
    assert 'primer.pide_sin_filtro' in sin_filtro and 'primer.repregunta' not in sin_filtro


def test_por_conversacion_promedia_repeticiones():
    convs = [{'intento_id': 1, 'turnos': [turno(otro=['CDMX'])]}, {'intento_id': 1, 'turnos': [turno()]},
             {'intento_id': 2, 'turnos': [turno(), turno(otro=['CPEM']), turno()]}]
    assert rp.por_conversacion(convs, 'primer', 'otro_codigo') == {1: 0.5, 2: 0}
    assert rp.por_conversacion(convs, 'siguientes', 'otro_codigo') == {2: 0.5}   # 1 de 2 mensajes siguientes
