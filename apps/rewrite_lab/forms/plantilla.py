"""Llenado de plantillas de formularios (sin LLM): el texto legal sale de la plantilla revisada
y solo se sustituyen los datos de la persona. Así Gemma no puede inventar cláusulas.

Sintaxis de la plantilla (forms/<formulario>/plantilla.md):
    {campo}                      valor del campo ({x.sub} dentro de un CADA)
    [SI campo] … [/SI]           solo si el campo es verdadero o no está vacío
    [SI NO campo] … [/SI]        solo si el campo es falso o está vacío
    [SI campo = valor] … [/SI]   solo si el campo tiene ese valor
    [CADA x EN lista] … [/CADA]  se repite por cada elemento de la lista
    {#pruebas} {#R medidas} {#A pretensiones}
                                 numeración automática (1, 2, 3… / I, II, III… / A, B, C…) por serie: si un
                                 bloque condicional se omite, los siguientes no brincan números
Los bloques se pueden anidar. Las mismas condiciones («campo», «NO campo», «campo = valor»)
se usan en el `si:` de los campos de formulario.yaml.
"""
from __future__ import annotations

import re

_TOKEN = re.compile(r'\[SI (?P<si>[^\]]+)\]|\[/SI\]|\[CADA (?P<var>\w+) EN (?P<lista>\w+)\]|\[/CADA\]')
_FIELD = re.compile(r'\{([\w.]+)\}')
_COUNTER = re.compile(r'\{#(R |A )?(\w+)\}')
_COMMENT = re.compile(r'<!--.*?-->\n?', re.S)
_ROMAN = [(10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I')]


def _roman(n: int) -> str:
    out = ''
    for value, sym in _ROMAN:
        while n >= value:
            out, n = out + sym, n - value
    return out


def _lookup(data: dict, name: str):
    value = data
    for part in name.split('.'):
        value = value.get(part) if isinstance(value, dict) else None
    return value


def condition(expr: str, data: dict) -> bool:
    """Evalúa «campo», «NO campo» o «campo = valor»."""
    expr = expr.strip()
    if '=' in expr:
        name, _, want = (s.strip() for s in expr.partition('='))
        return str(_lookup(data, name) or '') == want
    negate = expr.startswith('NO ')
    value = _lookup(data, expr[3:].strip() if negate else expr)
    truthy = bool(value) and value not in ('no', 'false', '0')
    return not truthy if negate else truthy


def _parse(text: str):
    """Árbol: lista de str | ('si', expr, hijos) | ('cada', var, lista, hijos)."""
    root, stack, pos = [], [], 0
    current = root
    for m in _TOKEN.finditer(text):
        current.append(text[pos:m.start()])
        pos = m.end()
        tok = m.group(0)
        if m.group('si'):
            node = ('si', m.group('si'), [])
        elif m.group('var'):
            node = ('cada', m.group('var'), m.group('lista'), [])
        else:
            want = 'si' if tok == '[/SI]' else 'cada'
            if not stack or stack[-1][0][0] != want:
                raise ValueError(f'{tok} sin su apertura (cerca de: {text[max(0, m.start() - 60):m.start()]!r})')
            _, current = stack.pop()
            continue
        current.append(node)
        stack.append((node, current))
        current = node[-1]
    if stack:
        raise ValueError(f'bloque sin cerrar: {stack[-1][0][:2]}')
    current.append(text[pos:])
    return root


def _render(nodes, data: dict, missing: list) -> str:
    out = []
    for n in nodes:
        if isinstance(n, str):
            def field(m):
                v = _lookup(data, m.group(1))
                if v in (None, ''):
                    missing.append(m.group(1))
                    return f'[FALTA: {m.group(1)}]'
                return str(v)
            out.append(_FIELD.sub(field, n))
        elif n[0] == 'si':
            if condition(n[1], data):
                out.append(_render(n[2], data, missing))
        else:
            _, var, lista, children = n
            for i, item in enumerate(_lookup(data, lista) or [], 1):
                out.append(_render(children, {**data, var: {**item, 'numero': i}}, missing))
    return ''.join(out)


def _number(text: str) -> str:
    counters: dict = {}
    def repl(m):
        counters[m.group(2)] = counters.get(m.group(2), 0) + 1
        n = counters[m.group(2)]
        return {'R ': _roman(n), 'A ': chr(64 + n)}.get(m.group(1), str(n))
    return _COUNTER.sub(repl, text)


def fill(template: str, data: dict) -> tuple[str, list[str]]:
    """(documento, campos que faltaron). Quita los comentarios <!-- --> de revisión."""
    missing: list[str] = []
    text = _number(_render(_parse(_COMMENT.sub('', template)), data, missing))
    text = re.sub(r'\n{3,}', '\n\n', text).strip() + '\n'
    return text, sorted(set(missing))
