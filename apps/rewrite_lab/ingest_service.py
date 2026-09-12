"""
apps/rewrite_lab/ingest_service.py — orquesta la ingesta de PDFs para el tab web.

Responsabilidad única: gestionar *jobs* de ingesta en segundo plano (uno a la vez)
sobre el pipeline reutilizable `ingestion.pipeline`. No sabe nada de HTTP ni de la
UI; `main.py` le pasa sus dependencias (tabla, TEI, conexión, directorios) y expone
rutas delgadas encima.

Un job procesa N PDFs en un hilo aparte para no bloquear el event-loop de FastAPI, y
va publicando el progreso por archivo (convert → clean → analyze → chunk → embed →
insert) para que la UI lo consulte por polling. Al terminar, invoca `on_complete`
(p. ej. recargar el índice BM25 en memoria) para que los chunks nuevos queden
buscables sin reiniciar el servidor.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from ingestion.pipeline import ingest_pdf


class IngestManager:
    def __init__(self, *, table: str, tei, connect_fn: Callable, clean_dir: Path,
                 upload_dir: Path, on_complete: Callable[[], None] | None = None):
        self.table = table
        self.tei = tei
        self.connect_fn = connect_fn
        self.clean_dir = Path(clean_dir)
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.on_complete = on_complete
        self.jobs: dict[str, dict] = {}
        self._lock = threading.Lock()

    # ── ciclo de vida del job ────────────────────────────────────────────────────
    def start(self, pdf_paths: list[Path]) -> str:
        """Crea un job y lanza el hilo que lo procesa. Uno a la vez: si ya hay uno
        corriendo, lo rechaza (embeber es pesado y `on_complete` toca estado global)."""
        with self._lock:
            if any(j["status"] == "running" for j in self.jobs.values()):
                raise RuntimeError("Ya hay una ingesta en curso. Espera a que termine.")
            job_id = uuid.uuid4().hex[:12]
            self.jobs[job_id] = {
                "id": job_id,
                "status": "running",
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "error": None,
                "files": [self._new_file_entry(p) for p in pdf_paths],
            }
        threading.Thread(target=self._run, args=(job_id, pdf_paths), daemon=True).start()
        return job_id

    @staticmethod
    def _new_file_entry(pdf_path: Path) -> dict:
        return {"pdf_name": pdf_path.name, "source": None, "stage": "queued",
                "message": "En cola…", "done": False, "error": None,
                "inserted": False, "replaced": False, "n_chunks": 0,
                "clean_available": False, "report": {}}

    def _run(self, job_id: str, pdf_paths: list[Path]) -> None:
        job = self.jobs[job_id]
        try:
            for entry, pdf in zip(job["files"], pdf_paths):
                def progress(stage: str, message: str, _e=entry) -> None:
                    _e["stage"], _e["message"] = stage, message

                result = ingest_pdf(
                    pdf, table=self.table, tei=self.tei, connect_fn=self.connect_fn,
                    clean_dir=self.clean_dir, progress=progress,
                )
                entry.update(
                    source=result.source, error=result.error, inserted=result.inserted,
                    replaced=result.replaced_existing, n_chunks=result.n_chunks,
                    clean_available=bool(result.clean_path), report=result.report, done=True,
                )
            job["status"] = "error" if any(f["error"] for f in job["files"]) else "done"
            if any(f["inserted"] for f in job["files"]) and self.on_complete:
                self.on_complete()   # recarga el índice en memoria: chunks nuevos ya buscables
        except Exception as exc:   # noqa: BLE001 — cualquier fallo del hilo se refleja en el job
            job["status"] = "error"
            job["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            # Los PDFs subidos son temporales (el .md limpio sí persiste). Se borran y
            # se retira el subdirectorio único de la subida si queda vacío.
            parents: set[Path] = set()
            for pdf in pdf_paths:
                pdf.unlink(missing_ok=True)
                parents.add(pdf.parent)
            for d in parents:
                if d != self.upload_dir and d.exists() and not any(d.iterdir()):
                    d.rmdir()

    def status(self, job_id: str) -> dict | None:
        return self.jobs.get(job_id)

    # ── consultas de apoyo para la UI ────────────────────────────────────────────
    def read_clean(self, source: str) -> str:
        """Texto del Markdown limpio guardado, para visualizarlo. Blinda contra
        path-traversal: sólo se sirve un archivo directo dentro de `clean_dir`."""
        path = (self.clean_dir / Path(source).name).resolve()
        if self.clean_dir.resolve() not in path.parents or not path.is_file():
            raise FileNotFoundError(f"No hay Markdown limpio para {source!r}")
        return path.read_text(encoding="utf-8")

    def documents(self) -> list[dict]:
        """Documentos ya presentes en la tabla (source + nº de chunks + si hay .md
        limpio guardado para visualizar), para el estado del corpus en la UI. Tolera
        que la tabla aún no exista. Los documentos ingeridos ANTES de este pipeline no
        tienen .md limpio en disco: `clean_available` avisa a la UI para no ofrecer el
        botón que daría 404."""
        with self.connect_fn() as conn, conn.cursor() as cur:
            cur.execute("SELECT to_regclass(%s)", (self.table,))
            if cur.fetchone()[0] is None:
                return []
            cur.execute(
                f"SELECT source, count(*) FROM {self.table} GROUP BY source ORDER BY source")
            rows = cur.fetchall()
        return [
            {"source": s, "chunks": n,
             "clean_available": (self.clean_dir / Path(s).name).is_file()}
            for s, n in rows
        ]
