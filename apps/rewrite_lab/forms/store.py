"""Dónde viven los formularios.

  · BD, tabla `formularios`: el paquete editable (formulario.yaml + plantilla.md + ejemplos.yaml
    como texto), su estado (borrador → revisado → publicado), versión y quién lo editó. Separada
    de la tabla de chunks: un formulario NO es parte del corpus del RAG.
  · MinIO: el documento fuente del modelo (forms/<id>/fuente/…) y una copia congelada de cada
    versión publicada (forms/<id>/publicado-v<N>.json).
  · Repo (forms/<id>/): siembra. Al arrancar se insertan los formularios que aún no estén en la BD
    y se actualizan los que siguen en BORRADOR y NUNCA se han editado desde la app (updated_by =
    'repo'). Si alguien lo editó en /formularios, o ya está revisado o publicado, el repo no lo toca:
    un texto revisado no puede cambiar sin volver a revisión.
"""
from __future__ import annotations

import time
from pathlib import Path

from forms.validar import cargar, validar

SCHEMA = """
CREATE TABLE IF NOT EXISTS formularios (
    id text PRIMARY KEY, tema text NOT NULL, titulo text NOT NULL,
    estado text NOT NULL DEFAULT 'borrador' CHECK (estado IN ('borrador', 'revisado', 'publicado')),
    version int NOT NULL DEFAULT 1,
    spec_yaml text NOT NULL, plantilla text NOT NULL, ejemplos_yaml text NOT NULL DEFAULT '',
    fuente_key text, publicado_key text,
    updated_by text, updated_at timestamptz DEFAULT now(), revisado_por text, publicado_at timestamptz)
"""
COLS = ['id', 'tema', 'titulo', 'estado', 'version', 'spec_yaml', 'plantilla', 'ejemplos_yaml',
        'fuente_key', 'publicado_key', 'updated_by', 'updated_at', 'revisado_por', 'publicado_at']


class Conflicto(Exception):
    """Otra persona guardó el formulario mientras lo editabas."""


class FormStore:
    def __init__(self, connect, object_store, seed_dir: Path):
        self.connect, self.objects, self.seed_dir = connect, object_store, seed_dir
        with self.connect() as c, c.cursor() as cur:
            cur.execute(SCHEMA)
            c.commit()
        self.sembrar()

    def sembrar(self) -> list[str]:
        """Inserta los formularios del repo que no estén en la BD y actualiza los que siguen siendo
        del repo (nadie los ha editado en la app). Solo paquetes válidos."""
        nuevos = []
        for d in sorted(p for p in self.seed_dir.iterdir() if (p / 'formulario.yaml').is_file()):
            spec_yaml, plantilla = (d / 'formulario.yaml').read_text(), (d / 'plantilla.md').read_text()
            ejemplos = (d / 'ejemplos.yaml').read_text() if (d / 'ejemplos.yaml').is_file() else ''
            if validar(spec_yaml, plantilla, ejemplos):
                print(f'formularios: {d.name} no se sembró (tiene errores; corre tests/test_forms.py)')
                continue
            spec, _, _ = cargar(spec_yaml)
            with self.connect() as c, c.cursor() as cur:
                cur.execute("INSERT INTO formularios (id, tema, titulo, estado, spec_yaml, plantilla, ejemplos_yaml, "
                            "updated_by) VALUES (%s,%s,%s,%s,%s,%s,%s,'repo') ON CONFLICT (id) DO UPDATE SET "
                            "tema = EXCLUDED.tema, titulo = EXCLUDED.titulo, spec_yaml = EXCLUDED.spec_yaml, "
                            "plantilla = EXCLUDED.plantilla, ejemplos_yaml = EXCLUDED.ejemplos_yaml, "
                            "version = formularios.version + 1, updated_at = now() "
                            "WHERE formularios.updated_by = 'repo' AND formularios.estado = 'borrador' AND (formularios.spec_yaml, formularios.plantilla, "
                            "formularios.ejemplos_yaml) IS DISTINCT FROM (EXCLUDED.spec_yaml, EXCLUDED.plantilla, EXCLUDED.ejemplos_yaml)",
                            (spec['id'], spec['tema'], spec['titulo'], spec.get('estado', 'borrador'),
                             spec_yaml, plantilla, ejemplos))
                if cur.rowcount:
                    nuevos.append(spec['id'])
                c.commit()
        return nuevos

    # ── lectura ───────────────────────────────────────────────────────────────────
    def lista(self) -> list[dict]:
        with self.connect() as c, c.cursor() as cur:
            cur.execute("SELECT id, tema, titulo, estado, version, updated_by, updated_at::text, revisado_por, "
                        "publicado_at::text, fuente_key FROM formularios ORDER BY tema, titulo")
            cols = ['id', 'tema', 'titulo', 'estado', 'version', 'updated_by', 'updated_at', 'revisado_por',
                    'publicado_at', 'fuente_key']
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    def obtener(self, fid: str) -> dict | None:
        with self.connect() as c, c.cursor() as cur:
            cur.execute(f"SELECT {', '.join(COLS)} FROM formularios WHERE id = %s", (fid,))
            r = cur.fetchone()
        return dict(zip(COLS, [str(x) if x is not None and k.endswith('_at') else x for k, x in zip(COLS, r)])) if r else None

    def catalogo(self, ver_borradores) -> dict:
        """{id: spec} listos para el asistente. `ver_borradores(tema)` decide si esta persona ve los
        no publicados de ese tema (admins del tema, para probarlos)."""
        out = {}
        with self.connect() as c, c.cursor() as cur:
            cur.execute("SELECT id, tema, estado, spec_yaml, plantilla FROM formularios ORDER BY titulo")
            for fid, tema, estado, spec_yaml, plantilla in cur.fetchall():
                if estado != 'publicado' and not ver_borradores(tema):
                    continue
                spec, _, errs = cargar(spec_yaml)
                if spec is None or errs:
                    continue
                out[fid] = {**spec, 'estado': estado, '_plantilla': plantilla}
        return out

    # ── escritura ─────────────────────────────────────────────────────────────────
    def guardar(self, fid: str, spec_yaml: str, plantilla: str, ejemplos_yaml: str, version: int,
                email: str) -> dict:
        """Guarda una nueva versión. Valida antes y rechaza si otra persona guardó entretanto."""
        errs = validar(spec_yaml, plantilla, ejemplos_yaml)
        if errs:
            return {'errores': errs}
        spec, _, _ = cargar(spec_yaml)
        if spec['id'] != fid:
            return {'errores': [f'el «id» del formulario.yaml ({spec["id"]}) no coincide con este formulario ({fid}).']}
        with self.connect() as c, c.cursor() as cur:
            # Al editar, un formulario publicado o revisado vuelve a borrador: hay que revisarlo de nuevo.
            cur.execute("UPDATE formularios SET spec_yaml = %s, plantilla = %s, ejemplos_yaml = %s, tema = %s, "
                        "titulo = %s, version = version + 1, estado = 'borrador', updated_by = %s, updated_at = now() "
                        "WHERE id = %s AND version = %s RETURNING version",
                        (spec_yaml, plantilla, ejemplos_yaml, spec['tema'], spec['titulo'], email, fid, version))
            r = cur.fetchone()
            if not r:
                raise Conflicto('Otra persona guardó este formulario mientras lo editabas. Recarga para ver su versión.')
            c.commit()
        return {'version': r[0], 'estado': 'borrador'}

    def crear(self, spec_yaml: str, plantilla: str, ejemplos_yaml: str, email: str) -> dict:
        errs = validar(spec_yaml, plantilla, ejemplos_yaml)
        if errs:
            return {'errores': errs}
        spec, _, _ = cargar(spec_yaml)
        with self.connect() as c, c.cursor() as cur:
            cur.execute("INSERT INTO formularios (id, tema, titulo, spec_yaml, plantilla, ejemplos_yaml, updated_by) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING",
                        (spec['id'], spec['tema'], spec['titulo'], spec_yaml, plantilla, ejemplos_yaml, email))
            if not cur.rowcount:
                return {'errores': [f'ya existe un formulario con id «{spec["id"]}».']}
            c.commit()
        return {'id': spec['id'], 'version': 1}

    def cambiar_estado(self, fid: str, estado: str, email: str) -> dict:
        """borrador → revisado → publicado. Al publicar, guarda una copia congelada en MinIO."""
        f = self.obtener(fid)
        if not f:
            return {'errores': ['no existe']}
        key = None
        if estado == 'publicado':
            key = self.objects.put_json(f'forms/{fid}/publicado-v{f["version"]}.json', {
                'id': fid, 'version': f['version'], 'publicado_por': email, 'publicado_at': time.strftime('%Y-%m-%d %H:%M'),
                'spec_yaml': f['spec_yaml'], 'plantilla': f['plantilla'], 'ejemplos_yaml': f['ejemplos_yaml']})
        with self.connect() as c, c.cursor() as cur:
            cur.execute("UPDATE formularios SET estado = %s, "
                        "revisado_por = CASE WHEN %s IN ('revisado', 'publicado') THEN %s ELSE revisado_por END, "
                        "publicado_key = COALESCE(%s, publicado_key), "
                        "publicado_at = CASE WHEN %s = 'publicado' THEN now() ELSE publicado_at END WHERE id = %s",
                        (estado, estado, email, key, estado, fid))
            c.commit()
        return {'estado': estado, 'publicado_key': key}

    def subir_fuente(self, fid: str, nombre: str, data: bytes, content_type: str) -> str:
        key = f'forms/{fid}/fuente/{Path(nombre).name}'   # relativa: get_bytes le vuelve a poner el prefijo
        self.objects.put_bytes(key, data, content_type)
        with self.connect() as c, c.cursor() as cur:
            cur.execute("UPDATE formularios SET fuente_key = %s WHERE id = %s", (key, fid))
            c.commit()
        return key
