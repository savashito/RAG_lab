"""
Pruebas de la compuerta de jurisdicción (apps/rewrite_lab/jurisdiction_gate.py) con un LLM falso:
qué lugares puede ver la búsqueda y qué nota recibe el LLM que responde.

    uv run --all-extras --with pytest python -m pytest tests/test_jurisdiction_gate.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps' / 'rewrite_lab'))

import jurisdiction_gate as jg  # noqa: E402

DISP = {'Ciudad de México': 'cdmx', 'Estado de México': 'edomex', 'Querétaro': 'queretaro', 'Morelos': 'morelos'}
NO_EST = ['federal', 'nacional', 'general']


class FakeLLM:
    def __init__(self, out):
        self.out = out

    def chat(self, *a, **k):
        if isinstance(self.out, Exception):
            raise self.out
        return self.out if isinstance(self.out, str) else json.dumps(self.out)


def test_normalizar_estado():
    assert jg.normalizar_estado('queretaro') == 'Querétaro'
    assert jg.normalizar_estado('CDMX') == 'Ciudad de México'
    assert jg.normalizar_estado('Edo. Mex.') == 'Estado de México'
    assert jg.normalizar_estado('Nuevo Leon') == 'Nuevo León'
    for x in ('Texas', '', None, 'Toluca', 'Federal'):
        assert jg.normalizar_estado(x) is None


def test_sin_lugar_no_ve_codigos_estatales_y_pide_estado():
    g = jg.decidir('Me robaron el celular, ¿qué pena tiene?', FakeLLM({'lugares': [], 'comparar': False}), DISP, NO_EST)
    assert g['estados'] == [] and g['jurisdictions'] == NO_EST
    assert 'pregunta en qué estado' in g['nota']


def test_ciudad_se_resuelve_a_su_estado():
    llm = FakeLLM({'lugares': [{'texto': 'Toluca', 'estado': 'Estado de México'}], 'comparar': False})
    g = jg.decidir('Me asaltaron en Toluca', llm, DISP, NO_EST)
    assert g['en_base'] == ['Estado de México'] and g['jurisdictions'] == NO_EST + ['edomex']
    assert '«Toluca»' in g['nota'] and 'No vuelvas a preguntar' in g['nota']


def test_comparacion_incluye_cada_estado():
    llm = FakeLLM('```json\n{"lugares": [{"texto": "CDMX", "estado": "CDMX"}, {"texto": "Querétaro", "estado": "Querétaro"}], "comparar": true}\n```')
    g = jg.decidir('Compara el robo en CDMX y Querétaro', llm, DISP, NO_EST)
    assert g['en_base'] == ['Ciudad de México', 'Querétaro'] and g['comparar']
    assert set(g['jurisdictions']) == set(NO_EST) | {'cdmx', 'queretaro'}
    assert 'CADA uno' in g['nota']


def test_estado_fuera_del_corpus():
    llm = FakeLLM({'lugares': [{'texto': 'Puebla', 'estado': 'Puebla'}], 'comparar': False})
    g = jg.decidir('Me amenazaron en Puebla', llm, DISP, NO_EST)
    assert g['faltan'] == ['Puebla'] and g['jurisdictions'] == NO_EST
    assert 'NO está en los documentos' in g['nota']


def test_respaldo_regex_si_el_llm_falla_o_omite():
    g = jg.decidir('¿Qué dice el Código Penal de Querétaro sobre el robo?', FakeLLM(TimeoutError('x')), DISP, NO_EST)
    assert g['fuente'] == 'regex' and g['en_base'] == ['Querétaro']
    g = jg.decidir('Robo en Morelos', FakeLLM('no sé'), DISP, NO_EST)
    assert g['en_base'] == ['Morelos']
    # el LLM no lo vio, la regex sí: se suma
    g = jg.decidir('Compara CDMX con Morelos', FakeLLM({'lugares': [{'texto': 'CDMX', 'estado': 'Ciudad de México'}]}), DISP, NO_EST)
    assert g['en_base'] == ['Ciudad de México', 'Morelos']


def test_estado_inventado_por_el_llm_se_descarta():
    g = jg.decidir('Me robaron en mi casa', FakeLLM({'lugares': [{'texto': 'mi casa', 'estado': 'Gotham'}]}), DISP, NO_EST)
    assert g['estados'] == [] and 'no se pudo saber de qué estado' in g['nota']
