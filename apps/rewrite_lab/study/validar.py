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
    for p in (spec.get('perfil') or []) + [q for e in spec.get('escenarios') or [] if isinstance(e, dict)
                                           for q in e.get('preguntas') or []]:
        if isinstance(p, dict):
            if isinstance(p.get('opciones'), dict):
                p['opciones'] = {_clave(k): v for k, v in p['opciones'].items()}
            if 'correcta' in p:
                p['correcta'] = _clave(p['correcta'])
    return spec, []


def _clave(k) -> str:
    """YAML lee `no:` y `si:`/`yes:` sin comillas como booleanos; aquí vuelven a ser 'no' / 'si'."""
    return 'si' if k is True else 'no' if k is False else str(k)


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
        if not isinstance(p, dict) or not p.get('id') or not p.get('pregunta') or not isinstance(p.get('opciones'), dict):
            errs.append('cada pregunta de «perfil» necesita id, pregunta y opciones (clave: texto).')
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
        for k in ('titulo', 'texto', 'referencia'):
            if not e.get(k):
                errs.append(f'escenario «{eid}»: falta «{k}».')
        if not e.get('preguntas'):
            errs.append(f'escenario «{eid}»: necesita al menos una pregunta de comprensión.')
        pids = set()
        for p in e.get('preguntas') or []:
            if not isinstance(p, dict) or not p.get('id') or not p.get('texto'):
                errs.append(f'escenario «{eid}»: cada pregunta necesita id y texto.')
                continue
            if p['id'] in pids:
                errs.append(f'escenario «{eid}»: pregunta «{p["id"]}» repetida.')
            pids.add(p['id'])
            ops = p.get('opciones')
            if not isinstance(ops, dict) or len(ops) < 2:
                errs.append(f'escenario «{eid}», pregunta «{p["id"]}»: necesita al menos 2 «opciones».')
            elif p.get('correcta') not in ops:
                errs.append(f'escenario «{eid}», pregunta «{p["id"]}»: «correcta» debe ser una de sus opciones.')
        gold = e.get('gold') or []
        if not isinstance(gold, list) or not all(isinstance(g, str) for g in gold):
            errs.append(f'escenario «{eid}»: «gold» debe ser una lista de textos.')
        elif gold_refs:
            for g in gold:
                if not gold_refs(g):
                    errs.append(f'escenario «{eid}»: no reconozco ley y artículo en el gold «{g}».')
    n = spec.get('escenarios_por_persona', len(escenarios))
    if not isinstance(n, int) or n < 1 or n > max(len(escenarios), 1):
        errs.append('«escenarios_por_persona» debe estar entre 1 y el número de escenarios.')
    return errs


def vista_publica(spec: dict, asignados: list[str]) -> dict:
    """Lo que ve una persona participante: sin gold, sin respuesta de referencia y sin la opción
    correcta de las preguntas de comprensión."""
    por_id = {e['id']: e for e in spec.get('escenarios') or []}
    return {
        'titulo': spec.get('titulo'),
        'consentimiento': spec.get('consentimiento'),
        'perfil': spec.get('perfil') or [],
        'sus': SUS if (spec.get('cierre') or {}).get('sus', True) else [],
        'abiertas': (spec.get('cierre') or {}).get('preguntas_abiertas') or [],
        'max_turnos': int((spec.get('asistente') or {}).get('max_turnos', 12)),
        'escenarios': [{'id': eid, 'titulo': por_id[eid]['titulo'], 'texto': por_id[eid]['texto'],
                        'preguntas': [{'id': p['id'], 'texto': p['texto'], 'opciones': p['opciones']}
                                      for p in por_id[eid].get('preguntas') or []]}
                       for eid in asignados if eid in por_id],
    }
