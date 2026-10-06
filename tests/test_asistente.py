"""Máquina de estados del asistente de trámites (apps/rewrite_lab/forms/asistente.py), con una IA falsa."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / 'apps' / 'rewrite_lab'
sys.path.insert(0, str(APP))

from forms import asistente as A  # noqa: E402

SPEC = {
    'id': 'f', 'titulo': 'Formulario de prueba', 'tema': 't', 'estado': 'publicado', 'descripcion': 'd',
    'campos': [
        {'id': 'nombre', 'pregunta': '¿Nombre?', 'tipo': 'texto'},
        {'id': 'hijos_si', 'pregunta': '¿Hijos?', 'tipo': 'si_no'},
        {'id': 'hijos', 'si': 'hijos_si', 'pregunta': '¿Cuáles?', 'tipo': 'lista', 'subcampos': [{'id': 'nombre', 'tipo': 'texto'}]},
        {'id': 'regimen', 'pregunta': '¿Régimen?', 'tipo': 'opcion', 'opciones': {'sc': 'Sociedad conyugal', 'sb': 'Separación'}},
        {'id': 'apodo', 'pregunta': '¿Apodo?', 'tipo': 'texto', 'obligatorio': False},
        {'id': 'fecha_firma', 'automatico': 'hoy', 'tipo': 'fecha'},
    ],
    '_plantilla': 'Yo, {nombre}.[SI hijos_si] Hijos:[CADA h EN hijos] {h.nombre}[/CADA].[/SI] Régimen {regimen}. {fecha_firma}',
}
CAT = {'f': SPEC}


class FakeIA:
    def __init__(self, extraer=None, elegir='f'):
        self._extraer, self._elegir, self.dudas = extraer or {}, elegir, []

    def elegir_formulario(self, catalogo, texto):
        return self._elegir, {'fake': True}

    def extraer(self, spec, campos, texto, actual, conocidas=None):
        return dict(self._extraer.get(texto, {})), {'fake': texto}

    def responder_duda(self, spec, texto):
        self.dudas.append(texto)
        return 'respuesta del RAG', {}


def run(steps, ia=None):
    b, ia = None, ia or FakeIA()
    for s in steps:
        b, v = A.turno(b, CAT, ia, **s)
    return b, v


def test_full_happy_path_with_buttons_and_quick_answers():
    b, v = run([{'evento': 'elegir:f'}])
    assert b['estado'] == A.TRIAJE and v['triaje']['titulo'] == 'Formulario de prueba'
    b, v = run([{'evento': 'elegir:f'}, {'evento': 'aplica'}])
    assert b['estado'] == A.ENTREVISTA and v['campo']['id'] == 'nombre'
    b, v = run([{'evento': 'elegir:f'}, {'evento': 'aplica'}, {'mensaje': 'Ana López'}, {'mensaje': 'no'},
                {'mensaje': 'Separación'}, {'evento': 'omitir'}])
    assert b['estado'] == A.REVISION, b
    assert b['respuestas'] == {'nombre': 'Ana López', 'hijos_si': False, 'regimen': 'sb'} and b['omitidos'] == ['apodo']
    assert [r['id'] for r in v['resumen']] == ['nombre', 'hijos_si', 'regimen', 'apodo']   # 'hijos' no aplica
    b, v = A.turno(b, CAT, FakeIA(), evento='confirmar')
    assert b['estado'] == A.DOCUMENTO and v['documento'].startswith('Yo, Ana López. Régimen sb.') and v['faltan'] == []


def test_conditional_field_is_asked_only_when_it_applies():
    ia = FakeIA({'Luis y Eva': {'hijos': [{'nombre': 'Luis'}, {'nombre': 'Eva'}]}})
    b, v = run([{'evento': 'elegir:f'}, {'evento': 'aplica'}, {'mensaje': 'Ana'}, {'mensaje': 'sí'}], ia)
    assert v['campo']['id'] == 'hijos'
    b, v = A.turno(b, CAT, ia, mensaje='Luis y Eva')
    assert b['respuestas']['hijos'] == [{'nombre': 'Luis'}, {'nombre': 'Eva'}] and v['campo']['id'] == 'regimen'


def test_free_text_can_fill_several_fields_at_once():
    ia = FakeIA({'Soy Ana, sin hijos, separación de bienes': {'nombre': 'Ana', 'hijos_si': False, 'regimen': 'sb'}})
    b, v = run([{'evento': 'elegir:f'}, {'evento': 'aplica'}, {'mensaje': 'Soy Ana, sin hijos, separación de bienes'}], ia)
    assert b['respuestas'] == {'nombre': 'Ana', 'hijos_si': False, 'regimen': 'sb'} and v['campo']['id'] == 'apodo'


def test_legal_question_goes_to_rag_and_repeats_the_same_question():
    ia = FakeIA({'¿qué es la sociedad conyugal?': {'_es_duda': True}})
    b, v = run([{'evento': 'elegir:f'}, {'evento': 'aplica'}, {'mensaje': 'Ana'}, {'mensaje': 'no'},
                {'mensaje': '¿qué es la sociedad conyugal?'}], ia)
    assert ia.dudas == ['¿qué es la sociedad conyugal?'] and v['mensaje'] == 'respuesta del RAG'
    assert b['estado'] == A.ENTREVISTA and v['campo']['id'] == 'regimen' and v['repetir']


def test_invalid_option_does_not_advance():
    b, v = run([{'evento': 'elegir:f'}, {'evento': 'aplica'}, {'mensaje': 'Ana'}, {'mensaje': 'no'}, {'mensaje': 'quién sabe'}])
    assert v['campo']['id'] == 'regimen' and 'Elige una de las opciones' in v['mensaje']


def test_review_correction_returns_to_review():
    b, v = run([{'evento': 'elegir:f'}, {'evento': 'aplica'}, {'mensaje': 'Ana'}, {'mensaje': 'no'},
                {'mensaje': 'sc'}, {'evento': 'omitir'}])
    b, v = A.turno(b, CAT, FakeIA(), evento='corregir', campo='nombre')
    assert b['estado'] == A.ENTREVISTA and v['campo']['id'] == 'nombre'
    b, v = A.turno(b, CAT, FakeIA(), mensaje='Ana María')
    assert b['estado'] == A.REVISION and b['respuestas']['nombre'] == 'Ana María' and b['corrigiendo'] is None


def test_correction_that_opens_new_questions():
    b, _ = run([{'evento': 'elegir:f'}, {'evento': 'aplica'}, {'mensaje': 'Ana'}, {'mensaje': 'no'},
                {'mensaje': 'sc'}, {'evento': 'omitir'}])
    b, v = A.turno(b, CAT, FakeIA({'sí tenemos hijos': {'hijos_si': True}}), mensaje='sí tenemos hijos')
    assert b['estado'] == A.ENTREVISTA and v['campo']['id'] == 'hijos'


def test_triage_rejection_and_restart():
    b, v = run([{'evento': 'elegir:f'}, {'evento': 'no_aplica'}])
    assert b['estado'] == A.INICIO and b['formulario'] is None
    b, v = run([{'evento': 'elegir:f'}, {'evento': 'aplica'}, {'evento': 'reiniciar'}])
    assert b['estado'] == A.INICIO and b['transicion']['evento'] == 'reiniciar'


def test_free_text_at_start_uses_llm_to_choose_and_keeps_context():
    ia = FakeIA({'me quiero divorciar, soy Ana': {'nombre': 'Ana'}})
    b, v = run([{'mensaje': 'me quiero divorciar, soy Ana'}], ia)
    assert b['estado'] == A.TRIAJE and b['contexto'] == 'me quiero divorciar, soy Ana'
    b, v = A.turno(b, CAT, ia, evento='aplica')
    assert b['respuestas'] == {'nombre': 'Ana'} and v['campo']['id'] == 'hijos_si'   # el nombre ya no se pregunta


def test_unknown_form_and_invalid_transitions():
    b, v = run([{'mensaje': 'quiero un amparo'}], FakeIA(elegir=None))
    assert b['estado'] == A.INICIO and 'No encontré' in v['mensaje']
    with pytest.raises(ValueError):
        A.transicion({'estado': A.INICIO}, 'confirmar')


def test_debug_panel_shows_state_and_transition():
    b, v = run([{'evento': 'elegir:f'}, {'evento': 'aplica'}])
    d = v['debug']
    assert d['estado'] == A.ENTREVISTA and d['transicion'] == {'de': A.TRIAJE, 'evento': 'aplica', 'a': A.ENTREVISTA,
                                                              'motivo': 'la persona confirmó que es su caso'}
    assert d['siguiente_campo'] == 'nombre' and d['pendientes'][:2] == ['nombre', 'hijos_si']


def test_optional_field_negative_answer_means_skip():
    b, v = run([{'evento': 'elegir:f'}, {'evento': 'aplica'}, {'mensaje': 'Ana'}, {'mensaje': 'no'},
                {'mensaje': 'sc'}, {'mensaje': 'no me acuerdo'}])
    assert b['omitidos'] == ['apodo'] and 'apodo' not in b['respuestas'] and b['estado'] == A.REVISION


def test_question_without_data_goes_to_rag_even_if_llm_does_not_flag_it():
    ia = FakeIA()   # la IA falsa no marca _es_duda
    b, v = run([{'evento': 'elegir:f'}, {'evento': 'aplica'}, {'mensaje': 'Ana'}, {'mensaje': 'no'},
                {'mensaje': '¿Cuál me conviene?'}], ia)
    assert ia.dudas == ['¿Cuál me conviene?'] and v['campo']['id'] == 'regimen'


def test_answer_that_opens_new_fields_is_reread_for_them():
    class IA2(FakeIA):
        def extraer(self, spec, campos, texto, actual, conocidas=None):
            if texto != 'sí, tenemos dos: Ana y Luis':
                return {}, {}
            ids = {c['id'] for c in campos}
            if 'hijos' in ids:
                return {'hijos': [{'nombre': 'Ana'}, {'nombre': 'Luis'}]}, {}
            return {'hijos_si': True}, {}
    b, v = run([{'evento': 'elegir:f'}, {'evento': 'aplica'}, {'mensaje': 'Eva'},
                {'mensaje': 'sí, tenemos dos: Ana y Luis'}], IA2())
    assert b['respuestas']['hijos'] == [{'nombre': 'Ana'}, {'nombre': 'Luis'}] and v['campo']['id'] == 'regimen'
