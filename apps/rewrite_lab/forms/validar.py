"""Validación de un paquete de formulario (formulario.yaml + plantilla.md + ejemplos.yaml).

La usan el editor de formularios (antes de guardar), el arranque (al sembrar desde el repo) y los
tests. Devuelve una lista de errores legibles; lista vacía = el paquete es válido.
"""
from __future__ import annotations

import re

import yaml

from forms.plantilla import fill

TIPOS = {'texto', 'texto_largo', 'fecha', 'si_no', 'opcion', 'lista'}
ESTADOS = ('borrador', 'revisado', 'publicado')
FORMATOS = ('telefono', 'correo', 'fecha_completa')


def cargar(spec_yaml: str, ejemplos_yaml: str = '') -> tuple[dict | None, dict, list[str]]:
    """(spec, ejemplos, errores de sintaxis YAML)."""
    errs = []
    try:
        spec = yaml.safe_load(spec_yaml or '')
    except yaml.YAMLError as e:
        return None, {}, [f'formulario.yaml no es YAML válido: {e}']
    try:
        ejemplos = yaml.safe_load(ejemplos_yaml or '') or {}
    except yaml.YAMLError as e:
        ejemplos, errs = {}, [f'ejemplos.yaml no es YAML válido: {e}']
    if not isinstance(spec, dict):
        return None, ejemplos, errs + ['formulario.yaml debe ser un objeto (clave: valor).']
    return spec, ejemplos if isinstance(ejemplos, dict) else {}, errs


def validar(spec_yaml: str, plantilla: str, ejemplos_yaml: str = '') -> list[str]:
    spec, ejemplos, errs = cargar(spec_yaml, ejemplos_yaml)
    if spec is None:
        return errs
    for k in ('id', 'titulo', 'tema', 'descripcion', 'campos'):
        if not spec.get(k):
            errs.append(f'formulario.yaml: falta «{k}».')
    if spec.get('id') and not re.fullmatch(r'[a-z0-9_]+', str(spec['id'])):
        errs.append('formulario.yaml: «id» solo admite minúsculas, números y guion bajo.')
    if spec.get('estado', 'borrador') not in ESTADOS:
        errs.append(f'formulario.yaml: «estado» debe ser uno de {", ".join(ESTADOS)}.')
    campos = spec.get('campos') or []
    ids = set()
    for i, c in enumerate(campos, 1):
        if not isinstance(c, dict) or not c.get('id'):
            errs.append(f'campo #{i}: falta «id».')
            continue
        if c['id'] in ids:
            errs.append(f'campo «{c["id"]}»: id repetido.')
        ids.add(c['id'])
        if c.get('tipo') not in TIPOS:
            errs.append(f'campo «{c["id"]}»: «tipo» debe ser uno de {", ".join(sorted(TIPOS))}.')
        if not c.get('automatico') and not c.get('pregunta'):
            errs.append(f'campo «{c["id"]}»: falta «pregunta».')
        if c.get('tipo') == 'opcion' and not isinstance(c.get('opciones'), dict):
            errs.append(f'campo «{c["id"]}»: un campo «opcion» necesita «opciones» (clave: texto).')
        if c.get('formato') and c['formato'] not in FORMATOS:
            errs.append(f'campo «{c["id"]}»: «formato» debe ser uno de {", ".join(FORMATOS)}.')
        if c.get('requiere') is not None and not (isinstance(c['requiere'], list) and all(isinstance(x, str) for x in c['requiere'])):
            errs.append(f'campo «{c["id"]}»: «requiere» debe ser una lista de textos.')
        if c.get('tipo') == 'lista' and not c.get('subcampos'):
            errs.append(f'campo «{c["id"]}»: un campo «lista» necesita «subcampos».')
    errs += _plantilla_vs_campos(plantilla, campos)
    try:
        fill(plantilla or '', {})
    except ValueError as e:
        errs.append(f'plantilla.md: {e}')
        return errs
    for nombre, datos in ejemplos.items():
        _, faltan = fill(plantilla, datos or {})
        if faltan:
            errs.append(f'ejemplo «{nombre}»: la plantilla quedó con datos faltantes: {", ".join(faltan)}.')
    return errs


def _plantilla_vs_campos(plantilla: str, campos: list) -> list[str]:
    errs = []
    ids = {c.get('id') for c in campos if isinstance(c, dict)}
    subs = {f"{c['id']}.{s.get('id')}" for c in campos if isinstance(c, dict) for s in c.get('subcampos') or []}
    body = re.sub(r'<!--.*?-->', '', plantilla or '', flags=re.S)
    loops = dict(re.findall(r'\[CADA (\w+) EN (\w+)\]', body))
    for name in sorted(set(re.findall(r'\{([\w.]+)\}', body))):
        head, _, sub = name.partition('.')
        if sub:
            if head not in loops or (sub != 'numero' and f'{loops[head]}.{sub}' not in subs):
                errs.append(f'plantilla.md usa {{{name}}}, que no es un subcampo definido.')
        elif name not in ids:
            errs.append(f'plantilla.md usa {{{name}}}, pero formulario.yaml no define ese campo.')
    conds = re.findall(r'\[SI ([^\]]+)\]', body) + [c['si'] for c in campos if isinstance(c, dict) and c.get('si')]
    for expr in conds:
        field = re.sub(r'^NO ', '', expr.strip()).split('=')[0].strip().split('.')[0]
        if field not in ids | set(loops):
            errs.append(f'condición «{expr}»: el campo «{field}» no existe.')
    return errs
