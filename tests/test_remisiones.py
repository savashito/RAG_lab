"""
Pruebas del detector de remisiones (apps/rewrite_lab/remisiones.py). Los textos son de los códigos penales del corpus
o escritos con su misma forma.

    uv run --all-extras --with pytest python -m pytest tests/test_remisiones.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps' / 'rewrite_lab'))

import remisiones as rm  # noqa: E402


def seguir(texto):
    return [(r['articulo'], r['fraccion'], r['ambito']) for r in rm.a_seguir(texto)]


def test_directa_mismo_codigo_con_pena():
    t = '**ARTÍCULO 224.-** Además de las penas previstas en el artículo 220 de este Código: se impondrá de dos a seis años…'
    r = rm.a_seguir(t)
    assert [(x['articulo'], x['ambito'], x['materia']) for x in r] == [('220', 'mismo', 'pena')]


def test_sin_nombre_de_ley_es_hipotesis_mismo_codigo():
    assert seguir('Al médico que se niegue a prestar atención se le impondrán las penas del artículo 181.') == [('181', None, 'mismo_supuesto')]


def test_multiple_y_fraccion():
    assert seguir('Conforme a los artículos 220 y 224 de este Código.') == [('220', None, 'mismo'), ('224', None, 'mismo')]
    assert seguir('En los casos de la fracción VI del artículo 127 del presente Código.') == [('127', 'VI', 'mismo')]


def test_sufijos_latinos():
    assert seguir('Las penas previstas en el artículo 211 Ter de este Código.') == [('211 Ter', None, 'mismo')]
    assert seguir('lo dispuesto en el artículo 199 octies.') == [('199 Octies', None, 'mismo_supuesto')]


def test_otra_ley_se_detecta_pero_no_se_sigue():
    t = 'serán asegurados en términos del artículo 190 Bis de la Ley Federal de Telecomunicaciones y Radiodifusión.'
    d = rm.detectar(t)
    assert d[0]['ambito'] == 'otra_ley' and d[0]['rechazo'] == 'otra_ley' and 'Ley Federal' in d[0]['ley']
    assert rm.a_seguir(t) == []


def test_notas_de_reforma_no_son_remisiones():
    for t in ['REFORMA VIGENTE.- Reformado el presente artículo por Artículo Primero del Decreto No. 1558, publicado…',
              'Se reforman los artículos 29, párrafo segundo; 222, párrafos tercero y cuarto, y 222 bis, del Código Penal Federal.',
              'Antes decía: ARTÍCULO 316.- Se impondrá de diez a cien días multa…',
              'Se adiciona una fracción X al artículo 223 del Código Penal para el Distrito Federal.']:
        assert rm.a_seguir(t) == [], t


def test_su_propio_encabezado_no_es_remision():
    t = 'Fuente: Código Penal de la Ciudad de México\nSección: TÍTULO DÉCIMO QUINTO > Artículo 224\n\n**ARTÍCULO 224.-** Se impondrá…'
    assert rm.detectar(t) == []
    assert rm.detectar('**<mark>Artículo 211 Ter.-</mark>** A quien difunda…') == []


def test_rango_corto_y_rango_amplio():
    assert [x[0] for x in seguir('en los casos de los artículos 220 a 222 de este Código')] == ['220', '221', '222']
    d = rm.detectar('las conductas de los artículos 200 al 230 de este Código')
    assert d and all(x['rechazo'] == 'rango_amplio' for x in d)


def test_relativa():
    r = rm.a_seguir('Se aplicará la pena prevista en el artículo anterior, aumentada en una mitad.')
    assert len(r) == 1 and r[0]['tipo'] == 'relativa' and r[0]['relativa'] == 'anterior' and r[0]['materia'] == 'pena'


def test_numeros_que_no_son_articulos():
    assert seguir('se le impondrán de 2 a 5 años de prisión y de 50 a 300 días multa') == []


def test_muestras_etiquetadas_a_mano():
    """Precisión y cobertura contra las dos muestras etiquetadas a ciegas (tests/fixtures/remisiones_*.json). OJO: el
    detector se ajustó mirando sus errores, así que esto ya no es una medida limpia: protege contra regresiones."""
    import json
    raiz = Path(__file__).resolve().parent / 'fixtures'
    tp = fp = fn = 0
    for nombre in ('remisiones_muestra.json', 'remisiones_holdout.json'):
        for x in json.load(open(raiz / nombre, encoding='utf-8'))['articulos']:
            # Se mide la DETECCIÓN: las listas y rangos largos son remisiones reales que, por política, no se siguen.
            seg = [r for r in rm.detectar(x['texto']) if r['rechazo'] in (None, 'lista_larga', 'rango_amplio')]
            got = {r['articulo'] for r in seg if r['tipo'] != 'relativa'} | {'rel:' + r['relativa'] for r in seg if r['tipo'] == 'relativa'}
            gold = set(x['remisiones']) | {'rel:' + r for r in x['relativas']}
            tp, fp, fn = tp + len(got & gold), fp + len(got - gold), fn + len(gold - got)
    assert tp / (tp + fp) >= 0.95 and tp / (tp + fn) >= 0.95, (tp, fp, fn)


def test_encabezado_de_otro_articulo_pegado_no_es_remision():
    t = 'ARTÍCULO 213.- Al que … se le impondrá prisión. ARTÍCULO 214.- Al que contraiga matrimonio …'
    d = rm.detectar(t)
    assert [x['rechazo'] for x in d if x['articulo'] == '214'] == ['encabezado_pegado']
    assert rm.a_seguir('las penas previstas en el artículo 214. Además, se aplicará…') != []   # fin de oración ≠ encabezado


def test_lista_larga_no_se_sigue():
    t = 'Se perseguirán por querella los delitos previstos en los artículos 224, 228, 229, 230 y 232 de este Código.'
    assert {x['rechazo'] for x in rm.detectar(t)} == {'lista_larga'}
    assert seguir('conforme a los artículos 220, 221 y 224 de este Código') == [('220', None, 'mismo'), ('221', None, 'mismo'), ('224', None, 'mismo')]
