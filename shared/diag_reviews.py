"""Visto bueno humano sobre el diagnóstico de chunking (shared/chunk_diagnostics.py).

Una persona revisa los avisos de un documento y marca cada uno —o el documento entero— como
«revisado, está bien» (ok) o «hay que corregir» (fix), con una nota. Cada visto bueno guarda la
FIRMA de lo que se revisó: si el documento se reingesta y el aviso cambia (otro resumen, otro
nivel), la firma ya no coincide y el visto bueno queda vencido (stale): vuelve a pedir revisión
en lugar de quedar pegado a una versión que ya no existe.

Las revisiones viven en la tabla `ingest_reviews` (main.py); aquí solo la lógica pura.
"""
from __future__ import annotations

import hashlib

DOC = ''   # check_id del visto bueno general del documento


def _h(text: str) -> str:
    return hashlib.sha1(text.encode('utf-8')).hexdigest()[:16]


def check_signature(check: dict) -> str:
    return _h(f"{check.get('id')}|{check.get('level')}|{check.get('summary')}")


def doc_signature(diag: dict) -> str:
    """Cambia si cambia cualquier aviso o el número de chunks (p. ej. tras reingestar)."""
    sigs = sorted(check_signature(c) for c in diag.get('checks', []))
    return _h(f"{(diag.get('stats') or {}).get('chunks')}|" + '|'.join(sigs))


def signature_for(diag: dict, check_id: str) -> str | None:
    """Firma actual del aviso `check_id` (DOC = el documento). None si el aviso no existe."""
    if check_id == DOC:
        return doc_signature(diag)
    c = next((c for c in diag.get('checks', []) if c.get('id') == check_id), None)
    return check_signature(c) if c else None


def review_state(diag: dict, reviews: list[dict]) -> dict:
    """Combina el diagnóstico con las revisiones guardadas.

    `reviews`: [{check_id, decision, note, signature, reviewer, updated_at}].
    Devuelve {'state', 'doc', 'checks'}: `doc` y cada `checks[id]` traen la revisión con
    `stale` (firma vencida). `state`:
      · 'fix'      — alguien marcó «hay que corregir» (vigente);
      · 'reviewed' — visto bueno general vigente, o todos los avisos con visto bueno vigente;
      · 'ok'       — no hay avisos que revisar;
      · 'pending'  — hay avisos sin visto bueno vigente."""
    by_id = {r['check_id']: r for r in reviews}
    out_checks = {}
    for c in diag.get('checks', []):
        r = by_id.get(c.get('id'))
        if r:
            out_checks[c['id']] = dict(r, stale=r['signature'] != check_signature(c))
    doc = by_id.get(DOC)
    doc = dict(doc, stale=doc['signature'] != doc_signature(diag)) if doc else None
    fresh = [r for r in [doc, *out_checks.values()] if r and not r['stale']]
    pending = [c for c in diag.get('checks', []) if c.get('level') != 'ok']
    if any(r['decision'] == 'fix' for r in fresh):
        state = 'fix'
    elif doc and not doc['stale'] and doc['decision'] == 'ok':
        state = 'reviewed'
    elif not pending:
        state = 'ok'
    elif all((r := out_checks.get(c['id'])) and not r['stale'] and r['decision'] == 'ok' for c in pending):
        state = 'reviewed'
    else:
        state = 'pending'
    return {'state': state, 'doc': doc, 'checks': out_checks}
