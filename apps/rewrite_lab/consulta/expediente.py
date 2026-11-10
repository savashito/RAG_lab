"""
Expediente de la consulta: los datos del caso que el programa anota mientras conversa con la persona.

No llama al LLM ni a la base: recibe lo que el LLM extrajo y el catálogo de casos, y decide qué falta y qué reglas
aplican. Diseño: 06_evaluation/estudio_ronda3_2026-11-10/diseno_maquina_estados.md.

El expediente es un dict:
    {'tipos_caso': ['imagenes_intimas'],          # ids del catálogo; [] = todavía no se sabe
     'datos': {'lugar_hechos': 'Querétaro', 'pide_dinero': 'si', 'edad_victima': 24},
     'no_sabe': ['monto'],                         # la persona dijo que no sabe: cuenta como contestado
     'preguntas': {'lugar_hechos': 2},             # cuántas veces se preguntó cada dato
     'orientados': ['imagenes_intimas']}           # tipos de caso de la última orientación

Valores de cada dato, según su `tipo` en el catálogo:
    si_no → 'si' | 'no' · numero → int/float · opcion → uno de `opciones` · estado → nombre oficial de la entidad.

Un dato con `obligatorio: true` (el lugar de los hechos) no acepta «no sé»: se sigue preguntando. Es la decisión del
diseño: es mejor no orientar que orientar con la ley de otro estado.
"""
from __future__ import annotations

import re
import unicodedata

NO_SABE = 'no_sabe'
# Entidad federativa (nombre oficial, como lo devuelve jurisdiction_gate.normalizar_estado) → código en el catálogo.
CODIGO_DE_ESTADO = {'Ciudad de México': 'cdmx', 'Querétaro': 'queretaro', 'Estado de México': 'edomex',
                    'Morelos': 'morelos'}


def _sin_acentos(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


def nuevo() -> dict:
    return {'tipos_caso': [], 'datos': {}, 'no_sabe': [], 'preguntas': {}, 'orientados': []}


def normalizar_valor(dato: dict, valor):
    """Valor que extrajo el LLM → valor del tipo del dato, o None si no sirve."""
    if valor is None or valor == '':
        return None
    if isinstance(valor, str) and _sin_acentos(valor).strip().lower().replace(' ', '_') in (NO_SABE, 'no_se', 'nose'):
        return NO_SABE
    tipo = dato.get('tipo', 'si_no')
    if tipo == 'si_no':
        v = _sin_acentos(str(valor)).strip().lower()
        return 'si' if v in ('si', 'true', '1', 'yes') else 'no' if v in ('no', 'false', '0') else None
    if tipo == 'numero':
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            return valor
        m = re.search(r'-?\d+(?:\.\d+)?', str(valor).replace(',', ''))
        return (float(m.group(0)) if '.' in m.group(0) else int(m.group(0))) if m else None
    if tipo == 'opcion':
        v = str(valor).strip()
        return v if v in (dato.get('opciones') or []) else None
    return str(valor).strip()          # estado y texto: tal cual (el estado ya viene normalizado)


def combinar(expediente: dict, extraido: dict, catalogo: dict) -> tuple[dict, list[str]]:
    """Agrega al expediente los datos que extrajo el LLM. Un dato nuevo reemplaza al anterior (la persona corrigió).
    Devuelve (expediente nuevo, ids de los datos que cambiaron). Ignora ids que no están en el catálogo."""
    por_id = {d['id']: d for d in catalogo.get('datos', [])}
    exp = {**expediente, 'datos': dict(expediente.get('datos', {})), 'no_sabe': list(expediente.get('no_sabe', []))}
    cambios = []
    for k, v in (extraido or {}).items():
        dato = por_id.get(k)
        if not dato:
            continue
        v = normalizar_valor(dato, v)
        if v is None:
            continue
        if v == NO_SABE:
            if dato.get('obligatorio') or k in exp['no_sabe'] or k in exp['datos']:
                continue
            exp['no_sabe'].append(k)
            cambios.append(k)
        elif exp['datos'].get(k) != v:
            exp['datos'][k] = v
            if k in exp['no_sabe']:
                exp['no_sabe'].remove(k)
            cambios.append(k)
    return exp, cambios


def datos_necesarios(expediente: dict, catalogo: dict) -> list[dict]:
    """Datos que pide el caso, en orden: primero los de todos los casos (`generales`), luego los de cada tipo de caso
    del expediente. Sin tipo de caso, solo los generales."""
    por_id = {d['id']: d for d in catalogo.get('datos', [])}
    ids = list(catalogo.get('generales', ['lugar_hechos']))
    tipos = {t['id']: t for t in catalogo.get('tipos_caso', [])}
    for t in expediente.get('tipos_caso', []):
        ids += [d for d in tipos.get(t, {}).get('datos', []) if d not in ids]
    return [por_id[i] for i in ids if i in por_id and por_id[i].get('preguntar', True)]


def datos_faltantes(expediente: dict, catalogo: dict) -> list[dict]:
    """Los datos necesarios sin valor ni «no sé», en el orden en que se preguntan. Lista vacía = ya están todos."""
    hay = set(expediente.get('datos', {})) | set(expediente.get('no_sabe', []))
    return [d for d in datos_necesarios(expediente, catalogo) if d['id'] not in hay]


# ── Reglas: datos → delitos ──────────────────────────────────────────────────────
_COND = re.compile(r'^\s*(?:(?P<no>NO)\s+(?P<solo>\w+)|(?P<id>\w+)\s*(?:(?P<op><=|>=|!=|=|<|>|\ben\b)\s*(?P<val>.+?))?)\s*$')


def evaluar(expr: str, datos: dict):
    """Una condición de `cuando` → True, False o None (no se puede saber: falta el dato o «no sé»).
    Formas: «dato» (= si), «NO dato» (= no), «dato = valor», «dato != valor», «dato < 18» (también <=, >, >=),
    «dato en [a, b]»."""
    m = _COND.match(expr or '')
    if not m:
        raise ValueError(f'Condición que no entiendo: «{expr}»')
    if m.group('no'):
        v = datos.get(m.group('solo'))
        return None if v in (None, NO_SABE) else v == 'no'
    v = datos.get(m.group('id'))
    if v in (None, NO_SABE):
        return None
    op, val = m.group('op'), (m.group('val') or '').strip()
    if not op:
        return v == 'si'
    if op == 'en':
        opciones = [x.strip().strip('\'"') for x in val.strip('[]').split(',')]
        return str(v) in opciones
    if op in ('=', '!='):
        igual = str(v).lower() == val.strip('\'"').lower()
        return igual if op == '=' else not igual
    try:
        a, b = float(v), float(val)
    except (TypeError, ValueError):
        return None
    return {'<': a < b, '<=': a <= b, '>': a > b, '>=': a >= b}[op]


def reglas_aplicables(expediente: dict, catalogo: dict, solo_confirmadas: bool = False) -> list[dict]:
    """Reglas de los tipos de caso del expediente cuyas condiciones no son falsas.
    Cada una lleva `incierta=True` si alguna condición no se pudo evaluar (falta el dato o la persona no sabe)."""
    datos = {**expediente.get('datos', {}), **{k: NO_SABE for k in expediente.get('no_sabe', [])}}
    tipos = set(expediente.get('tipos_caso', []))
    out = []
    for r in catalogo.get('reglas', []):
        if r.get('tipo_caso') not in tipos or r.get('estado') == 'descartada':
            continue
        if solo_confirmadas and r.get('estado') != 'confirmada':
            continue
        valores = [evaluar(c, datos) for c in r.get('cuando') or []]
        if False in valores:
            continue
        out.append({**r, 'incierta': None in valores})
    return out


def codigos_del_caso(expediente: dict, reglas: list[dict]) -> list[str]:
    """Qué códigos del catálogo usar: el del estado de los hechos (si está en el corpus) y el federal si alguna regla
    solo tiene artículos federales o el caso es de un tipo federal."""
    out = []
    est = CODIGO_DE_ESTADO.get(expediente.get('datos', {}).get('lugar_hechos'))
    if est:
        out.append(est)
    if any(r.get('articulos', {}).get('federal') and not any(r['articulos'].get(k) for k in CODIGO_DE_ESTADO.values())
           for r in reglas):
        out.append('federal')
    return out


def articulos_del_caso(expediente: dict, reglas: list[dict]) -> dict[str, list[str]]:
    """{código: [artículos]} de las reglas aplicables, solo de los códigos del caso, sin repetir."""
    out: dict[str, list[str]] = {}
    for cod in codigos_del_caso(expediente, reglas):
        for r in reglas:
            for a in r.get('articulos', {}).get(cod, []):
                if a not in out.setdefault(cod, []):
                    out[cod].append(a)
    return out
