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
    """Clasifica pidiendo agregar `tipos` (y quitar `quitar`) y extrae, por cada mensaje, lo que diga
    `respuestas[texto del mensaje]`."""

    def __init__(self, tipos=('imagenes_intimas',), opciones=(), respuestas=None, quitar=()):
        self.tipos, self.opciones, self.respuestas = list(tipos), list(opciones), respuestas or {}
        self.quitar, self.conversaciones = list(quitar), []
        self.clasificaciones = 0

    def clasificar_caso(self, conversacion, actuales, catalogo):
        self.clasificaciones += 1
        self.conversaciones.append(conversacion)
        return {'agregar': [t for t in self.tipos if t not in actuales], 'quitar': self.quitar, 'por_que': 'prueba',
                'opciones': self.opciones, '_llamada': {'tarea': 'clasificar_caso'}}

    def extraer_expediente(self, texto, pregunta, datos, ultimo=None):
        ultimo = texto.split('\n')[-1]
        pedidos = {d['id'] for d in datos}
        return {'datos': {k: v for k, v in self.respuestas.get(ultimo, {}).items() if k in pedidos},
                '_llamada': {'tarea': 'extraer_expediente'}}


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


def test_catalogo_materia_por_omision_penal_y_rechaza_otra():
    assert C.validar_entrada('reglas', CAT['reglas'][0], CAT)['materia'] == 'penal'
    with pytest.raises(ValueError, match='Materia'):
        C.validar_entrada('reglas', {**CAT['reglas'][0], 'materia': 'laboral'}, CAT)


def test_catalogo_guarda_leyes_que_no_son_codigos_penales_solo_si_se_citan():
    r = C.validar_entrada('reglas', {**CAT['reglas'][0], 'articulos': {'cdmx': ['236'], 'ley_extorsion': ['15']}}, CAT)
    assert r['articulos']['ley_extorsion'] == ['15'] and 'cnpp' not in r['articulos'] and r['articulos']['morelos'] == []


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
    'No, nunca acepté que las compartiera': {'consentimiento_difusion': 'no'},
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
    assert salida['codigos'] == ['queretaro', 'ley_extorsion', 'lgamvlv', 'federal'] and '167 Quinquies' in salida['articulos']['queretaro']
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
    assert estado == M.ORIENTACION and reg['cambios'] == ['lugar_hechos'] and salida['codigos'] == ['cdmx', 'ley_extorsion', 'lgamvlv', 'federal']
    assert '181 Quintus' in salida['articulos']['cdmx']


def test_estado_fuera_del_corpus():
    resp = {**FOTOS, 'En Querétaro': {'lugar_hechos': 'Jalisco'}}
    salida = conversar(IAFalsa(respuestas=resp), list(FOTOS))[-1][2]
    # Jalisco no está en el corpus, pero hay reglas con leyes generales y el CPF: se orienta con ellas y no cuenta como fuera.
    assert salida['tipo'] == 'orientar' and not salida['fuera_de_corpus'] and salida['codigos'] == ['ley_extorsion', 'lgamvlv', 'federal']


def test_solo_confirmadas_deja_sin_reglas_un_catalogo_sin_revisar():
    exp = {**E.nuevo(), 'tipos_caso': ['imagenes_intimas'], 'datos': {'pide_dinero': 'si'}}
    assert E.reglas_aplicables(exp, CAT, solo_confirmadas=True) == []


def test_clasifica_en_cada_mensaje():
    ia = IAFalsa(respuestas=FOTOS)
    conversar(ia, list(FOTOS))
    assert ia.clasificaciones == len(FOTOS)


class IACambia(IAFalsa):
    """Primero dice `otro`; cuando la persona cuenta lo de las fotos, `imagenes_intimas`."""

    def clasificar_caso(self, conversacion, actuales, catalogo):
        self.clasificaciones += 1
        return {'agregar': ['imagenes_intimas'] if 'fotos' in conversacion else ['otro'], 'quitar': [],
                'opciones': [], '_llamada': {}}


def test_el_tipo_de_caso_cambia_con_informacion_nueva_y_conserva_los_datos():
    resp = {'Hola, tengo una duda': {}, 'Fue en Querétaro': {'lugar_hechos': 'Querétaro'}, 'A mí': {'papel': 'victima'},
            'Me piden dinero por unas fotos': {'pide_dinero': 'si'}}
    pasos = conversar(IACambia(respuestas=resp), list(resp))
    assert pasos[2][0] == M.ORIENTACION and pasos[2][1]['tipos_caso'] == ['otro']   # «otro»: solo lugar y papel
    estado, exp, salida, reg = pasos[3]
    assert exp['tipos_caso'] == ['imagenes_intimas'] and reg['tipos_antes'] == ['otro']
    assert estado == M.LLENAR_EXPEDIENTE and reg['estado_antes'] == M.ORIENTACION    # el tipo nuevo pide más datos
    assert exp['datos']['lugar_hechos'] == 'Querétaro' and salida['dato'] != 'lugar_hechos'


def test_la_duda_no_quita_un_tipo_ya_elegido():
    ia = IAFalsa(respuestas=FOTOS)
    estado, exp, _, _ = conversar(ia, list(FOTOS)[:2])[-1]
    ia.tipos, ia.opciones = [], ['imagenes_intimas', 'amenazas_extorsion']
    _, exp, salida, _ = M.turno(estado, exp, {'tipo': 'mensaje', 'texto': 'A mí', 'historial': []}, CAT, ia)
    assert exp['tipos_caso'] == ['imagenes_intimas'] and salida['tipo'] != 'elegir_tipo'


@pytest.mark.parametrize('antes,agregar,quitar,despues', [
    (['amenazas_extorsion'], ['imagenes_intimas'], [], ['amenazas_extorsion', 'imagenes_intimas']),
    (['amenazas_extorsion'], [], ['amenazas_extorsion'], ['amenazas_extorsion']),       # no deja el expediente sin tipo
    (['amenazas_extorsion'], ['imagenes_intimas'], ['amenazas_extorsion'], ['imagenes_intimas']),
    (['imagenes_intimas'], ['otro'], [], ['imagenes_intimas']),                          # otro no reemplaza un tipo real
    (['otro'], ['imagenes_intimas'], [], ['imagenes_intimas']),                          # un tipo real saca a otro
    ([], ['otro'], [], ['otro']),
    (['imagenes_intimas'], [], [], ['imagenes_intimas']),
])
def test_aplicar_clasificacion(antes, agregar, quitar, despues):
    assert M._aplicar_clasificacion(antes, {'agregar': agregar, 'quitar': quitar}) == despues


def test_clasificar_ve_las_preguntas_del_asistente():
    ia = IAFalsa(respuestas=FOTOS)
    conversar(ia, list(FOTOS)[:2])
    assert ia.conversaciones[1].startswith('Persona: ') and '\nAsistente: ' in ia.conversaciones[1]


def test_quitar_un_tipo_ya_orientado_lo_avisa_en_la_orientacion():
    ia = IAFalsa(respuestas=FOTOS)
    estado, exp, salida, _ = conversar(ia, list(FOTOS))[-1]
    assert salida['tipo'] == 'orientar' and salida['tipos_quitados'] == []
    ia.tipos, ia.quitar = ['otro'], ['imagenes_intimas']          # «perdón, no hay fotos; es otra cosa»
    estado, exp, salida, reg = M.turno(estado, exp, {'tipo': 'mensaje', 'texto': 'no hay fotos', 'historial': []},
                                       CAT, ia)
    assert exp['tipos_caso'] == ['otro'] and reg['tipos_quitados'] == ['imagenes_intimas'] and reg['por_que']
    assert salida['tipo'] == 'orientar' and salida['tipos_quitados'] == ['imagenes_intimas']
    _, _, salida, _ = M.turno(estado, exp, {'tipo': 'mensaje', 'texto': 'gracias', 'historial': []}, CAT, IAFalsa(tipos=()))
    assert salida['tipos_quitados'] == []                          # se avisa una sola vez


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
        self.respuestas, self.sistemas, self.usuarios = list(respuestas), [], []

    def chat(self, system, user, **kw):
        self.sistemas.append(system)
        self.usuarios.append(user)
        return self.respuestas.pop(0)


def test_ia_clasificar_descarta_ids_inventados():
    ia = IA.ConsultaIA(LLMFalso(['{"agregar": ["imagenes_intimas", "inventado"], "quitar": ["amenazas_extorsion"]}']))
    r = ia.clasificar_caso('Persona: me piden dinero por mis fotos', [], CAT)
    assert r['agregar'] == ['imagenes_intimas'] and r['quitar'] == [] and r['_llamada']['prompt_md5']


def test_ia_clasificar_recibe_los_tipos_actuales_y_la_conversacion():
    llm = LLMFalso(['{"agregar": [], "quitar": ["imagenes_intimas"], "por_que": "dijo que no hay fotos"}'])
    r = IA.ConsultaIA(llm).clasificar_caso('Asistente: ¿Tiene fotos tuyas?\nPersona: no, nunca hubo fotos',
                                           ['imagenes_intimas'], CAT)
    assert r['quitar'] == ['imagenes_intimas'] and r['por_que'] == 'dijo que no hay fotos'
    assert 'ACTUALES: imagenes_intimas' in llm.usuarios[0] and 'Asistente: ¿Tiene fotos' in llm.usuarios[0]


def test_ia_clasificar_dudoso():
    ia = IA.ConsultaIA(LLMFalso(['{"agregar": [], "dudoso": true, "opciones": ["imagenes_intimas", "amenazas_extorsion"]}']))
    r = ia.clasificar_caso('Persona: me chantajean', [], CAT)
    assert r['agregar'] == [] and r['opciones'] == ['imagenes_intimas', 'amenazas_extorsion']


def test_ia_extraer_usa_el_filtro_de_lugares_y_el_json(monkeypatch):
    monkeypatch.setattr(IA.jgate, 'extraer_lugares',
                        lambda texto, llm, sistema=None, texto_regex=None: {'lugares': [{'texto': 'Querétaro', 'estado': 'Querétaro', 'rol': 'hechos'},
                                                        {'texto': 'CDMX', 'estado': 'Ciudad de México', 'rol': 'vive'}],
                                            'raw': '', 'fuente': 'llm'})
    ia = IA.ConsultaIA(LLMFalso(['{"pide_dinero": "si", "edad_victima": null, "inventado": 3}']))
    datos = [d for d in CAT['datos'] if d['id'] in ('lugar_hechos', 'pide_dinero', 'edad_victima')]
    r = ia.extraer_expediente('vivo en CDMX, me pasó en Querétaro, me piden dinero', '', datos)
    assert r['datos'] == {'lugar_hechos': 'Querétaro', 'pide_dinero': 'si'}


def test_ia_llm_caido_no_tumba():
    class Caido:
        def chat(self, *a, **k):
            raise TimeoutError('sin GPU')
    r = IA.ConsultaIA(Caido()).clasificar_caso('Persona: hola', ['imagenes_intimas'], CAT)
    assert r['agregar'] == r['quitar'] == r['opciones'] == [] and '__error__' in r['_llamada']['raw']


@pytest.mark.parametrize('lugar, articulos, esperado', [
    # ley general: vale en cualquier estado, junto al código penal del estado
    ('Querétaro', {'queretaro': ['1'], 'ley_extorsion': ['15']}, ['queretaro', 'ley_extorsion']),
    # código civil de la CDMX: solo si los hechos son en la CDMX
    ('Ciudad de México', {'cc_cdmx': ['308'], 'cnpcf': ['1']}, ['cdmx', 'cc_cdmx', 'cnpcf']),
    ('Querétaro', {'cc_cdmx': ['308'], 'cnpcf': ['1']}, ['queretaro', 'cnpcf']),
    # ley federal: solo si la regla no cita ninguna ley de un estado
    ('Morelos', {'morelos': ['1'], 'lfcdo': ['2']}, ['morelos']),
    ('Morelos', {'federal': ['1'], 'lfcdo': ['2']}, ['morelos', 'federal', 'lfcdo']),
])
def test_codigos_del_caso_con_leyes_generales_federales_y_de_familia(lugar, articulos, esperado):
    exp = {**E.nuevo(), 'datos': {'lugar_hechos': lugar}}
    assert E.codigos_del_caso(exp, [{'id': 'r', 'articulos': articulos}]) == esperado


# ── Orientación: qué artículos entran al contexto ────────────────────────────────────────────────────────────────
from consulta import orientar as O  # noqa: E402


def _art(codigo, num, chars, distancia=None):
    a = {'codigo': codigo, 'num': num, 'ruta': f'Artículo {num}', 'texto': 'x' * chars, 'ids': []}
    if distancia is not None:
        a['distancia'] = distancia
    return a


def test_contexto_todos_sigue_el_catalogo_y_respeta_el_tope():
    reglas = [{'id': 'r1', 'articulos': {'cdmx': ['1', '2']}, 'incierta': True},
              {'id': 'r2', 'articulos': {'cdmx': ['3', '1']}, 'incierta': False}]
    arts = [_art('cdmx', '1', 350), _art('cdmx', '2', 350), _art('cdmx', '3', 350)]   # ~100 tokens cada uno
    elegidos = O.elegir(arts, reglas, 'todos', tope=250)
    assert [a['num'] for a in elegidos] == ['3', '1']      # primero la regla que no es incierta; el 1 cuenta una vez
    assert not next(a for a in arts if a['num'] == '2')['entra']


def test_contexto_embedding_pone_primero_el_mejor_de_cada_regla():
    reglas = [{'id': 'r1', 'articulos': {'cdmx': ['1', '2']}}, {'id': 'r2', 'articulos': {'federal': ['9']}}]
    arts = [_art('cdmx', '1', 350, .10), _art('cdmx', '2', 350, .05), _art('federal', '9', 350, .40)]
    elegidos = O.elegir(arts, reglas, 'embedding', tope=250)
    assert [a['num'] for a in elegidos] == ['2', '9']       # el 9 está lejos, pero es el único de r2: entra


def test_contexto_desconocido_se_rechaza():
    with pytest.raises(ValueError):
        O.orientar(cur=None, table='t', salida={}, expediente={}, catalogo={}, conversacion='', contexto='bm25',
                   embed=None, chat=None, system='')


class IAConResidencia(IAFalsa):
    """Como IAFalsa, pero el extractor de lugares dice dónde vive la persona (rol «otro») si el texto dice «soy de»."""

    def extraer_expediente(self, texto, pregunta, datos, ultimo=None):
        x = super().extraer_expediente(texto, pregunta, datos, ultimo)
        return {**x, 'residencia': 'Ciudad de México' if 'soy de cdmx' in texto.lower() else None}


def test_si_solo_dice_donde_vive_lo_ofrece_y_luego_lo_supone():
    ia = IAConResidencia(respuestas={'ya te dije': {}})
    pasos = conversar(ia, ['Mandé fotos íntimas a un extraño y ahora me pide dinero; soy de CDMX', 'ya te dije'])
    assert pasos[0][2]['texto'] == 'Ciudad de México es tu lugar de residencia, ¿también ocurrieron los hechos ahí?'
    estado, exp, salida, _ = pasos[1]
    assert exp['datos']['lugar_hechos'] == 'Ciudad de México' and exp['supuestos'] == ['lugar_hechos']
    assert not (salida['tipo'] == 'pregunta' and salida['dato'] == 'lugar_hechos')
    assert salida['aviso'] == 'Voy a asumir que lo que te pasó ocurrió en Ciudad de México, donde vives.'


def test_si_nombra_otro_estado_gana_ese_y_no_hay_supuesto():
    ia = IAConResidencia(respuestas={'No, fue en Querétaro': {'lugar_hechos': 'Querétaro'}})
    pasos = conversar(ia, ['Me amenazan con publicar mis fotos; soy de CDMX', 'No, fue en Querétaro'])
    exp = pasos[1][1]
    assert exp['datos']['lugar_hechos'] == 'Querétaro' and not exp.get('supuestos')
    assert 'aviso' not in pasos[1][2]


def test_la_pregunta_redactada_lleva_el_dato_su_texto_y_el_aviso():
    salida = {'tipo': 'pregunta', 'dato': 'edad_victima', 'texto': '¿Qué edad tiene la víctima?',
              'aviso': 'Voy a asumir que lo que te pasó ocurrió en Ciudad de México, donde vives.'}
    m = O.mensajes_pregunta('Persona: me piden dinero por mis fotos', salida, CAT)
    assert m[0]['role'] == 'system' and 'Pregunta solo eso' in m[0]['content']
    u = m[1]['content']
    assert 'DATO QUE FALTA: edad_victima' in u and '¿Qué edad tiene la víctima?' in u and 'AVISO: Voy a asumir' in u


class IASaludo(IAFalsa):
    """Sin tipo de caso mientras la persona no cuenta nada; con «fotos» en la conversación, imagenes_intimas."""

    def clasificar_caso(self, conversacion, actuales, catalogo):
        c = super().clasificar_caso(conversacion, actuales, catalogo)
        return c if 'fotos' in conversacion else {**c, 'agregar': []}


def test_sin_relato_pide_que_cuente_su_situacion_y_guarda_lo_que_ya_dio():
    ia = IASaludo(respuestas={'Hola, soy de Querétaro': {'lugar_hechos': 'Querétaro'}})
    pasos = conversar(ia, ['Hola, soy de Querétaro', 'Me piden dinero por mis fotos íntimas'])
    estado, exp, salida, _ = pasos[0]
    assert estado == M.LLENAR_EXPEDIENTE and salida['dato'] == 'relato'
    assert salida['texto'] == 'Hola, soy Tlacua, tu asistente jurídico.\n¿En qué te puedo ayudar? Cuéntame tu situación.'
    assert exp['datos'] == {'lugar_hechos': 'Querétaro'}
    estado, exp, salida, _ = pasos[1]
    assert exp['tipos_caso'] == ['imagenes_intimas'] and salida['dato'] != 'lugar_hechos'   # el lugar ya estaba


def test_el_saludo_va_solo_en_el_primer_mensaje_del_asistente():
    pasos = conversar(IASaludo(), ['Hola', 'mmm'])
    assert pasos[0][2]['texto'].startswith('Hola, soy Tlacua') and pasos[1][2]['texto'] == M.RELATO


def test_ia_extraer_lugar_ve_la_pregunta_del_asistente(monkeypatch):
    vistos = []
    monkeypatch.setattr(IA.jgate, 'extraer_lugares', lambda texto, llm, sistema=None, texto_regex=None: vistos.append((texto, sistema, texto_regex)) or
                        {'lugares': [{'texto': 'cdmx', 'estado': 'Ciudad de México', 'rol': 'hechos'}], 'raw': '', 'fuente': 'llm'})
    ia = IA.ConsultaIA(LLMFalso([]))
    datos = [d for d in CAT['datos'] if d['id'] == 'lugar_hechos']
    r = ia.extraer_expediente('mandé unas fotos\nen cdmx', '¿En qué estado pasó?', datos, 'en cdmx')
    assert r['datos'] == {'lugar_hechos': 'Ciudad de México'}
    assert vistos == [('mandé unas fotos\n[El asistente preguntó: ¿En qué estado pasó?]\nen cdmx', IA.jgate.EXTRAER_SYSTEM_V2,
                       'mandé unas fotos\nen cdmx')]   # el respaldo por regex no ve la pregunta


def test_si_le_paso_a_la_persona_la_pregunta_es_de_tu():
    cat = {**CAT, 'datos': [{**d, 'pregunta_tu': '¿Qué edad tienes?'} if d['id'] == 'edad_victima' else d
                            for d in CAT['datos']]}
    ia = IAFalsa(respuestas={**FOTOS})
    historial, salidas = [], []
    estado = exp = None
    for m in list(FOTOS)[:4]:
        estado, exp, salida, _ = M.turno(estado, exp, {'tipo': 'mensaje', 'texto': m, 'historial': historial}, cat, ia)
        historial += [{'role': 'user', 'content': m}, {'role': 'assistant', 'content': salida.get('texto', '')}]
        salidas.append(salida)
    assert salidas[-1]['dato'] == 'edad_victima' and salidas[-1]['texto'] == '¿Qué edad tienes?'
