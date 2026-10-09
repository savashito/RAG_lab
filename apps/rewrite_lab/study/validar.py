"""Validación de la definición de un estudio (estudio.yaml).

Un estudio dice qué escenarios ficticios ve cada participante, con qué configuración responde el
asistente, qué preguntas de comprensión se hacen (opción múltiple, con respuesta correcta) y qué
consentimiento se firma. Lo usan el editor (/estudios), la siembra desde el repo y los tests.
"""
from __future__ import annotations

import re

import yaml

ESTADOS = ('borrador', 'abierto', 'cerrado')
GRUPOS = ('lego', 'estudiante', 'experto')            # quién participa
ROLES_CALIFICADOR = ('estudiante', 'experto')          # quién califica
VEREDICTOS = ('correcta', 'parcial', 'incorrecta', 'no_responde')
DANOS = ('ninguno', 'leve', 'enganoso', 'peligroso')
CITA = ('respalda', 'no_respalda', 'sin_cita')
SI_NO_NS = ('si', 'no', 'no_se')
TIPOS_PERFIL = ('opcion', 'texto', 'escala')          # escala = 1–5
CAMPOS_VARIANTE = ('texto', 'gold', 'referencia', 'preguntas', 'correctas')

# System Usability Scale (Brooke 1996), versión en español. Impares positivas, pares negativas.
SUS = [
    'Creo que me gustaría usar este asistente con frecuencia.',
    'Encontré el asistente innecesariamente complicado.',
    'Pensé que el asistente era fácil de usar.',
    'Creo que necesitaría ayuda de una persona experta para poder usarlo.',
    'Las distintas partes del asistente funcionan bien juntas.',
    'Pensé que había demasiadas inconsistencias en el asistente.',
    'Imagino que la mayoría de las personas aprendería a usarlo muy rápido.',
    'Encontré el asistente muy difícil de usar.',
    'Me sentí con confianza al usar el asistente.',
    'Tuve que aprender muchas cosas antes de poder usarlo.',
]


def cargar(spec_yaml: str) -> tuple[dict | None, list[str]]:
    try:
        spec = yaml.safe_load(spec_yaml or '')
    except yaml.YAMLError as e:
        return None, [f'estudio.yaml no es YAML válido: {e}']
    if not isinstance(spec, dict):
        return None, ['estudio.yaml debe ser un objeto (clave: valor).']
    escenarios = [e for e in spec.get('escenarios') or [] if isinstance(e, dict)]
    variantes = [v for e in escenarios for v in e.get('variantes') or [] if isinstance(v, dict)]
    for p in (spec.get('perfil') or []) + [q for x in escenarios + variantes for q in x.get('preguntas') or []]:
        if isinstance(p, dict):
            if isinstance(p.get('opciones'), dict):
                p['opciones'] = {_clave(k): v for k, v in p['opciones'].items()}
            if 'correcta' in p:
                p['correcta'] = _clave(p['correcta'])
    for v in variantes:
        if isinstance(v.get('correctas'), dict):
            v['correctas'] = {str(k): _clave(x) for k, x in v['correctas'].items()}
    return spec, []


def _clave(k) -> str:
    """YAML lee `no:` y `si:`/`yes:` sin comillas como booleanos; aquí vuelven a ser 'no' / 'si'."""
    return 'si' if k is True else 'no' if k is False else str(k)


def escenario_efectivo(esc: dict, variante: str | None) -> dict:
    """El escenario tal como lo vio una persona: la variante sustituye texto, gold, referencia o
    preguntas, y `correctas: {pregunta: opción}` cambia solo la respuesta correcta de esas preguntas."""
    v = next((x for x in esc.get('variantes') or [] if x.get('id') == variante), None)
    if not v:
        return esc
    out = {**esc, **{k: v[k] for k in ('texto', 'gold', 'referencia', 'preguntas') if k in v}, 'variante': v['id']}
    if v.get('correctas'):
        out['preguntas'] = [dict(p, correcta=v['correctas'].get(p['id'], p.get('correcta'))) for p in out.get('preguntas') or []]
    return out


def _validar_escenario(e: dict, nombre: str, gold_refs, errs: list):
    for k in ('titulo', 'texto', 'referencia'):
        if not e.get(k):
            errs.append(f'{nombre}: falta «{k}».')
    if not e.get('preguntas'):
        errs.append(f'{nombre}: necesita al menos una pregunta de comprensión.')
    pids = set()
    for p in e.get('preguntas') or []:
        if not isinstance(p, dict) or not p.get('id') or not p.get('texto'):
            errs.append(f'{nombre}: cada pregunta necesita id y texto.')
            continue
        if p['id'] in pids:
            errs.append(f'{nombre}: pregunta «{p["id"]}» repetida.')
        pids.add(p['id'])
        ops = p.get('opciones')
        if not isinstance(ops, dict) or len(ops) < 2:
            errs.append(f'{nombre}, pregunta «{p["id"]}»: necesita al menos 2 «opciones».')
        elif p.get('correcta') not in ops:
            errs.append(f'{nombre}, pregunta «{p["id"]}»: «correcta» debe ser una de sus opciones.')
    gold = e.get('gold') or []
    if not isinstance(gold, list) or not all(isinstance(g, str) for g in gold):
        errs.append(f'{nombre}: «gold» debe ser una lista de textos.')
    elif gold_refs:
        for g in gold:
            if not gold_refs(g):
                errs.append(f'{nombre}: no reconozco ley y artículo en el gold «{g}».')


def validar(spec_yaml: str, gold_refs=None) -> list[str]:
    """Errores legibles; lista vacía = válido. `gold_refs(texto)` (opcional) convierte un texto
    "Cita el art. 179 del Código Penal de la Ciudad de México" en grupos de artículos; si se da,
    se revisa que cada `gold` nombre una ley y un artículo reconocibles."""
    spec, errs = cargar(spec_yaml)
    if spec is None:
        return errs
    for k in ('id', 'titulo', 'consentimiento', 'escenarios'):
        if not spec.get(k):
            errs.append(f'falta «{k}».')
    if spec.get('id') and not re.fullmatch(r'[a-z0-9_]+', str(spec['id'])):
        errs.append('«id» solo admite minúsculas, números y guion bajo.')
    if spec.get('estado', 'borrador') not in ESTADOS:
        errs.append(f'«estado» debe ser uno de {", ".join(ESTADOS)}.')
    a = spec.get('asistente') or {}
    if not isinstance(a, dict) or not a.get('tema'):
        errs.append('«asistente.tema» es obligatorio (el tema del corpus que consulta el asistente).')
    for p in spec.get('perfil') or []:
        tipo = (p or {}).get('tipo', 'opcion') if isinstance(p, dict) else None
        if not isinstance(p, dict) or not p.get('id') or not p.get('pregunta') or tipo not in TIPOS_PERFIL:
            errs.append(f'cada pregunta de «perfil» necesita id, pregunta y tipo ({", ".join(TIPOS_PERFIL)}).')
        elif tipo == 'opcion' and not isinstance(p.get('opciones'), dict):
            errs.append(f'perfil «{p["id"]}»: una pregunta de opción necesita «opciones» (clave: texto).')
    escenarios = spec.get('escenarios') or []
    ids = set()
    for i, e in enumerate(escenarios, 1):
        if not isinstance(e, dict) or not e.get('id'):
            errs.append(f'escenario #{i}: falta «id».')
            continue
        eid = e['id']
        if eid in ids:
            errs.append(f'escenario «{eid}»: id repetido.')
        ids.add(eid)
        variantes = e.get('variantes') or []
        if not variantes:
            _validar_escenario(e, f'escenario «{eid}»', gold_refs, errs)
            continue
        vids = set()
        for v in variantes:
            if not isinstance(v, dict) or not v.get('id') or v['id'] in vids:
                errs.append(f'escenario «{eid}»: cada variante necesita un «id» único.')
                continue
            vids.add(v['id'])
            extra = set(v) - {'id', *CAMPOS_VARIANTE}
            if extra:
                errs.append(f'escenario «{eid}», variante «{v["id"]}»: campos no permitidos {sorted(extra)}.')
            ef = escenario_efectivo(e, v['id'])
            for pid in (v.get('correctas') or {}):
                if pid not in {p.get('id') for p in ef.get('preguntas') or []}:
                    errs.append(f'escenario «{eid}», variante «{v["id"]}»: «correctas» menciona la pregunta «{pid}», que no existe.')
            _validar_escenario(ef, f'escenario «{eid}», variante «{v["id"]}»', gold_refs, errs)
    n = spec.get('escenarios_por_persona', len(escenarios))
    if not isinstance(n, int) or n < 1 or n > max(len(escenarios), 1):
        errs.append('«escenarios_por_persona» debe estar entre 1 y el número de escenarios.')
    return errs


def vista_publica(spec: dict, asignados: list[str], variantes: dict | None = None) -> dict:
    """Lo que ve una persona participante: sin gold, sin respuesta de referencia, sin la opción
    correcta de las preguntas de comprensión y sin saber que hay otras variantes."""
    por_id = {e['id']: e for e in spec.get('escenarios') or []}
    vista = []
    for eid in asignados:
        if eid in por_id:
            e = escenario_efectivo(por_id[eid], (variantes or {}).get(eid))
            vista.append({'id': eid, 'titulo': e['titulo'], 'texto': e['texto'],
                          'preguntas': [{'id': p['id'], 'texto': p['texto'], 'opciones': p['opciones']}
                                        for p in e.get('preguntas') or []]})
    return {
        'titulo': spec.get('titulo'),
        'consentimiento': spec.get('consentimiento'),
        'perfil': [{k: p[k] for k in ('id', 'pregunta', 'tipo', 'opciones', 'ayuda', 'obligatorio') if k in p}
                   for p in spec.get('perfil') or []],
        'sus': SUS if (spec.get('cierre') or {}).get('sus', True) else [],
        'abiertas': (spec.get('cierre') or {}).get('preguntas_abiertas') or [],
        'max_turnos': int((spec.get('asistente') or {}).get('max_turnos', 12)),
        'escenarios': vista,
    }


def limpiar_perfil(spec: dict, perfil: dict) -> tuple[dict, list[str]]:
    """Solo los campos definidos y con valores válidos; lista de obligatorios que faltan."""
    out, faltan = {}, []
    for p in spec.get('perfil') or []:
        v, tipo = (perfil or {}).get(p['id']), p.get('tipo', 'opcion')
        if tipo == 'opcion' and v in (p.get('opciones') or {}):
            out[p['id']] = v
        elif tipo == 'texto' and isinstance(v, str) and v.strip():
            out[p['id']] = v.strip()[:120]
        elif tipo == 'escala' and v in (1, 2, 3, 4, 5):
            out[p['id']] = v
        elif p.get('obligatorio', True):
            faltan.append(p['pregunta'])
    return out, faltan
