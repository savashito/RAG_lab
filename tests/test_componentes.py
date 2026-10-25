"""
Pruebas de los evaluadores de la página 🧩 Componentes (apps/rewrite_lab/componentes.py): deciden, sin LLM, si la salida
de cada componente cumple lo esperado.

    uv run --all-extras --with pytest python -m pytest tests/test_componentes.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps' / 'rewrite_lab'))

import componentes as cp  # noqa: E402


def lugar(estado, rol='hechos'):
    return {'texto': estado, 'estado': estado, 'rol': rol}


def test_filtro_estados_y_papel():
    sal = {'lugares': [lugar('Morelos', 'otro')], 'depende_del_estado': True}
    ok, det = cp.eval_filtro({'estados': ['Morelos']}, sal)
    assert ok
    ok, det = cp.eval_filtro({'hechos': ['Morelos'], 'otros': []}, sal)   # el caso de «Trabajo en Morelos…»
    assert not ok and set(det['fallas']) == {'hechos', 'otros'}
    ok, _ = cp.eval_filtro({'hechos': ['Guanajuato'], 'otros': ['Querétaro']},
                           {'lugares': [lugar('Querétaro', 'otro'), lugar('Guanajuato')]})
    assert ok


def test_filtro_solo_revisa_los_campos_del_caso():
    sal = {'lugares': [], 'depende_del_estado': False, 'delito_federal': True, 'teorica': False}
    assert cp.eval_filtro({'depende': False, 'federal': True}, sal)[0]
    assert not cp.eval_filtro({'teorica': True}, sal)[0]


def test_descomponer_no_comparativa_debe_quedar_entera():
    assert cp.eval_descomponer({'compara': False}, ['Me robaron el celular, ¿qué pena tiene?'])[0]
    ok, det = cp.eval_descomponer({'compara': False}, ['¿Qué delito es el robo?', '¿Qué pena tiene el robo?'])
    assert not ok and 'dividió' in det['falla']


def test_descomponer_comparativa_una_busqueda_por_entidad():
    esp = {'compara': True, 'entidades': ['CDMX', 'Querétaro']}
    assert cp.eval_descomponer(esp, ['robo simple en la Ciudad de México', 'robo simple en Querétaro'])[0]
    ok, det = cp.eval_descomponer(esp, ['robo simple en la Ciudad de México y en Querétaro'])
    assert not ok and 'no dividió' in det['falla']
    ok, det = cp.eval_descomponer(esp, ['robo en la CDMX', 'robo en Morelos'])
    assert not ok and det['faltan'] == ['Querétaro']
    # Una búsqueda de más («qué es» + una por estado) es aviso, no fallo.
    ok, det = cp.eval_descomponer(esp, ['¿Qué es el robo?', 'robo en la CDMX', 'robo en Querétaro'])
    assert ok and det['aviso']
    # Conceptos, sin entidades fijas: basta con dividir.
    assert cp.eval_descomponer({'compara': True}, ['¿Qué es el estupro?', '¿Qué es la violación?'])[0]


def test_por_delito_conductas_cantidad_y_sin_estados():
    esp = {'conductas': [['sustancia', 'droga'], ['robo', 'apoder']]}
    assert cp.eval_por_delito(esp, ['administrar una sustancia sin consentimiento', 'robo de cartera'])[0]
    ok, det = cp.eval_por_delito(esp, ['administrar una droga sin consentimiento'])
    assert not ok and det['conductas_halladas'] == 1
    ok, det = cp.eval_por_delito({'conductas': [['extorsi']]}, ['extorsión telefónica', 'extorsión con amenazas'])
    assert ok and det['aviso']
    ok, det = cp.eval_por_delito(esp, ['sustancia en la Ciudad de México', 'robo en la CDMX'])
    assert not ok and any('CDMX' in f for f in det['fallas'])


def test_hyde_reglas():
    assert cp.eval_hyde({'permitidos': []}, 'Comete abuso sexual quien ejecute un acto sexual sin consentimiento.')[0]
    ok, det = cp.eval_hyde({'permitidos': []}, 'Conforme al artículo 176, comete abuso sexual…')
    assert not ok and det['fallas'] == ['trae número de artículo']
    assert not cp.eval_hyde({'permitidos': []}, 'En la Ciudad de México se sanciona…')[0]
    assert cp.eval_hyde({'permitidos': ['CDMX']}, 'En la Ciudad de México se sanciona…')[0]


def test_metricas_por_grupo():
    filas = [{'ok': True, 'esperado': {'compara': True}, 'segundos': 0.5},
             {'ok': False, 'esperado': {'compara': False}, 'segundos': 0.7},
             {'ok': None, 'error': 'TimeoutError', 'esperado': {'compara': False}}]
    m = cp.metricas('descomponer', filas)
    assert m['aciertos'] == 1 and m['errores'] == 1 and m['tasa'] == 0.5
    assert m['por_grupo'] == {'comparativas': {'aciertos': 1, 'n': 1}, 'no comparativas': {'aciertos': 0, 'n': 1}}


def test_casos_iniciales_bien_formados():
    datos = json.loads(cp.CASOS_INICIALES.read_text())
    # Los casos con mensajes de participantes (casos_en_base) no viven en el repo: los carga un script en la base.
    en_base = {c for c, d in cp.COMPONENTES.items() if d.get('casos_en_base')}
    assert set(datos) == set(cp.COMPONENTES) - en_base and not en_base & set(datos)
    for comp, casos in datos.items():
        assert casos, comp
        for k in casos:
            assert k['entrada'].strip() and isinstance(k['esperado'], dict), (comp, k)


def test_contar_preguntas_y_tipos():
    assert cp.contar_preguntas('Me robaron el celular. ¿Es delito y cuánta cárcel le dan?') == 2
    assert cp.contar_preguntas('¿Qué es el fraude?') == 1
    assert cp.contar_preguntas('¿Qué es la tentativa? ¿Y el desistimiento?') == 2
    assert cp.tipos_pregunta('¿Robo en la CDMX y en Querétaro?') == ['comparativa']
    assert cp.tipos_pregunta('Me drogó y me robó', conductas=2) == ['varias conductas']


def test_division_cada_version_con_su_regla():
    varias = {'compara': False, 'preguntas': 2, 'nombrados': []}
    dos = ['¿Qué delito es robar un celular?', '¿Qué pena tiene el robo de un celular?']
    assert not cp.eval_division('solo_lugar')(varias, dos)[0]        # no compara: debía quedar entera
    assert cp.eval_division('solo_pregunta')(varias, dos)[0]
    assert cp.eval_division('lugar_y_pregunta')(varias, dos)[0]
    comp = {'compara': True, 'entidades': ['CDMX', 'Querétaro'], 'preguntas': 1, 'nombrados': ['CDMX', 'Querétaro']}
    por_estado = ['robo en la CDMX', 'robo en Querétaro']
    assert cp.eval_division('solo_lugar')(comp, por_estado)[0]
    assert not cp.eval_division('solo_pregunta')(comp, por_estado)[0]   # una sola pregunta: debía quedar entera
    assert cp.eval_division('libre')(comp, por_estado)[0]
    assert not cp.eval_division('libre')(comp, ['robo en la CDMX', 'robo en Morelos'])[0]   # nombra un estado ajeno


def test_metricas_recall_por_version_y_tipo():
    filas = [{'salida': {'gold': 2, 'aciertos': {'sin dividir': 1, 'solo por lugar': 2}, 'tipos': ['comparativa']}},
             {'salida': {'gold': 1, 'aciertos': {'sin dividir': 1, 'solo por lugar': 1}, 'tipos': []}}]
    m = cp.metricas('division_recall', filas)['por_version']
    assert m['sin dividir']['todas'] == {'aciertos': 2, 'gold': 3, 'preguntas': 2, 'recall': 0.6667}
    assert m['solo por lugar']['comparativa']['recall'] == 1.0 and m['sin dividir']['otra']['gold'] == 1


def test_metricas_recall_tiempo_por_version():
    filas = [{'salida': {'gold': 1, 'aciertos': {'libre': 1}, 'segundos': {'libre': 2.0}}},
             {'salida': {'gold': 1, 'aciertos': {'libre': 0}, 'segundos': {'libre': 4.0}}}]
    assert cp.metricas('division_recall', filas)['por_version']['libre']['segundos'] == {'media': 3.0, 'de': 1.0}


def test_metricas_recall_palabras_del_contexto():
    filas = [{'salida': {'gold': 1, 'aciertos': {'k 10': 1}, 'palabras': {'k 10': 1000}}},
             {'salida': {'gold': 1, 'aciertos': {'k 10': 1}, 'palabras': {'k 10': 3000}}}]
    assert cp.metricas('contexto_recall', filas)['por_version']['k 10']['palabras'] == {'media': 2000.0, 'de': 1000.0}


def test_filtro_ve_la_pregunta_del_asistente():
    import jurisdiction_gate as jg
    larga = ('Lamento lo que pasa. En la Ciudad de México y en Querétaro se sanciona la difusión de imágenes. '
             '**Para orientarte, ¿podrías decirme en qué estado de la República ocurrieron estos hechos?**')
    assert jg.pregunta_de_lugar(larga) == '¿podrías decirme en qué estado de la República ocurrieron estos hechos?'
    assert jg.pregunta_de_lugar('Es necesario precisar en qué entidad ocurrieron los hechos.').startswith('necesario precisar')
    assert jg.pregunta_de_lugar('¿El hecho ocurrió en Querétaro o en la Ciudad de México?')
    assert jg.pregunta_de_lugar('Te recomiendo denunciar. ¿Quieres saber cómo?') is None
    msgs = [{'role': 'user', 'content': 'mandé fotos y me piden dinero'}, {'role': 'assistant', 'content': larga},
            {'role': 'user', 'content': 'Queretaro'}]
    texto, persona = jg.texto_para_filtro(msgs, con_pregunta=True)
    assert texto.splitlines() == ['mandé fotos y me piden dinero',
                                  '[El asistente preguntó: ¿podrías decirme en qué estado de la República ocurrieron estos hechos?]',
                                  'Queretaro']
    assert persona == 'mandé fotos y me piden dinero\nQueretaro'          # el respaldo por regex no lee la pregunta
    assert jg.texto_para_filtro(msgs)[0] == persona                       # sin la opción: igual que hoy
    assert 'Ciudad de México' not in texto                                # las explicaciones del asistente no entran


def test_pregunta_de_lugar_frases_de_gemma():
    """Las frases que se le escapaban a la regex en 216 respuestas reales (regex_contra_gemma.py, 24-oct)."""
    import jurisdiction_gate as jg
    for t in ['…le ofrezco explicar qué establece el código penal de su estado si me indica cuál es.',
              'Es necesario que proporcione la información sobre en qué estado de la República ocurrieron los hechos.',
              'Si necesitas saber qué establece la ley, puedes decirme en qué estado te encuentras.',
              '¿Podrías confirmarme si los hechos ocurrieron físicamente en la Ciudad de México o en otro estado?',
              '¿Los hechos que mencionas ocurrieron dentro de la Ciudad de México?']:
        assert jg.pregunta_de_lugar(t), t
    for t in ['¿Sabes si el proceso se encuentra en una etapa de investigación inicial?',
              'La pena depende del estado donde se cometa el delito.',
              '¿Cómo te encuentras en este momento?', '¿En qué etapa te encuentras?', 'Es importante que confirmen su estado de ebriedad.']:
        assert jg.pregunta_de_lugar(t) is None, t
    # v3 (25-oct): las que se escapaban en el set de referencia de 2,220 respuestas.
    for t in ['Es indispensable confirmar si los hechos ocurrieron efectivamente en el Estado de Querétaro.',
              'Por lo anterior, se requiere saber en qué estado ocurrieron los hechos.',
              'Es necesario precisar la ubicación de los hechos.',
              'Si necesitas saber qué establece la ley en un estado específico, por favor indícame cuál es.',
              '¿Podrías confirmarme si los hechos ocurren en la Ciudad de México?',
              '¿Los hechos que me narras ocurrieron dentro del Estado de México?',
              'Solo necesitaría que me contaras qué sucedió, cuándo y dónde.']:
        assert jg.pregunta_de_lugar(t), t


def test_filtro_metodos_evalua_cada_metodo_y_agrupa():
    v1, v2, v3 = cp.METODOS_FILTRO
    sal = {v1: {'lugares': [lugar('Querétaro', 'otro')]}, v2: {'lugares': [lugar('Querétaro')]}, v3: {'lugares': [lugar('Querétaro')]},
           'segundos': {v1: 0.5, v2: 0.6, v3: 0.9}}
    esp = {'hechos': ['Querétaro'], 'otros': [], 'conversacion': [{'role': 'user', 'content': 'x'}], 'tipo_caso': 'A · contesta solo el lugar'}
    ok, det = cp.eval_filtro_metodos(esp, sal)
    assert ok and not det['por_version'][v1]['ok'] and det['por_version'][v3]['ok']
    m = cp.metricas('filtro_metodos', [{'esperado': esp, 'salida': sal, 'detalle': det, 'ok': ok},
                                       {'esperado': {'estados': ['Morelos'], 'conversacion': []}, 'ok': True, 'salida': sal,
                                        'detalle': cp.eval_filtro_metodos({'estados': ['Morelos'], 'conversacion': []}, sal)[1]}])
    pv = m['por_version']
    assert m['medida'] == 'tasa' and pv[v2]['todas'] == {'aciertos': 1, 'n': 2, 'tasa': 0.5}
    assert pv[v1]['dos mensajes · A · contesta solo el lugar']['tasa'] == 0.0 and pv[v2]['segundos']['media'] == 0.6
    assert 'un mensaje · estados' in pv[v1]
    assert {t['id'] for t in cp.TARJETAS} >= {'filtro', 'reescritura', 'descomponer', 'hyde'}
    assert all(p in cp.COMPONENTES for t in cp.TARJETAS for p in t['pruebas'] + t.get('anteriores', []))


def test_errores_del_lugar_de_los_hechos():
    v1, v2, _ = cp.METODOS_FILTRO
    filas = [{'esperado': {'hechos': ['Querétaro']}, 'salida': {v1: {'lugares': [lugar('Querétaro', 'otro')]}, v2: {'lugares': [lugar('Querétaro')]}}},
             {'esperado': {'hechos': []}, 'salida': {v1: {'lugares': [lugar('Morelos')]}, v2: {'lugares': [lugar('Morelos', 'otro')]}}},
             {'esperado': {'estados': ['CDMX']}, 'salida': {v1: {'lugares': []}}}]   # no prueba «hechos»: no cuenta
    e = cp.errores_lugar(filas)
    assert e[v1] == {'casos': 2, 'falsos_positivos': 1, 'falsos_negativos': 1, 'sin_lugar': 1}
    assert e[v2] == {'casos': 2, 'falsos_positivos': 0, 'falsos_negativos': 0, 'sin_lugar': 1}
