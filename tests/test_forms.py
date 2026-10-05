"""Plantillas de formularios (apps/rewrite_lab/forms): llenado sin LLM y consistencia con formulario.yaml."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import yaml

APP = Path(__file__).resolve().parents[1] / 'apps' / 'rewrite_lab'
sys.path.insert(0, str(APP))

from forms.plantilla import condition, fill  # noqa: E402

FORMS = sorted(p for p in (APP / 'forms').iterdir() if (p / 'formulario.yaml').is_file())


def test_fields_conditions_and_lists():
    tpl = ('Hola {nombre}.[SI hijos] Hijos:[CADA h EN hijos] {h.numero}) {h.nombre};[/CADA][/SI]'
           '[SI NO hijos] Sin hijos.[/SI][SI regimen = separacion] Separación.[/SI]')
    doc, missing = fill(tpl, {'nombre': 'Ana', 'hijos': [{'nombre': 'Luis'}, {'nombre': 'Eva'}], 'regimen': 'separacion'})
    assert doc.strip() == 'Hola Ana. Hijos: 1) Luis; 2) Eva; Separación.'
    doc, _ = fill(tpl, {'nombre': 'Ana', 'hijos': [], 'regimen': 'sociedad'})
    assert doc.strip() == 'Hola Ana. Sin hijos.'


def test_missing_fields_are_marked_not_invented():
    doc, missing = fill('Nombre: {nombre}. Cónyuge: {conyuge}.', {'nombre': 'Ana'})
    assert '[FALTA: conyuge]' in doc and missing == ['conyuge']


def test_auto_numbering_skips_omitted_blocks():
    tpl = '{#p}. a [SI x]{#p}. b [/SI]{#p}. c | {#R m} {#R m} | {#A l} {#A l}'
    assert fill(tpl, {'x': False})[0].strip() == '1. a 2. c | I II | A B'
    assert fill(tpl, {'x': True})[0].strip() == '1. a 2. b 3. c | I II | A B'


def test_review_comments_are_removed():
    assert fill('a<!-- REVISAR: algo -->b', {})[0].strip() == 'ab'


def test_unbalanced_blocks_fail_loudly():
    with pytest.raises(ValueError):
        fill('[SI x] sin cerrar', {})
    with pytest.raises(ValueError):
        fill('cierre sin abrir [/SI]', {})


def test_condition_syntax():
    assert condition('x', {'x': True}) and not condition('x', {'x': False}) and not condition('x', {})
    assert condition('NO x', {'x': False}) and condition('r = a', {'r': 'a'}) and not condition('r = a', {'r': 'b'})


@pytest.mark.parametrize('form', FORMS, ids=lambda p: p.name)
def test_template_and_form_definition_agree(form):
    spec = yaml.safe_load((form / 'formulario.yaml').read_text())
    tpl = (form / 'plantilla.md').read_text()
    ids = {c['id'] for c in spec['campos']}
    subs = {f"{c['id']}.{s['id']}" for c in spec['campos'] for s in c.get('subcampos', [])}
    body = re.sub(r'<!--.*?-->', '', tpl, flags=re.S)
    loop_vars = dict(re.findall(r'\[CADA (\w+) EN (\w+)\]', body))
    for name in re.findall(r'\{([\w.]+)\}', body):
        head, _, sub = name.partition('.')
        if sub:
            assert head in loop_vars and (sub == 'numero' or f'{loop_vars[head]}.{sub}' in subs), name
        else:
            assert name in ids, f'la plantilla usa {{{name}}} pero formulario.yaml no lo define'
    for expr in re.findall(r'\[SI ([^\]]+)\]', body) + [c['si'] for c in spec['campos'] if 'si' in c]:
        field = re.sub(r'^NO ', '', expr).split('=')[0].strip()
        assert field.split('.')[0] in ids | set(loop_vars), f'condición sobre campo desconocido: {expr}'


@pytest.mark.parametrize('form', FORMS, ids=lambda p: p.name)
def test_examples_fill_completely(form):
    examples = form / 'ejemplos.yaml'
    if not examples.is_file():
        pytest.skip('sin ejemplos')
    tpl = (form / 'plantilla.md').read_text()
    for name, data in yaml.safe_load(examples.read_text()).items():
        _, missing = fill(tpl, data)
        assert missing == [], f'{name}: faltan {missing}'
