"""
shared/rerank_client.py — cliente ligero para un reranker cross-encoder servido por
TEI (endpoint /rerank). Reordena una lista de pasajes por relevancia a la consulta.

A diferencia del embedder (bi-encoder: query y pasaje por separado), el reranker mira
query+pasaje JUNTOS, así que puntúa mucho mejor la relevancia fina — a costa de correr
el modelo una vez por candidato. Por eso se usa como SEGUNDA pasada sobre el top-N que
ya trajo la búsqueda densa/léxica, no sobre todo el corpus.

`enabled` es False si no hay RERANK_URL configurado: el reranking queda desactivado y el
llamador sigue con el orden base (el checkbox de la UI no tiene efecto)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


class RerankClient:
    def __init__(self, url: str | None = None):
        self.url = (url if url is not None else os.environ.get('RERANK_URL', '')).rstrip('/')

    @property
    def enabled(self) -> bool:
        return bool(self.url)

    def rerank(self, query: str, texts: list[str], timeout: int = 60) -> list[tuple[int, float]]:
        """Devuelve [(indice_en_texts, score)] ordenado por relevancia desc. Si el reranker
        no está configurado, devuelve el orden original con score 0 (no-op) para que el
        llamador no falle.

        Tolera dos APIs de /rerank:
          · vLLM (Qwen3-Reranker): body {query, documents}; resp {results:[{index, relevance_score}]}.
          · TEI (cross-encoder):   body {query, texts};     resp [{index, score}].
        Se manda `documents` (vLLM) y se parsea cualquiera de las dos formas."""
        if not self.enabled or not texts:
            return [(i, 0.0) for i in range(len(texts))]
        body = json.dumps({'query': query, 'documents': texts}).encode()
        req = urllib.request.Request(self.url + '/rerank', data=body,
                                     headers={'Content-Type': 'application/json'})
        resp = json.load(urllib.request.urlopen(req, timeout=timeout))
        items = resp['results'] if isinstance(resp, dict) else resp
        out = [(int(r['index']), float(r.get('relevance_score', r.get('score', 0.0)))) for r in items]
        out.sort(key=lambda t: -t[1])   # asegura orden desc aunque el server no lo garantice
        return out
