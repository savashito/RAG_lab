"""
ingestion/ocr_client.py — cliente del servicio OCR de la Mac mini (Docling + macOS Vision).

El VPS no hace OCR (comparte CPU con otra app en producción). Los PDFs escaneados se
mandan al servicio de la Mac, que el VPS ve en `127.0.0.1:8095` gracias a un túnel
inverso que abre la propia Mac. Contrato del servicio:

    GET  /health → {"ok": true, "engine": "docling+vision", "busy": bool}
    POST /ocr    → multipart `file` + `Authorization: Bearer <token>`
                   → {"markdown", "pages", "seconds", "engine"}
                   401 token · 413 muy grande · 429 ocupado (+Retry-After)

Config por entorno: OCR_URL (default http://127.0.0.1:8095), OCR_TOKEN_FILE
(default ~/.ocr_token, permisos 600), OCR_MAX_WAIT (s que se espera si está ocupado).
Si la Mac no responde NO hay plan B local: se falla con un mensaje claro.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable

DEFAULT_URL = "http://127.0.0.1:8095"
DEFAULT_TOKEN_FILE = "~/.ocr_token"
SECONDS_PER_PAGE_BUDGET = 10     # tope holgado de lectura (medido: ~1–2.5 s/pág)
MIN_READ_TIMEOUT = 300


class OCRUnavailable(RuntimeError):
    """El servicio OCR no se pudo usar (caído, túnel abajo, token, límites…)."""


def _config() -> tuple[str, Path, float]:
    url = os.environ.get("OCR_URL", DEFAULT_URL).rstrip("/")
    token_file = Path(os.environ.get("OCR_TOKEN_FILE", DEFAULT_TOKEN_FILE)).expanduser()
    max_wait = float(os.environ.get("OCR_MAX_WAIT", 1800))
    return url, token_file, max_wait


def _read_token(token_file: Path) -> str:
    try:
        token = token_file.read_text().strip()
    except OSError as exc:
        raise OCRUnavailable(f"No se pudo leer el token del OCR ({token_file}): {exc.strerror}.") from exc
    if not token:
        raise OCRUnavailable(f"El archivo de token del OCR está vacío ({token_file}).")
    return token


def health(timeout: float = 5.0) -> dict:
    """Estado del servicio. Lanza OCRUnavailable si no contesta (Mac apagada, túnel caído)."""
    import httpx

    url, _, _ = _config()
    try:
        r = httpx.get(f"{url}/health", timeout=timeout)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as exc:
        raise OCRUnavailable(
            "El servicio OCR de la Mac mini no responde (¿Mac apagada o túnel caído?). "
            "Reintenta más tarde."
        ) from exc


def ocr_pdf(pdf: bytes, *, filename: str, pages: int,
            progress: Callable[[str], None] = lambda _m: None) -> dict:
    """Manda un PDF a la Mac y devuelve {"markdown", "pages", "seconds", "engine"}.

    Si la Mac está ocupada con otro PDF (429) espera `Retry-After` y reintenta, hasta
    OCR_MAX_WAIT segundos en total. `progress` recibe mensajes legibles para la UI."""
    import httpx

    url, token_file, max_wait = _config()
    token = _read_token(token_file)
    health()   # falla rápido y claro si la Mac no está, antes de subir megas

    read_timeout = max(MIN_READ_TIMEOUT, pages * SECONDS_PER_PAGE_BUDGET)
    timeout = httpx.Timeout(30.0, read=read_timeout)
    deadline = time.monotonic() + max_wait
    while True:
        try:
            r = httpx.post(f"{url}/ocr", headers={"Authorization": f"Bearer {token}"},
                           files={"file": (filename, pdf, "application/pdf")}, timeout=timeout)
        except httpx.TimeoutException as exc:
            raise OCRUnavailable(f"El OCR tardó más de {read_timeout // 60} min y se canceló la espera.") from exc
        except httpx.HTTPError as exc:
            raise OCRUnavailable(f"Se perdió la conexión con la Mac mini durante el OCR: {exc}") from exc

        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", 60))
            if time.monotonic() + wait > deadline:
                raise OCRUnavailable("La Mac mini sigue ocupada con otro PDF. Reintenta más tarde.")
            progress(f"La Mac mini está ocupada con otro PDF; reintento en {wait} s…")
            time.sleep(wait)
            continue
        if r.status_code == 200:
            return r.json()

        detail = _detail(r)
        if r.status_code == 401:
            raise OCRUnavailable("El servicio OCR rechazó el token (¿cambió .token en la Mac?).")
        if r.status_code == 413:
            raise OCRUnavailable(f"PDF demasiado grande para el OCR: {detail}")
        raise OCRUnavailable(f"El OCR falló (HTTP {r.status_code}): {detail}")


def _detail(r) -> str:
    try:
        return r.json().get("detail") or r.text[:200]
    except ValueError:
        return r.text[:200]
