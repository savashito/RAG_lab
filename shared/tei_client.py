"""
shared/tei_client.py — cliente ligero para el servidor TEI (embeddings) vía túnel.

Envuelve /info, /tokenize y /embed con:
  * reintentos + backoff (el túnel a veces corta la respuesta: IncompleteRead),
  * peticiones en paralelo (el túnel embebe ~10 textos/s en serie),
  * caché en disco de vectores (embeber ~7k chunks tarda; la caché lo hace instantáneo).

Lo usan el notebook de exploración de chunking y el de recuperación, para no
duplicar la lógica ni reembeber lo ya calculado.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.client import IncompleteRead
from pathlib import Path

import numpy as np


class TEIClient:
    def __init__(self, url: str | None = None, cache_dir: str | Path | None = None):
        self.url = (url or os.environ.get('TEI_URL', 'http://localhost:8085')).rstrip('/')
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._info: dict | None = None   # perezoso: sólo se pide /info si hace falta el servidor

    def _get_info(self) -> dict:
        """Lee /info la primera vez que se necesita el servidor (no en el constructor),
        para que las operaciones 100% de caché funcionen aunque el túnel esté caído."""
        if self._info is None:
            for attempt in range(4):
                try:
                    self._info = json.load(urllib.request.urlopen(self.url + '/info', timeout=10))
                    break
                except (urllib.error.URLError, TimeoutError, ConnectionError):
                    if attempt == 3:
                        raise
                    time.sleep(1.5 * (attempt + 1))
        return self._info

    @property
    def model_id(self) -> str:
        return self._get_info()['model_id']

    @property
    def ctx(self) -> int:
        return int(self._get_info().get('max_input_length') or 0)

    @property
    def max_batch(self) -> int:
        return int(self._get_info().get('max_client_batch_size') or 32)

    # ── HTTP resiliente ──────────────────────────────────────────────────────────
    def _post(self, path: str, payload: dict, timeout: int = 120, retries: int = 4):
        data = json.dumps(payload).encode()
        for attempt in range(retries):
            try:
                req = urllib.request.Request(self.url + path, data=data,
                                             headers={'Content-Type': 'application/json'})
                return json.load(urllib.request.urlopen(req, timeout=timeout))
            except (IncompleteRead, urllib.error.URLError, TimeoutError, ConnectionError):
                if attempt == retries - 1:
                    raise
                time.sleep(1.5 * (attempt + 1))

    def _batched(self, items, batch):
        items = list(items)
        return [items[i:i + batch] for i in range(0, len(items), batch)]

    def _map(self, path, batches, workers, build):
        with ThreadPoolExecutor(max_workers=workers) as ex:
            return list(ex.map(lambda b: self._post(path, build(b)), batches))

    # ── API ──────────────────────────────────────────────────────────────────────
    def token_counts(self, texts, batch: int = 8, workers: int = 4) -> list[int]:
        """Número de tokens por texto (según el tokenizer del modelo servido). Lotes
        chicos: /tokenize devuelve los IDs completos (respuesta pesada)."""
        results = self._map('/tokenize', self._batched(texts, batch), workers, lambda b: {'inputs': b})
        return [len(t) for b in results for t in b]

    def _hash(self, s: str) -> str:
        return hashlib.md5(s.encode('utf-8')).hexdigest()

    def embed(self, texts, batch: int = 32, workers: int = 8, use_cache: bool = True,
              cache_key_model: str | None = None) -> np.ndarray:
        """Vectores L2-normalizados (float32). Cachea por hash de (modelo + textos).

        Caché en dos niveles: la lista completa (ruta rápida) y, si falta, POR LOTE
        —resumible—: si el túnel se cae a media corrida, lo ya embebido queda en disco
        y una re-ejecución continúa desde donde iba en vez de empezar de cero.

        `cache_key_model` fuerza el modelo de la llave de caché, para LEER embeddings
        hechos con otro modelo aunque TEI sirva ahora un reranker. Si hay que embeber
        de verdad y el modelo servido no coincide, es un error explícito."""
        texts = list(texts)
        key_model = cache_key_model or (self.model_id if self._info is not None else None) or self.model_id
        full_cache = None
        if use_cache and self.cache_dir:
            full_cache = self.cache_dir / f'{self._hash(key_model + chr(10) + chr(10).join(texts))}.npy'
            if full_cache.exists():
                return np.load(full_cache)

        batches = self._batched(texts, min(batch, self.max_batch))
        results: list = [None] * len(batches)
        batch_dir = (self.cache_dir / 'batches') if (use_cache and self.cache_dir) else None
        if batch_dir:
            batch_dir.mkdir(exist_ok=True)
        missing = []
        for bi, b in enumerate(batches):
            bc = batch_dir / f'{self._hash(key_model + chr(10) + chr(10).join(b))}.npy' if batch_dir else None
            if bc is not None and bc.exists():
                results[bi] = np.load(bc)
            else:
                missing.append(bi)

        if missing and cache_key_model and cache_key_model != self.model_id:
            raise RuntimeError(
                f'Faltan {len(missing)} lotes de embeddings para {cache_key_model!r}, '
                f'pero TEI sirve {self.model_id!r}. Sirve ese embedder para completarlos.')

        def emb(bi):
            arr = np.asarray(self._post('/embed', {'inputs': batches[bi], 'normalize': True, 'truncate': True}),
                             dtype=np.float32)
            if batch_dir:
                np.save(batch_dir / f'{self._hash(key_model + chr(10) + chr(10).join(batches[bi]))}.npy', arr)
            return bi, arr

        if missing:
            with ThreadPoolExecutor(max_workers=workers) as ex:
                for bi, arr in ex.map(emb, missing):
                    results[bi] = arr

        out = np.concatenate(results, axis=0).astype(np.float32)
        if full_cache is not None:
            np.save(full_cache, out)
        return out

    def rerank(self, query: str, texts, batch: int | None = None) -> list[tuple[int, float]]:
        """Cross-encoder vía /rerank: puntúa (query, texto) y devuelve
        [(índice_original, score), ...] ordenado de mayor a menor. Requiere que TEI
        sirva un modelo RERANKER (p. ej. BAAI/bge-reranker-v2-m3), no el embedder."""
        texts = list(texts)
        batch = batch or self.max_batch
        scored: list[tuple[int, float]] = []
        for start in range(0, len(texts), batch):
            part = texts[start:start + batch]
            for item in self._post('/rerank', {'query': query, 'texts': part, 'return_text': False}):
                scored.append((start + int(item['index']), float(item['score'])))
        return sorted(scored, key=lambda x: -x[1])
