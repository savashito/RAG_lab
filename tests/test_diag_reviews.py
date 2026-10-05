"""Visto bueno humano sobre el diagnóstico de chunking."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.diag_reviews import DOC, check_signature, doc_signature, review_state, signature_for  # noqa: E402

DIAG = {'stats': {'chunks': 950},
        'checks': [{'id': 'secuencia', 'level': 'bad', 'summary': 'Faltan 204 artículos'},
                   {'id': 'repetido', 'level': 'warn', 'summary': '3 líneas repetidas'},
                   {'id': 'estrategia', 'level': 'ok', 'summary': 'por artículo'}]}


def rv(check_id, decision='ok', diag=DIAG):
    return {'check_id': check_id, 'decision': decision, 'note': '', 'reviewer': 'k@x', 'updated_at': 't',
            'signature': signature_for(diag, check_id)}


def test_pending_until_every_warning_is_reviewed():
    assert review_state(DIAG, [])['state'] == 'pending'
    assert review_state(DIAG, [rv('secuencia')])['state'] == 'pending'
    assert review_state(DIAG, [rv('secuencia'), rv('repetido')])['state'] == 'reviewed'


def test_document_level_ok_covers_all_warnings():
    st = review_state(DIAG, [rv(DOC)])
    assert st['state'] == 'reviewed' and st['doc']['stale'] is False


def test_fix_wins():
    assert review_state(DIAG, [rv(DOC), rv('repetido', 'fix')])['state'] == 'fix'


def test_no_warnings_is_ok():
    clean = {'stats': {'chunks': 10}, 'checks': [{'id': 'estrategia', 'level': 'ok', 'summary': 'x'}]}
    assert review_state(clean, [])['state'] == 'ok'


def test_review_goes_stale_when_the_warning_changes():
    reviews = [rv('secuencia'), rv('repetido'), rv(DOC)]
    changed = {'stats': {'chunks': 950},
               'checks': [{'id': 'secuencia', 'level': 'bad', 'summary': 'Faltan 10 artículos'},
                          {'id': 'repetido', 'level': 'warn', 'summary': '3 líneas repetidas'}]}
    st = review_state(changed, reviews)
    assert st['checks']['secuencia']['stale'] and not st['checks']['repetido']['stale']
    assert st['doc']['stale'] and st['state'] == 'pending'


def test_signatures():
    assert signature_for(DIAG, 'nope') is None
    assert signature_for(DIAG, DOC) == doc_signature(DIAG)
    assert signature_for(DIAG, 'repetido') == check_signature(DIAG['checks'][1])
