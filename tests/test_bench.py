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
