"""
Pruebas de la lógica pura del benchmark (apps/rewrite_lab/bench.py): parseo tolerante de
la salida del juez, puntuación con must/should/must_not y agregados.

    uv run --all-extras --with pytest python -m pytest tests/test_bench.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps' / 'rewrite_lab'))

from bench import (IMPLICIT_COMPONENT, aggregate, build_judge_prompt,  # noqa: E402
                   effective_components, parse_judge, score_question)


def C(kind, text='x', weight=1.0):
    return {'kind': kind, 'text': text, 'weight': weight}


def V(verdict):
    return {'verdict': verdict, 'evidence': ''}


# ── parse_judge ─────────────────────────────────────────────────────────────────

def test_parse_clean_json():
    raw = '{"elementos": [{"n": 1, "veredicto": "presente", "evidencia": "art. 146"}, {"n": 2, "veredicto": "ausente"}]}'
    out = parse_judge(raw, 2)
    assert [o['verdict'] for o in out] == ['presente', 'ausente']
    assert out[0]['evidence'] == 'art. 146'


def test_parse_fenced_with_prose_and_english_and_aliases():
    raw = 'Claro:\n```json\n{"elements": [{"id": 2, "verdict": "Partial"}, {"id": 1, "verdict": "yes"}]}\n```'
    out = parse_judge(raw, 2)
    assert [o['verdict'] for o in out] == ['presente', 'parcial']


def test_parse_missing_and_garbage_become_none():
    assert [o['verdict'] for o in parse_judge('no sé', 2)] == [None, None]
    out = parse_judge('{"elementos": [{"n": 1, "veredicto": "quizá"}]}', 3)
    assert [o['verdict'] for o in out] == [None, None, None]


def test_parse_ignores_out_of_range_index():
    out = parse_judge('{"elementos": [{"n": 9, "veredicto": "presente"}]}', 1)
    assert out[0]['verdict'] is None


# ── score_question ──────────────────────────────────────────────────────────────

def test_all_must_present_passes():
    s = score_question([C('must'), C('must')], [V('presente'), V('presente')])
    assert s['score'] == 1.0 and s['passed'] and s['must_ok'] == 2


def test_partial_must_halves_and_fails():
    s = score_question([C('must'), C('must')], [V('presente'), V('parcial')])
    assert s['score'] == 0.75 and not s['passed']


def test_should_counts_but_does_not_fail():
    s = score_question([C('must'), C('should')], [V('presente'), V('ausente')])
    assert s['score'] == 0.5 and s['passed']


def test_weights():
    s = score_question([C('must', weight=3), C('should', weight=1)], [V('presente'), V('ausente')])
    assert s['score'] == 0.75


def test_must_not_present_subtracts_and_fails():
    s = score_question([C('must'), C('must_not')], [V('presente'), V('presente')])
    assert s['score'] == 0.0 and not s['passed'] and s['violations'] == 1


def test_must_not_partial_subtracts_half_but_passes():
    s = score_question([C('must'), C('must_not')], [V('presente'), V('parcial')])
    assert s['score'] == 0.5 and s['passed'] and s['violations'] == 0


def test_unknown_verdict_counts_as_absent():
    s = score_question([C('must')], [V(None)])
    assert s['score'] == 0.0 and not s['passed']


def test_only_must_not():
    assert score_question([C('must_not')], [V('ausente')])['score'] == 1.0
    assert score_question([C('must_not')], [V('presente')])['score'] == 0.0


# ── componentes efectivos y prompt ──────────────────────────────────────────────

def test_implicit_component_from_reference():
    comps = effective_components({'components': [], 'expected_answer': 'La prisión preventiva…'})
    assert comps[0]['text'] == IMPLICIT_COMPONENT and comps[0]['kind'] == 'must'
    assert effective_components({'components': [], 'expected_answer': ''}) == []
    assert effective_components({'components': [C('should', '  ')], 'expected_answer': ''}) == []


def test_prompt_does_not_reveal_kinds():
    p = build_judge_prompt('¿Q?', 'resp', [C('must', 'A'), C('must_not', 'B')], 'ref')
    assert '1. A' in p and '2. B' in p and 'must' not in p and 'REFERENCIA' in p


# ── aggregate ───────────────────────────────────────────────────────────────────

def test_aggregate_skips_errors():
    rows = [dict(score=1.0, passed=True, must_total=2, must_ok=2, violations=0, seconds=4, error=None),
            dict(score=0.5, passed=False, must_total=2, must_ok=1, violations=1, seconds=6, error=None),
            dict(score=0.0, passed=False, must_total=0, must_ok=0, violations=0, seconds=1, error='boom')]
    a = aggregate(rows)
    assert a['n'] == 3 and a['errors'] == 1
    assert a['score'] == 0.75 and a['pass_rate'] == 0.5 and a['must_coverage'] == 0.75
    assert a['violations'] == 1 and a['avg_seconds'] == 5.0


# ── reintentos ante errores transitorios del LLM ────────────────────────────────

def test_retry_recovers_from_transient(monkeypatch):
    import http.client

    import bench
    monkeypatch.setattr(bench, 'RETRY_WAITS', (0, 0))
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise http.client.RemoteDisconnected('Remote end closed connection without response')
        return 'ok'
    assert bench._retry(flaky) == 'ok' and len(calls) == 3


def test_retry_gives_up_and_skips_logic_errors(monkeypatch):
    import urllib.error

    import bench
    monkeypatch.setattr(bench, 'RETRY_WAITS', (0, 0))
    calls = []

    def down():
        calls.append(1)
        raise urllib.error.URLError('[Errno 111] Connection refused')
    try:
        bench._retry(down)
    except urllib.error.URLError:
        pass
    assert len(calls) == 3   # 1 + 2 reintentos

    calls.clear()

    def bug():
        calls.append(1)
        raise ValueError('pregunta vacía')
    try:
        bench._retry(bug)
    except ValueError:
        pass
    assert len(calls) == 1   # los errores de lógica no se reintentan


# ── validación del JSON del editor (/benchmark/editor) ──────────────────────────

def _payload(**over):
    p = {'name': 'Set', 'topic': 't', 'questions': [
        {'id': 1, 'question': '¿Q1?', 'components': [{'kind': 'must', 'text': 'A', 'weight': 2}]},
        {'question': '¿Nueva?', 'expected_answer': 'Ref.'}]}
    p.update(over)
    return p


def test_validate_ok():
    from bench import validate_set_payload
    assert validate_set_payload(_payload(), {1, 2}) == []


def test_validate_reports_each_problem():
    from bench import validate_set_payload
    bad = _payload(name='', questions=[
        {'id': 99, 'question': ' ', 'components': [{'kind': 'mus', 'text': '', 'weight': -1}]},
        {'id': 1, 'question': 'ok', 'components': []},
        {'id': 1, 'question': 'dup', 'components': [{'kind': 'should', 'text': 'x'}]}])
    errs = validate_set_payload(bad, {1})
    joined = '\n'.join(errs)
    assert 'Falta "name"' in joined
    assert 'Pregunta #1: "question" está vacío' in joined
    assert '"id": 99 no pertenece' in joined
    assert '"kind" debe ser' in joined and '"text" está vacío' in joined and '"weight" debe ser' in joined
    assert 'Pregunta #2: sin componentes ni "expected_answer"' in joined
    assert 'Pregunta #3: "id": 1 está repetido' in joined


def test_validate_rejects_non_list_questions():
    from bench import validate_set_payload
    assert validate_set_payload(_payload(questions={}), set())[-1].startswith('"questions" debe ser una lista')
    assert validate_set_payload([], set()) == ['El JSON debe ser un objeto { … }.']


# ── dificultad ───────────────────────────────────────────────────────────────────

def test_norm_difficulty_aliases():
    from bench import norm_difficulty
    assert [norm_difficulty(x) for x in ('Fácil', 'facil', 'MEDIO', 'mediano', 'Difícil', 'hard')] == \
        ['facil', 'facil', 'mediano', 'mediano', 'dificil', 'dificil']
    assert norm_difficulty('') is None and norm_difficulty(None) is None
    assert norm_difficulty('imposible') is False


def test_validate_difficulty():
    from bench import validate_set_payload
    ok = _payload(questions=[{'question': 'q', 'difficulty': 'Difícil', 'expected_answer': 'r'},
                             {'question': 'q2', 'expected_answer': 'r'}])          # sin dificultad: válido
    assert validate_set_payload(ok, set()) == []
    bad = _payload(questions=[{'question': 'q', 'difficulty': 'extrema', 'expected_answer': 'r'}])
    assert '"difficulty" debe ser' in validate_set_payload(bad, set())[0]


# ── artículo correcto: extracción desde los must y chequeo de recuperación ──────

def test_gold_refs_from_citation_musts():
    from bench import gold_refs
    comps = [{'kind': 'must', 'text': 'Cita el art. 179 del Código Penal de la Ciudad de México'},
             {'kind': 'must', 'text': 'Cita los arts. 269 y 269 Bis del Código Penal del Estado de México'},
             {'kind': 'must', 'text': 'Cita al menos uno de estos artículos: art. 20 del Código Penal de la Ciudad de México; '
                                      'art. 12 del Código Penal Federal'},
             {'kind': 'should', 'text': 'Cita el art. 272 del Código Penal del Estado de México'},   # should: no es gold
             {'kind': 'must_not', 'text': 'Cita el art. 1 del Código Penal Federal'}]                # must_not: tampoco
    g = gold_refs('¿pregunta?', comps)
    assert [[x['label'] for x in grp] for grp in g] == [['CDMX 179'], ['CPEM 269'], ['CPEM 269 Bis'], ['CDMX 20', 'CPF 12']]


def test_gold_refs_uses_question_law_and_marks_gap():
    from bench import gold_refs
    g = gold_refs('En el Código Penal Federal, ¿cómo se tipifica el estupro?',
                  [{'kind': 'must', 'text': 'Las sanciones del estupro (art. 262) son imprescriptibles'},
                   {'kind': 'must', 'text': 'Querétaro (art. 167): el sujeto pasivo es mayor de 14'}])
    assert [x['label'] for grp in g for x in grp] == ['CPF 262', 'Querétaro 167']
    assert g[1][0]['source'] is None          # Querétaro no está en el corpus


def test_retrieval_check_ranks_and_attainable():
    from bench import retrieval_check
    groups = [[{'label': 'CDMX 179', 'ids': [10]}],
              [{'label': 'CDMX 20', 'ids': [20]}, {'label': 'CPF 12', 'ids': [30]}],   # basta una
              [{'label': 'CPF 266', 'ids': [40]}],
              [{'label': 'Querétaro 167', 'ids': []}]]                                 # hueco
    r = retrieval_check(groups, [99, 30, 10])
    assert [g['rank'] for g in r['groups']] == [3, 2, None, None]
    assert (r['hit'], r['total'], r['attainable']) == (2, 4, 3)


def test_aggregate_retrieval():
    rows = [dict(score=1, passed=True, must_total=1, must_ok=1, violations=0, seconds=1, error=None,
                 retrieval={'hit': 2, 'total': 2, 'attainable': 2}),
            dict(score=0, passed=False, must_total=1, must_ok=0, violations=0, seconds=1, error=None,
                 retrieval={'hit': 0, 'total': 2, 'attainable': 1})]
    a = aggregate(rows)
    assert a['retrieval_recall'] == round(2 / 3, 4) and a['retrieval_full'] == 0.5 and a['retrieval_n'] == 2


# ── query decomposition ─────────────────────────────────────────────────────────

def test_parse_subquestions():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from shared.llm_client import parse_subquestions
    q = 'Compara el estupro en Morelos y en la CDMX'
    raw = 'Claro: {"subpreguntas": ["estupro en el Código Penal de Morelos", "estupro en el Código Penal de la CDMX", "Estupro en el Código Penal de Morelos", ""]}'
    assert parse_subquestions(raw, q) == ['estupro en el Código Penal de Morelos', 'estupro en el Código Penal de la CDMX']
    assert parse_subquestions('no es json', q) == [q]          # cualquier falla → la pregunta original
    assert parse_subquestions('{"subpreguntas": []}', q) == [q]
    # una sola sub-pregunta (aunque sea una paráfrasis) → se usa la pregunta original
    assert parse_subquestions('{"subpreguntas": ["¿Qué es el estupro en Morelos y CDMX? (reformulada)"]}', q) == [q]
    assert len(parse_subquestions('{"subpreguntas": ["a","b","c","d","e"]}', q)) == 4


def test_interleave_scored_balances_entities():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from shared.lexical import interleave_scored
    morelos = [(1, .9), (2, .8), (3, .7), (4, .6)]
    cdmx = [(10, .5), (2, .4), (11, .3)]
    assert [i for i, _ in interleave_scored([morelos, cdmx])] == [1, 10, 2, 3, 11, 4]   # sin repetir el 2
    assert interleave_scored([morelos]) == morelos


def test_gold_refs_family_codes_not_confused():
    from bench import gold_refs
    comps = [{'kind': 'must', 'text': 'Cita el art. 562 del Código Nacional de Procedimientos Civiles y Familiares'},
             {'kind': 'must', 'text': 'Cita el art. 491 del Código Procesal Familiar para el Estado de Morelos'},
             {'kind': 'must', 'text': 'Cita el art. 65 del Código Familiar para el Estado de Morelos'},
             {'kind': 'must', 'text': 'Cita el art. 146 del Código Nacional de Procedimientos Penales'},
             {'kind': 'must', 'text': 'Cita el art. 159 del Código Penal para el Estado de Morelos'}]
    srcs = [g[0]['source'] for g in gold_refs('q', comps)]
    assert srcs == ['Código Nacional de Procedimientos Civiles y Familiares.md', 'CPROFAMEM.md', 'CFAMILIAREM.md',
                    'Código Nacional de Procedimientos Penales.md', 'Código PENALEM.md']
