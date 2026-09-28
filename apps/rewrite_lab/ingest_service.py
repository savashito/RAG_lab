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

import json
import threading
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from ingestion.pipeline import ingest_md, ingest_pdf, ingest_url

# Archivos subidos que no son PDF pero ya vienen en Markdown: se ingieren tal cual.
MD_EXTS = {".md", ".markdown"}
# Registro persistente de DÓNDE se convirtió cada documento (VPS o OCR en la Mac mini),
# para que la lista del corpus lo siga mostrando después de reiniciar. Vive junto a los
# .md limpios; `read_clean` sólo sirve .md, así que no se expone por esa ruta.
CONVERSION_LOG = "_conversion.json"


def _kind_of(path: Path) -> str:
    """Clasifica un archivo subido por su extensión: `md` (Markdown ya listo) o `pdf`."""
    return "md" if path.suffix.lower() in MD_EXTS else "pdf"


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
    def start(self, file_paths: list[Path], topic: str | None = None,
              jurisdiction: str | None = None) -> str:
        """Job de ingesta de archivos subidos (rutas temporales que se borran al
        terminar). Admite PDFs y Markdown (`.md`/`.markdown`): el `.md` ya es Markdown,
        así que salta la conversión y sigue el mismo camino aguas abajo."""
        items = [{"kind": _kind_of(p), "ref": p, "name": p.name} for p in file_paths]
        return self._start(items, topic, jurisdiction)

    def start_urls(self, urls: list[str], topic: str | None = None,
                   jurisdiction: str | None = None) -> str:
        """Job de ingesta de URLs (HTML o PDF en línea). No hay archivos temporales."""
        items = [{"kind": "url", "ref": u, "name": u} for u in urls]
        return self._start(items, topic, jurisdiction)

    def _start(self, items: list[dict], topic: str | None,
               jurisdiction: str | None = None) -> str:
        """Crea un job y lanza el hilo que lo procesa. Uno a la vez: si ya hay uno
        corriendo, lo rechaza (embeber es pesado y `on_complete` toca estado global).
        `topic` etiqueta los chunks resultantes (segmentación por tema)."""
        with self._lock:
            if any(j["status"] == "running" for j in self.jobs.values()):
                raise RuntimeError("Ya hay una ingesta en curso. Espera a que termine.")
            job_id = uuid.uuid4().hex[:12]
            self.jobs[job_id] = {
                "id": job_id,
                "status": "running",
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "error": None,
                "topic": topic,
                "jurisdiction": jurisdiction,
                "files": [self._new_file_entry(it["name"]) for it in items],
            }
        threading.Thread(target=self._run, args=(job_id, items, topic, jurisdiction), daemon=True).start()
        return job_id

    @staticmethod
    def _new_file_entry(name: str) -> dict:
        return {"pdf_name": name, "source": None, "stage": "queued",
                "message": "En cola…", "done": False, "error": None,
                "inserted": False, "replaced": False, "n_chunks": 0,
                "clean_available": False, "report": {}, "conversion": {}}

    def _run(self, job_id: str, items: list[dict], topic: str | None = None,
             jurisdiction: str | None = None) -> None:
        job = self.jobs[job_id]
        try:
            for entry, item in zip(job["files"], items):
                def progress(stage: str, message: str, _e=entry) -> None:
                    _e["stage"], _e["message"] = stage, message

                if item["kind"] == "url":
                    result = ingest_url(
                        item["ref"], table=self.table, tei=self.tei, connect_fn=self.connect_fn,
                        clean_dir=self.clean_dir, progress=progress,
                    )
                elif item["kind"] == "md":
                    result = ingest_md(
                        item["ref"], table=self.table, tei=self.tei, connect_fn=self.connect_fn,
                        clean_dir=self.clean_dir, progress=progress,
                    )
                else:
                    result = ingest_pdf(
                        item["ref"], table=self.table, tei=self.tei, connect_fn=self.connect_fn,
                        clean_dir=self.clean_dir, progress=progress,
                    )
                # Etiqueta con el tópico y la jurisdicción los chunks recién insertados de
                # este documento. El pipeline compartido no los conoce; se setean aquí por
                # `source` (upsert por documento).
                if (result.inserted or result.replaced_existing) and not result.error:
                    sets, vals = [], []
                    if topic:
                        sets.append("topic = %s"); vals.append(topic)
                    if jurisdiction:
                        sets.append("jurisdiction = %s"); vals.append(jurisdiction)
                    if sets:
                        vals.append(result.source)
                        with self.connect_fn() as conn, conn.cursor() as cur:
                            cur.execute(f"UPDATE {self.table} SET {', '.join(sets)} WHERE source = %s", vals)
                            conn.commit()
                if result.inserted and result.conversion:
                    self._log_conversion(result.source, result.conversion)
                entry.update(
                    source=result.source, error=result.error, inserted=result.inserted,
                    replaced=result.replaced_existing, n_chunks=result.n_chunks,
                    topic=topic, clean_available=bool(result.clean_path), report=result.report,
                    conversion=result.conversion, done=True,
                )
            job["status"] = "error" if any(f["error"] for f in job["files"]) else "done"
            if any(f["inserted"] for f in job["files"]) and self.on_complete:
                self.on_complete()   # recarga el índice en memoria: chunks nuevos ya buscables
        except Exception as exc:   # noqa: BLE001 — cualquier fallo del hilo se refleja en el job
            job["status"] = "error"
            job["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            # Los archivos subidos (PDF o .md) son temporales (el .md limpio sí
            # persiste en clean_dir). Se borran y se retira el subdirectorio único de la
            # subida si queda vacío. Las URLs no dejan archivos que limpiar.
            parents: set[Path] = set()
            for it in items:
                if it["kind"] in ("pdf", "md"):
                    up = it["ref"]
                    up.unlink(missing_ok=True)
                    parents.add(up.parent)
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
        if (self.clean_dir.resolve() not in path.parents or not path.is_file()
                or path.suffix.lower() not in MD_EXTS):
            raise FileNotFoundError(f"No hay Markdown limpio para {source!r}")
        return path.read_text(encoding="utf-8")

    def topic_of(self, source: str) -> str | None:
        """Tópico con el que está etiquetado un documento (por `source`). Sirve para
        comprobar permisos antes de borrar. `None` si el documento no existe."""
        with self.connect_fn() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT max(topic) FROM {self.table} WHERE source = %s", (source,))
            row = cur.fetchone()
        return row[0] if row else None

    def delete(self, source: str) -> dict:
        """Borra TODO el registro de un documento: sus chunks en la tabla (para que no se
        recuperen más) y su Markdown limpio en disco si existe. Devuelve cuántas filas se
        eliminaron. El índice en memoria (`on_complete`) se recarga en segundo plano para
        que el BM25 deje de ver los chunks borrados."""
        with self.connect_fn() as conn, conn.cursor() as cur:
            cur.execute(f"DELETE FROM {self.table} WHERE source = %s", (source,))
            deleted = cur.rowcount
            conn.commit()
        clean = (self.clean_dir / Path(source).name)
        if clean.is_file():
            clean.unlink(missing_ok=True)
        self._log_conversion(source, None)
        if deleted and self.on_complete:
            # Recargar el índice en memoria tarda ~20 s con el corpus completo: se hace en
            # segundo plano para que la UI reciba la respuesta ya (los chunks ya no están
            # en la BD, así que la búsqueda densa deja de verlos al instante).
            threading.Thread(target=self.on_complete, daemon=True).start()
        return {"source": source, "deleted": deleted, "index_reloading": bool(deleted)}

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
                f"SELECT source, max(topic), count(*) FROM {self.table} "
                f"GROUP BY source ORDER BY source")
            rows = cur.fetchall()
        log = self._read_conversion_log()
        return [
            {"source": s, "topic": t, "chunks": n,
             "clean_available": (self.clean_dir / Path(s).name).is_file(),
             "conversion": log.get(s)}   # None = ingerido antes de registrar esto
            for s, t, n in rows
        ]

    # ── registro de conversión (VPS vs Mac mini) ─────────────────────────────────
    def _read_conversion_log(self) -> dict:
        try:
            return json.loads((self.clean_dir / CONVERSION_LOG).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _log_conversion(self, source: str, conversion: dict | None) -> None:
        """Guarda (o borra, con None) la conversión de un documento. Escritura atómica."""
        with self._lock:
            log = self._read_conversion_log()
            if conversion is None:
                if log.pop(source, None) is None:
                    return
            else:
                log[source] = {**conversion, "at": time.strftime("%Y-%m-%d %H:%M")}
            self.clean_dir.mkdir(parents=True, exist_ok=True)
            tmp = self.clean_dir / (CONVERSION_LOG + ".tmp")
            tmp.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self.clean_dir / CONVERSION_LOG)
