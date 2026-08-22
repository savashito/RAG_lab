"""
core/minio.py

Public API is fully async — safe to call from any route or db function.
The sync helpers are private (_prefixed) and only used internally via
run_in_executor so the event loop is never blocked.
"""

import asyncio
import io
import json

from minio import Minio
from minio.error import S3Error

from core.config import settings

# ── Client ────────────────────────────────────────────────────────────────────

_client: Minio | None = None


def _get_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
    return _client


def ensure_bucket() -> None:
    """Sync is fine here — only called once at startup before any requests."""
    client = _get_client()
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)


# ── Private sync internals ────────────────────────────────────────────────────

def _put_json(key: str, data: dict) -> str:
    raw = json.dumps(data, ensure_ascii=False, indent=2).encode()
    _get_client().put_object(
        settings.minio_bucket, key, io.BytesIO(raw), len(raw),
        content_type="application/json",
    )
    return key


def _put_text(key: str, text: str) -> str:
    raw = text.encode()
    _get_client().put_object(
        settings.minio_bucket, key, io.BytesIO(raw), len(raw),
        content_type="text/plain; charset=utf-8",
    )
    return key


def _get_json(key: str) -> dict:
    r = _get_client().get_object(settings.minio_bucket, key)
    return json.loads(r.read())


def _get_text(key: str) -> str:
    r = _get_client().get_object(settings.minio_bucket, key)
    return r.read().decode()


def _list_objects(prefix: str) -> list[dict]:
    try:
        objects = _get_client().list_objects(
            settings.minio_bucket, prefix=prefix, recursive=True
        )
        return [
            {
                "object_name": obj.object_name,
                "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
                "size": obj.size,
            }
            for obj in objects
        ]
    except S3Error:
        return []


# ── Public async API ──────────────────────────────────────────────────────────

async def put_json(key: str, data: dict) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _put_json, key, data)


async def put_text(key: str, text: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _put_text, key, text)


async def get_json(key: str) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_json, key)


async def get_text(key: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_text, key)


async def list_objects(prefix: str) -> list[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _list_objects, prefix)
