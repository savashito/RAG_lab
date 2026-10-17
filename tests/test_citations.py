"""
Pruebas de la verificación de citas sin LLM (apps/rewrite_lab/citations.py). Los casos de emparejamiento
artículo→ley salen de errores reales encontrados al revisar a mano las respuestas del estudio de usuarios.

    uv run --all-extras --with pytest python -m pytest tests/test_citations.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps' / 'rewrite_lab'))

import citations as cit  # noqa: E402

QRO = 'Código Penal del Estado de Querétaro.md'
CDMX = 'Código Penal de la Ciudad de México.md'
CPEM = 'Código Penal del Estado de México.md'
CPF = 'Código Penal Federal.md'
CNPP = 'Código Nacional de Procedimientos Penales.md'


def pares(texto):
    return [(c['label'], c['article']) for c in cit.extract(texto)]


# ── emparejamiento artículo → ley ───────────────────────────────────────────────

def test_ley_antes_en_la_linea_de_viñeta():
    assert pares('*   **Código Penal del Estado de Querétaro:** Artículos 167 BIS y 167 TER.\n'
                 '*   **Código Penal de la Ciudad de México:** Artículo 179.') == \
        [('Querétaro', '167 BIS'), ('Querétaro', '167 TER'), ('CDMX', '179')]


def test_ley_despues_con_del():
    assert pares('Según el artículo 179 del Código Penal de la Ciudad de México, y el artículo 269 del Código '
                 'Penal del Estado de México.') == [('CDMX', '179'), ('CPEM', '269')]


def test_ley_despues_con_fraccion_o_coma():
    assert pares('(Art. 20, frac. I, CNPP).') == [('CNPP', '20')]
    assert pares('se duplican (**Art. 107, Código Penal CDMX**).') == [('CDMX', '107')]
    assert pares('el **Artículo 2, fracción IV**, de la Ley General para Prevenir, Investigar y Sancionar los '
                 'Delitos en Materia de Extorsión') == [('LGExtorsión', '2')]


def test_sufijos_latinos():
    assert pares('el **Artículo 199 Octies del Código Penal Federal**') == [('CPF', '199 Octies')]


def test_no_toma_la_ley_de_la_linea_siguiente():
    # Antes: «Artículo 199 Octies.» se emparejaba con la CDMX de la línea de abajo.
    assert pares('*   **Código Penal Federal**: Artículo 199 Octies.\n*   **Código Penal de la Ciudad de México**: '
                 'Artículo 181 QUINTUS.') == [('CPF', '199 Octies'), ('CDMX', '181 QUINTUS')]


def test_comparacion_no_es_la_ley_del_articulo():
    assert pares('Sobre la posesión: Al igual que en la CDMX, el **Artículo 201** menciona que…') == [(None, '201')]
    assert pares('El fundamento principal es el Artículo 161: Al igual que en la CDMX, se establece…') == [(None, '161')]


def test_referencias_ambiguas_o_que_no_son_leyes():
    assert pares('el **artículo 150 BIS** del citado código establece') == [(None, '150 BIS')]
    assert pares('mediante el artículo 200, fracción III, del Código Penal local, y en Querétaro') == [(None, '200')]
    assert pares('Artículo 10 del Código Penal del Estado de México; y Artículo 12 de *Lecciones de Derecho Penal*.') == \
        [('CPEM', '10'), (None, '12')]


def test_otra_oracion_no_cuenta():
    assert pares('…diferente al miembro viril (Artículo 273, segundo párrafo). Finalmente, el **Código Penal '
                 'Federal** define la cópula') == [(None, '273')]


def test_tabla_por_columna():
    t = ('### Resumen\n\n| Concepto | Ciudad de México | Querétaro |\n| :--- | :--- | :--- |\n'
         '| **Fundamento** | Artículo 175 | Artículo 161 |\n')
    assert pares(t) == [('CDMX', '175'), ('Querétaro', '161')]


# ── clasificación ───────────────────────────────────────────────────────────────

CORPUS = {(CDMX, '179'): [1], (CPEM, '269'): [2], (CPEM, '287'): [3], (CNPP, '311'): [4], (QRO, '167 quinquies'): [5]}


def resolve(source, article):
    return CORPUS.get((source, cit._norm_art(article)), []), False


CHUNKS = [{'id': 1, 'source': CDMX, 'hierarchy': 'X > Artículo 179'},
          {'id': 2, 'source': CPEM, 'hierarchy': 'X > Artículo 269'}]


def test_clases():
    r = cit.classify('Trabajo en la Ciudad de México y mi jefe me acosa. ¿Es delito?',
                     'El artículo 179 del Código Penal de la Ciudad de México lo sanciona. '
                     'También el artículo 311 del CNPP. Según el artículo 269 del Código Penal de la Ciudad de '
                     'México hay hostigamiento. Y el artículo 999 del Código Penal de la Ciudad de México.',
                     CHUNKS, resolve)
    clases = {(it['label'], it['article']): it['clase'] for it in r['items']}
    assert clases == {('CDMX', '179'): 'en_contexto', ('CNPP', '311'): 'memoria',
                      ('CDMX', '269'): 'cruzada', ('CDMX', '999'): 'inexistente'}
    assert r['question_states'] == ['CDMX']
    assert r['other_states'] == []


def test_otros_estados():
    r = cit.classify('Me robaron el celular en la Ciudad de México. ¿Qué pena tiene?',
                     'Conforme al artículo 287 del Código Penal del Estado de México, el robo…', CHUNKS, resolve)
    assert r['other_states'] == ['CPEM 287']
    sin = cit.classify('¿Qué es la tentativa?', 'El artículo 287 del Código Penal del Estado de México…', CHUNKS, resolve)
    assert sin['other_states'] is None   # la pregunta no menciona estados: no aplica


def test_ley_fuera_del_corpus_queda_sin_ley():
    r = cit.classify('x', 'El artículo 179 del Código Penal de la Ciudad de México.', CHUNKS, resolve, corpus_sources={CPF})
    assert r['items'][0]['clase'] == 'sin_ley'


def test_aggregate_y_acuerdo_con_juez():
    juez = lambda presente: [{'kind': 'must_not', 'text': 'Presenta como aplicable un artículo de otra entidad',
                              'verdict': 'presente' if presente else 'ausente'}]
    def row(otros, presente, counts):
        return {'error': None, 'verdicts': juez(presente),
                'citations': {'counts': dict(dict.fromkeys(cit.CLASES, 0), **counts), 'other_states': otros, 'derogated': 0}}
    rows = [row(['CPEM 287'], True, {'en_contexto': 2, 'memoria': 1}),
            row([], False, {'en_contexto': 3, 'inexistente': 1}),
            row([], True, {'en_contexto': 1, 'sin_ley': 2})]
    m = cit.aggregate(rows)
    assert m['cit_n'] == 8 and m['cit_unknown'] == 2 and m['cit_missing'] == 1
    assert m['cit_context'] == 0.75 and m['cit_memory'] == 0.125
    assert m['cit_answers_missing'] == 1 and m['cit_answers_ungrounded'] == 1
    assert m['other_state_rate'] == round(1 / 3, 4) and m['other_state_judge_rate'] == round(2 / 3, 4)
    assert m['other_state_agreement'] == round(2 / 3, 4)
    assert cit.aggregate([{'error': None, 'citations': None}]) == {}


def test_alias_dentro_de_otra_ley_no_es_la_ley_penal():
    assert pares('el artículo 388 del Código Civil para el Distrito Federal (ahora Ciudad de México)') == [(None, '388')]
    assert pares('*   **Código Procesal Familiar del Estado de Morelos:** Artículos 302 y 443.') == [('CPFM', '302'), ('CPFM', '443')]
    assert pares('el Artículo 7o, transitorio, de la Constitución Política del Estado de Morelos') == [(None, '7o')]
    assert pares('el artículo 194bis del Código Federal de Procedimientos Penales') == [(None, '194bis')]
    assert pares('el artículo 179 del Código Penal de la Ciudad de México') == [('CDMX', '179')]
    assert pares('el artículo 311 del Código Nacional de Procedimientos Penales') == [('CNPP', '311')]


def test_rangos():
    assert pares('las lesiones de los artículos 291 a 293 del Código Penal Federal') == [('CPF', '291'), ('CPF', '293')]


def test_ley_que_no_es_del_corpus_no_hereda_la_anterior():
    assert pares('En el Distrito Federal, Chiapas y Veracruz, así como el artículo 4o. de la Constitución Política de '
                 'los Estados Unidos Mexicanos') == [(None, '4o')]
    assert pares('La Ley Federal contra la Delincuencia Organizada establece que el acopio de armas, previsto en los '
                 'artículos 83 Bis, 84 (párrafo primero) de la Ley Federal de Armas de Fuego') == [(None, '83 Bis'), (None, '84')]
    assert pares('el art. 7o. del Código Penal Federal') == [('CPF', '7o')]


def test_mencion_suelta_de_articulo_ya_citado_no_se_repite():
    assert pares('Según el artículo 290 del Código Penal del Estado de México… Además, el Artículo 290 establece…') == \
        [('CPEM', '290')]
