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
    assert set(datos) == set(cp.COMPONENTES)
    for comp, casos in datos.items():
        assert casos, comp
        for k in casos:
            assert k['entrada'].strip() and isinstance(k['esperado'], dict), (comp, k)
