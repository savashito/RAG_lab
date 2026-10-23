"""
Pruebas del cliente del reranker (shared/rerank_client.py): la plantilla de Qwen3-Reranker y el orden del resultado.

    uv run --all-extras --with pytest python -m pytest tests/test_rerank_client.py
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import shared.rerank_client as rc  # noqa: E402


def test_formato_qwen3():
    q, docs = rc.formato_qwen3('pena del robo', ['El robo se sanciona…'])
    assert q.startswith('<|im_start|>system') and '<Query>: pena del robo' in q and '<Instruct>:' in q
    assert docs[0].startswith('<Document>: El robo se sanciona…') and docs[0].endswith('</think>\n\n')


def test_rerank_aplica_formato_y_ordena(monkeypatch):
    enviado = {}

    def falso(req, timeout=60):
        enviado.update(json.loads(req.data))
        return io.StringIO(json.dumps({'results': [{'index': 0, 'relevance_score': 0.1}, {'index': 1, 'relevance_score': 0.9}]}))
    monkeypatch.setattr(rc.urllib.request, 'urlopen', falso)
    out = rc.RerankClient(url='http://x', formato='qwen3').rerank('pena del robo', ['a', 'b'])
    assert out == [(1, 0.9), (0, 0.1)]
    assert '<Query>: pena del robo' in enviado['query'] and enviado['documents'][0].startswith('<Document>: a')
    rc.RerankClient(url='http://x', formato='').rerank('pena del robo', ['a', 'b'])
    assert enviado['query'] == 'pena del robo'   # sin formato: tal cual (rerankers tipo TEI)


def test_sin_url_no_hace_nada():
    assert rc.RerankClient(url='').rerank('q', ['a', 'b']) == [(0, 0.0), (1, 0.0)]
