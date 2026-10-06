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
    def revisar_partes(self, campo, valor, partes):   # por defecto: Gemma diría que falta todo lo dudoso
        return list(partes), {}

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


SPEC2 = {'id': 'g', 'titulo': 'G', 'tema': 't', 'estado': 'publicado', 'descripcion': 'd', '_plantilla': '{dom} {tel}',
         'campos': [{'id': 'dom', 'pregunta': '¿Domicilio?', 'tipo': 'texto',
                     'requiere': ['calle y número', 'colonia', 'código postal']},
                    {'id': 'tel', 'pregunta': '¿Teléfono?', 'tipo': 'texto', 'formato': 'telefono'}]}


def test_incomplete_answer_asks_for_missing_parts_then_completes():
    ia = FakeIA({'Roble 5': {'dom': 'Roble 5'},
                 'Roble 5, Col. Del Valle CP 03100': {'dom': 'Roble 5, Col. Del Valle, C.P. 03100'}})
    cat = {'g': SPEC2}
    b, v = A.turno(None, cat, ia, evento='elegir:g'); b, v = A.turno(b, cat, ia, evento='aplica')
    b, v = A.turno(b, cat, ia, mensaje='Roble 5')
    assert v['campo']['id'] == 'dom' and 'colonia y código postal' in v['mensaje'] and 'dom' not in b['respuestas']
    assert {'evento': 'aceptar_incompleto', 'texto': 'Dejarlo así'} in v['botones']
    b, v = A.turno(b, cat, ia, mensaje='Col. Del Valle CP 03100')   # se junta con lo anterior
    assert b['respuestas']['dom'] == 'Roble 5, Col. Del Valle, C.P. 03100' and b['incompleto'] is None and v['campo']['id'] == 'tel'


def test_incomplete_answer_can_be_left_as_is():
    ia = FakeIA({'Roble 5': {'dom': 'Roble 5'}})
    cat = {'g': SPEC2}
    b, v = A.turno(None, cat, ia, evento='elegir:g'); b, v = A.turno(b, cat, ia, evento='aplica')
    b, v = A.turno(b, cat, ia, mensaje='Roble 5')
    b, v = A.turno(b, cat, ia, evento='aceptar_incompleto')
    assert b['respuestas']['dom'] == 'Roble 5' and v['campo']['id'] == 'tel'


def test_format_checks_without_llm():
    assert A.faltan_formato({'formato': 'telefono'}, '55 1234 5678') == []
    assert A.faltan_formato({'formato': 'telefono'}, '+52 55 1234 5678') == []
    assert A.faltan_formato({'formato': 'telefono'}, '1234 5678') != []
    assert A.faltan_formato({'formato': 'correo'}, 'ana@example.com') == []
    assert A.faltan_formato({'formato': 'correo'}, 'ana@example') != []
    assert A.faltan_formato({'formato': 'fecha_completa'}, '3 de marzo de 2015') == []
    assert A.faltan_formato({'formato': 'fecha_completa'}, '30 de noviembre') == ['el año']
    assert A.faltan_formato({'formato': 'fecha_completa'}, '2015') == ['el día y el mes']
    dom = {'requiere': ['calle y número', 'colonia', 'alcaldía o municipio', 'código postal']}
    sin_ia = A.faltan_partes(dom, 'Calle Roble 5')[0]          # sin IA, solo lo seguro
    assert sin_ia == ['código postal']
    class IA4(FakeIA):
        def revisar_partes(self, campo, valor, partes):
            return [p for p in partes if p == 'colonia' and 'Narvarte' not in valor] + \
                   [p for p in partes if p == 'alcaldía o municipio'], {}
    assert A.faltan_partes(dom, 'Calle Roble 5', IA4())[0] == ['colonia', 'alcaldía o municipio', 'código postal']
    assert A.faltan_partes(dom, 'Roble 5, Col. Del Valle, Benito Juárez, C.P. 03100', IA4())[0] == []
    assert A.faltan_partes(dom, 'Av. Universidad 100, Narvarte, Alcaldía Benito Juárez, 03020', IA4())[0] == []


def test_unknown_required_parts_are_checked_by_the_llm():
    class IA3(FakeIA):
        def revisar_partes(self, campo, valor, partes):
            return ['número de acta', 'inventada'], {}
    faltan, _ = A.faltan_partes({'requiere': ['juzgado', 'número de acta']}, 'Juzgado 14', IA3())
    assert faltan == ['número de acta']   # lo que Gemma invente fuera de la lista se ignora


def test_format_fields_replace_instead_of_merging():
    cat = {'g': SPEC2}
    ia = FakeIA({'Roble 5, Col. Centro, 06000': {'dom': 'Roble 5, Col. Centro, 06000'}})
    b, v = A.turno(None, cat, ia, evento='elegir:g'); b, v = A.turno(b, cat, ia, evento='aplica')
    b, v = A.turno(b, cat, ia, mensaje='Roble 5, Col. Centro, 06000')
    b, v = A.turno(b, cat, ia, mensaje='55 1234')
    assert b['incompleto']['campo'] == 'tel'
    b, v = A.turno(b, cat, ia, mensaje='55 1234 5678')
    assert b['respuestas']['tel'] == '55 1234 5678' and b['incompleto'] is None


def test_llm_object_values_become_text():
    assert A.normalizar({'tipo': 'texto'}, {'texto': 'Av. Universidad 100'}) == ('Av. Universidad 100', None)
    assert A.normalizar({'tipo': 'texto'}, ['Calle 1', 'Col. Centro']) == ('Calle 1, Col. Centro', None)


def test_same_address_reference_uses_known_address_or_asks_which():
    spec = {'id': 'h', 'titulo': 'H', 'tema': 't', 'estado': 'publicado', 'descripcion': 'd', '_plantilla': '{a}{b}{c}',
            'campos': [{'id': 'a', 'pregunta': 'a', 'tipo': 'texto', 'requiere': ['código postal']},
                       {'id': 'b', 'pregunta': 'b', 'tipo': 'texto', 'requiere': ['código postal']},
                       {'id': 'c', 'pregunta': 'c', 'tipo': 'texto', 'requiere': ['código postal']}]}
    cat = {'h': spec}
    b = {**A.nuevo_borrador(), 'estado': A.ENTREVISTA, 'formulario': 'h', 'respuestas': {'a': 'Roble 5, 03100'}}
    b, v = A.turno(b, cat, FakeIA(), mensaje='en mi casa')          # un solo domicilio conocido → se usa
    assert b['respuestas']['b'] == 'Roble 5, 03100'
    b['respuestas']['b'] = 'Pino 8, 04100'
    b, v = A.turno(b, cat, FakeIA(), mensaje='en mi casa')          # varios → pregunta cuál
    assert v['mensaje'] == '¿Cuál de estos domicilios?' and [x['texto'] for x in v['botones']] == ['Roble 5, 03100', 'Pino 8, 04100']
    b, v = A.turno(b, cat, FakeIA(), mensaje='Pino 8, 04100')
    assert b['respuestas']['c'] == 'Pino 8, 04100'
