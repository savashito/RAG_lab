"""Máquina de estados de la consulta (apps/rewrite_lab/consulta/), con una IA falsa y el catálogo real."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / 'apps' / 'rewrite_lab'
sys.path.insert(0, str(APP))

from consulta import catalogo as C  # noqa: E402
from consulta import expediente as E  # noqa: E402
from consulta import ia as IA  # noqa: E402
from consulta import maquina as M  # noqa: E402

CAT, MD5 = C.cargar()


class IAFalsa:
    """Clasifica con `tipos`/`opciones` fijos y extrae, por cada mensaje, lo que diga `respuestas[texto del mensaje]`."""

    def __init__(self, tipos=('imagenes_intimas',), opciones=(), respuestas=None):
        self.tipos, self.opciones, self.respuestas = list(tipos), list(opciones), respuestas or {}
        self.clasificaciones = 0

    def clasificar_caso(self, texto, catalogo):
        self.clasificaciones += 1
        return {'tipos': self.tipos, 'opciones': self.opciones, '_llamada': {'tarea': 'clasificar_caso'}}

    def extraer_hechos(self, texto, pregunta, datos):
        ultimo = texto.split('\n')[-1]
        pedidos = {d['id'] for d in datos}
        return {'datos': {k: v for k, v in self.respuestas.get(ultimo, {}).items() if k in pedidos},
                '_llamada': {'tarea': 'extraer_hechos'}}


def conversar(ia, mensajes, estado=None, exp=None):
    """Manda los mensajes uno por uno; devuelve la lista de (estado, expediente, salida, registro)."""
    historial, out = [], []
    for m in mensajes:
        estado, exp, salida, reg = M.turno(estado, exp, {'tipo': 'mensaje', 'texto': m, 'historial': historial}, CAT, ia)
        historial += [{'role': 'user', 'content': m}, {'role': 'assistant', 'content': salida.get('texto', '…')}]
        out.append((estado, exp, salida, reg))
    return out


# ── evaluar ───────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize('expr,datos,esperado', [
    ('pide_dinero = si', {'pide_dinero': 'si'}, True),
    ('pide_dinero = si', {'pide_dinero': 'no'}, False),
    ('pide_dinero = si', {}, None),
    ('pide_dinero = si', {'pide_dinero': 'no_sabe'}, None),
    ('NO pide_dinero', {'pide_dinero': 'no'}, True),
    ('pide_dinero', {'pide_dinero': 'si'}, True),
    ('edad_victima < 18', {'edad_victima': 15}, True),
    ('edad_victima < 18', {'edad_victima': 24}, False),
    ('edad_victima >= 18', {'edad_victima': 18}, True),
    ('relacion_partes en [pareja_o_expareja, familiar]', {'relacion_partes': 'familiar'}, True),
    ('lugar_hechos = Querétaro', {'lugar_hechos': 'Querétaro'}, True),
])
def test_evaluar(expr, datos, esperado):
    assert E.evaluar(expr, datos) is esperado


def test_evaluar_rechaza_basura():
    with pytest.raises(ValueError):
        E.evaluar('pide dinero ?? 3', {})


# ── catálogo ──────────────────────────────────────────────────────────────────────
def test_catalogo_real_es_valido():
    assert {'lugar_hechos', 'papel'} <= {d['id'] for d in CAT['datos']}
    assert all(d.get('tipo') in C.TIPOS_DATO for d in CAT['datos'])
    assert len(MD5) == 32


def test_catalogo_rechaza_condicion_con_dato_inexistente():
    r = {**CAT['reglas'][0], 'cuando': ['color_de_ojos = azul']}
    with pytest.raises(ValueError, match='no existe'):
        C.validar_entrada('reglas', r, CAT)


# ── expediente ────────────────────────────────────────────────────────────────────
def test_combinar_normaliza_y_reporta_cambios():
    exp, cambios = E.combinar(E.nuevo(), {'pide_dinero': 'Sí', 'edad_victima': '24 años', 'inventado': 1}, CAT)
    assert exp['datos'] == {'pide_dinero': 'si', 'edad_victima': 24} and set(cambios) == {'pide_dinero', 'edad_victima'}


def test_no_sabe_no_vale_para_el_lugar():
    exp, _ = E.combinar(E.nuevo(), {'lugar_hechos': 'no sé', 'monto': 'no sé'}, CAT)
    assert exp['no_sabe'] == ['monto'] and 'lugar_hechos' not in exp['datos']


def test_faltan_primero_los_generales():
    exp = {**E.nuevo(), 'tipos_caso': ['imagenes_intimas']}
    ids = [d['id'] for d in E.datos_faltantes(exp, CAT)]
    assert ids[:2] == ['lugar_hechos', 'papel'] and 'pide_dinero' in ids


# ── máquina de estados ────────────────────────────────────────────────────────────
FOTOS = {
    'Me escribe alguien que conocí en una app: si no le deposito 5,000 pesos publica mis fotos íntimas':
        {'pide_dinero': 'si', 'medio_digital': 'si'},
    'En Querétaro': {'lugar_hechos': 'Querétaro'},
    'A mí': {'papel': 'victima'},
    'No, todavía no': {'ya_difundido': 'no'},
    'Tengo 24': {'edad_victima': 24},
    'Sí, yo se las mandé': {'consentimiento': 'si'},
    'Sí': {'victima_mujer': 'si'},
}


def test_no_orienta_hasta_tener_los_datos_y_luego_orienta():
    pasos = conversar(IAFalsa(respuestas=FOTOS), list(FOTOS))
    for estado, _, salida, _ in pasos[:-1]:
        assert estado == M.LLENAR_EXPEDIENTE and salida['tipo'] == 'pregunta'
    assert pasos[0][2]['dato'] == 'lugar_hechos'        # lo primero que pregunta es el lugar
    estado, exp, salida, reg = pasos[-1]
    assert estado == M.ORIENTACION and reg['estado_antes'] == M.LLENAR_EXPEDIENTE
    delitos = {r['delito'] for r in CAT['reglas'] if r['id'] in salida['reglas']}
    assert 'extorsión' in delitos and 'amenazas' not in delitos                       # pide dinero
    assert 'pornografía de personas menores de edad' not in delitos                  # tiene 24
    assert salida['codigos'] == ['queretaro'] and '167 Quinquies' in salida['articulos']['queretaro']
    assert not salida['fuera_de_corpus']


def test_el_lugar_se_sigue_preguntando_aunque_diga_no_se():
    ia = IAFalsa(respuestas={'No sé': {'lugar_hechos': 'no_sabe'}})
    pasos = conversar(ia, ['me amenazan con unas fotos', 'No sé', 'No sé', 'No sé'])
    assert all(p[0] == M.LLENAR_EXPEDIENTE and p[2]['dato'] == 'lugar_hechos' for p in pasos)


def test_un_dato_no_obligatorio_sin_respuesta_no_atrapa():
    resp = {'Querétaro': {'lugar_hechos': 'Querétaro'}, 'víctima': {'papel': 'victima'}}
    pasos = conversar(IAFalsa(respuestas=resp), ['fotos', 'Querétaro', 'víctima'] + ['mmm'] * 12)
    assert pasos[-1][0] == M.ORIENTACION
    preguntas = [p[2]['dato'] for p in pasos if p[2]['tipo'] == 'pregunta']
    assert max(preguntas.count(d) for d in set(preguntas)) <= M.MAX_PREGUNTAS


def test_tipo_dudoso_muestra_botones_y_el_boton_lo_fija():
    ia = IAFalsa(tipos=(), opciones=('imagenes_intimas', 'amenazas_extorsion'),
                 respuestas={'me quieren chantajear': {'pide_dinero': 'si'}})
    estado, exp, salida, _ = conversar(ia, ['me quieren chantajear'])[0]
    assert salida['tipo'] == 'elegir_tipo' and [o['id'] for o in salida['opciones']][-1] == 'otro'
    assert exp['datos'] == {'pide_dinero': 'si'}                 # no se pierde lo que ya contó
    estado, exp, salida, _ = M.turno(estado, exp, {'tipo': 'elegir_tipo', 'valor': 'imagenes_intimas'}, CAT, ia)
    assert exp['tipos_caso'] == ['imagenes_intimas'] and salida['dato'] == 'lugar_hechos'


def test_en_orientacion_cambiar_el_lugar_reorienta_con_otro_codigo():
    pasos = conversar(IAFalsa(respuestas={**FOTOS, 'Perdón, fue en la CDMX': {'lugar_hechos': 'Ciudad de México'}}),
                      list(FOTOS) + ['Perdón, fue en la CDMX'])
    estado, exp, salida, reg = pasos[-1]
    assert estado == M.ORIENTACION and reg['cambios'] == ['lugar_hechos'] and salida['codigos'] == ['cdmx']
    assert '181 Quintus' in salida['articulos']['cdmx']


def test_estado_fuera_del_corpus():
    resp = {**FOTOS, 'En Querétaro': {'lugar_hechos': 'Jalisco'}}
    salida = conversar(IAFalsa(respuestas=resp), list(FOTOS))[-1][2]
    assert salida['tipo'] == 'orientar' and salida['fuera_de_corpus'] and salida['codigos'] == []


def test_solo_confirmadas_deja_sin_reglas_un_catalogo_sin_revisar():
    exp = {**E.nuevo(), 'tipos_caso': ['imagenes_intimas'], 'datos': {'pide_dinero': 'si'}}
    assert E.reglas_aplicables(exp, CAT, solo_confirmadas=True) == []


def test_clasifica_una_sola_vez():
    ia = IAFalsa(respuestas=FOTOS)
    conversar(ia, list(FOTOS))
    assert ia.clasificaciones == 1


def test_reiniciar():
    estado, exp, _, _ = conversar(IAFalsa(respuestas=FOTOS), list(FOTOS))[-1]
    estado, exp, salida, reg = M.turno(estado, exp, {'tipo': 'reiniciar'}, CAT, IAFalsa())
    assert reg['estado_antes'] == M.ORIENTACION and estado == M.LLENAR_EXPEDIENTE and exp['datos'] == {}


def test_transicion_invalida():
    with pytest.raises(ValueError):
        M._siguiente(M.ORIENTACION, 'tipo_dudoso')


# ── ia.py con un LLM falso ────────────────────────────────────────────────────────
class LLMFalso:
    def __init__(self, respuestas):
        self.respuestas, self.sistemas = list(respuestas), []

    def chat(self, system, user, **kw):
        self.sistemas.append(system)
        return self.respuestas.pop(0)


def test_ia_clasificar_descarta_ids_inventados():
    ia = IA.ConsultaIA(LLMFalso(['{"tipos": ["imagenes_intimas", "inventado"], "dudoso": false, "opciones": []}']))
    r = ia.clasificar_caso('me piden dinero por mis fotos', CAT)
    assert r['tipos'] == ['imagenes_intimas'] and r['_llamada']['prompt_md5']


def test_ia_clasificar_dudoso():
    ia = IA.ConsultaIA(LLMFalso(['{"tipos": [], "dudoso": true, "opciones": ["imagenes_intimas", "amenazas_extorsion"]}']))
    r = ia.clasificar_caso('me chantajean', CAT)
    assert r['tipos'] == [] and r['opciones'] == ['imagenes_intimas', 'amenazas_extorsion']


def test_ia_extraer_usa_el_filtro_de_lugares_y_el_json(monkeypatch):
    monkeypatch.setattr(IA.jgate, 'extraer_lugares',
                        lambda texto, llm: {'lugares': [{'texto': 'Querétaro', 'estado': 'Querétaro', 'rol': 'hechos'},
                                                        {'texto': 'CDMX', 'estado': 'Ciudad de México', 'rol': 'vive'}],
                                            'raw': '', 'fuente': 'llm'})
    ia = IA.ConsultaIA(LLMFalso(['{"pide_dinero": "si", "edad_victima": null, "inventado": 3}']))
    datos = [d for d in CAT['datos'] if d['id'] in ('lugar_hechos', 'pide_dinero', 'edad_victima')]
    r = ia.extraer_hechos('vivo en CDMX, me pasó en Querétaro, me piden dinero', '', datos)
    assert r['datos'] == {'lugar_hechos': 'Querétaro', 'pide_dinero': 'si'}


def test_ia_llm_caido_no_tumba():
    class Caido:
        def chat(self, *a, **k):
            raise TimeoutError('sin GPU')
    r = IA.ConsultaIA(Caido()).clasificar_caso('hola', CAT)
    assert r['tipos'] == [] and r['opciones'] == [] and '__error__' in r['_llamada']['raw']
