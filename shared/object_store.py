"""
shared/object_store.py — almacén de objetos (MinIO) para artefactos grandes del lab.

Qué va aquí y qué NO:
  * SÍ: artefactos "escribir una vez, leer de vez en cuando" — el detalle completo de
    una corrida del benchmark (respuestas, chunks, prompts, salida cruda del juez),
    exportaciones de sets de preguntas y, más adelante, PDFs fuente y `.md` limpios.
  * NO: chunks ni vectores (viven en Postgres junto a su embedding: el retrieval los
    necesita juntos) ni nada que se edite o se consulte con filtros (preguntas, métricas).

Config por env (sin pydantic: el venv de prod no lo trae):
  MINIO_ENDPOINT   p. ej. 127.0.0.1:9000 en el servidor
  MINIO_ACCESS_KEY / MINIO_SECRET_KEY
  MINIO_SECURE     true/false (default false: en el servidor se habla por loopback)
  MINIO_BUCKET     default llm-lab
  OBJECT_PREFIX    default rag_lab/ (todo lo de este app cuelga de ahí dentro del bucket)

Si MinIO no está configurado (sin endpoint o sin llaves), cae a una carpeta local
(`OBJECT_STORE_DIR`, default ingestion/.objects) con las MISMAS llaves. Así el app
funciona en local y en prod antes de tener credenciales, y el código no cambia.
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path

LABS = Path(__file__).resolve().parents[1]


class ObjectStore:
    def __init__(self):
        self.endpoint = os.environ.get('MINIO_ENDPOINT', '').strip()
        self.access_key = os.environ.get('MINIO_ACCESS_KEY', '').strip()
        self.secret_key = os.environ.get('MINIO_SECRET_KEY', '').strip()
        self.secure = os.environ.get('MINIO_SECURE', 'false').strip().lower() in ('1', 'true', 'yes')
        self.bucket = os.environ.get('MINIO_BUCKET', 'llm-lab').strip()
        self.prefix = os.environ.get('OBJECT_PREFIX', 'rag_lab/').strip().strip('/') + '/'
        self.local_dir = Path(os.environ.get('OBJECT_STORE_DIR', LABS / 'ingestion' / '.objects'))
        self._client = None
        self.backend = 'minio' if (self.endpoint and self.access_key and self.secret_key) else 'local'

    # ── internos ──────────────────────────────────────────────────────────────────
    def _key(self, key: str) -> str:
        return self.prefix + key.lstrip('/')

    def _minio(self):
        if self._client is None:
            from minio import Minio
            self._client = Minio(self.endpoint, access_key=self.access_key,
                                 secret_key=self.secret_key, secure=self.secure)
            if not self._client.bucket_exists(self.bucket):
                self._client.make_bucket(self.bucket)
        return self._client

    def _local_path(self, key: str) -> Path:
        p = (self.local_dir / self._key(key)).resolve()
        if not p.is_relative_to(self.local_dir.resolve()):   # nada de ../ fuera del store
            raise ValueError(f'llave inválida: {key!r}')
        return p

    # ── API pública (bytes) ───────────────────────────────────────────────────────
    def put_bytes(self, key: str, data: bytes, content_type: str = 'application/octet-stream') -> str:
        """Guarda `data` bajo `key` (relativa al prefijo del app). Devuelve la llave completa."""
        if self.backend == 'minio':
            self._minio().put_object(self.bucket, self._key(key), io.BytesIO(data), len(data),
                                     content_type=content_type)
        else:
            p = self._local_path(key)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        return self._key(key)

    def get_bytes(self, key: str) -> bytes:
        if self.backend == 'minio':
            r = self._minio().get_object(self.bucket, self._key(key))
            try:
                return r.read()
            finally:
                r.close()
                r.release_conn()
        return self._local_path(key).read_bytes()

    def delete(self, key: str) -> None:
        if self.backend == 'minio':
            self._minio().remove_object(self.bucket, self._key(key))
        else:
            self._local_path(key).unlink(missing_ok=True)

    # ── JSON ──────────────────────────────────────────────────────────────────────
    def put_json(self, key: str, obj) -> str:
        raw = json.dumps(obj, ensure_ascii=False, indent=1).encode()
        return self.put_bytes(key, raw, 'application/json')

    def get_json(self, key: str):
        return json.loads(self.get_bytes(key))

    def describe(self) -> dict:
        """Para la UI: dónde se están guardando los artefactos."""
        if self.backend == 'minio':
            return {'backend': 'minio', 'where': f'{self.bucket}/{self.prefix}', 'endpoint': self.endpoint}
        return {'backend': 'local', 'where': str(self.local_dir / self.prefix)}


store = ObjectStore()
