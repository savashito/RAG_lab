"""
📚 Catálogo de casos (ronda 3): datos del expediente, tipos de caso, reglas (datos → delito → artículos) y lo que va
a «otro». Diseño: 06_evaluation/estudio_ronda3_2026-11-10/diseno_maquina_estados.md.

Mientras Karen lo revisa, la versión de trabajo vive en la base (tabla consulta_catalogo, un solo documento jsonb) y
se edita desde /catalogo. Al arrancar, si la tabla está vacía, se carga `catalogo_casos.yaml`. «Descargar YAML»
exporta la versión de trabajo; esa exportación es la que va a git y la que congela un estudio (con su md5).

Cada entrada tiene `estado`: borrador/sugerida (sin revisar), confirmada (revisada por una abogada), descartada.
Todo cambio queda en consulta_catalogo_log (quién, qué, cuándo).
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Callable

import yaml
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, Response

HERE = Path(__file__).resolve().parent
YAML_INICIAL = HERE / 'catalogo_casos.yaml'

SCHEMA = """
CREATE TABLE IF NOT EXISTS consulta_catalogo (
    id int PRIMARY KEY DEFAULT 1 CHECK (id = 1), doc jsonb NOT NULL, actualizado_por text, updated_at timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS consulta_catalogo_log (
    id serial PRIMARY KEY, accion text NOT NULL, detalle jsonb, por text, at timestamptz DEFAULT now());
"""

# Código → documento del corpus.
CODIGOS = {
    'cdmx': 'Código Penal de la Ciudad de México.md',
    'queretaro': 'Código Penal del Estado de Querétaro.md',
    'edomex': 'Código Penal del Estado de México.md',
    'morelos': 'Código PENALEM.md',
    'federal': 'Código Penal Federal.md',
}
PARTES = {'datos': 'id', 'tipos_caso': 'id', 'reglas': 'id'}
ESTADOS = {'borrador', 'sugerida', 'confirmada', 'descartada'}


class ConflictoError(Exception):
    pass


def _norm(s: str) -> str:
    s = unicodedata.normalize('NFD', str(s).upper())
    return ' '.join(''.join(c for c in s if unicodedata.category(c) != 'Mn').replace('.', ' ').split())


def md5_de(doc: dict) -> str:
    return hashlib.md5(json.dumps(doc, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def a_yaml(doc: dict) -> str:
    return yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=120)


def validar_entrada(parte: str, e: dict, doc: dict) -> dict:
    """Limpia una entrada que manda la página. Lanza ValueError con el motivo."""
    if parte not in PARTES:
        raise ValueError(f'Parte desconocida: {parte}')
    if not isinstance(e, dict):
        raise ValueError('Entrada inválida.')
    e = {k: v for k, v in e.items() if v is not None}
    if not re.fullmatch(r'[a-z0-9_]{1,40}', str(e.get('id') or '')):
        raise ValueError('El id debe tener solo minúsculas, números y _ (máximo 40).')
    if e.get('estado', 'borrador') not in ESTADOS:
        raise ValueError(f'Estado inválido: {e.get("estado")}')
    ids_datos = {d['id'] for d in doc.get('datos', [])}
    ids_tipos = {t['id'] for t in doc.get('tipos_caso', [])}
    if parte == 'tipos_caso':
        faltan = [d for d in e.get('datos', []) if d not in ids_datos]
        if faltan:
            raise ValueError(f'Datos del expediente que no existen: {", ".join(faltan)}')
    if parte == 'reglas':
        if e.get('tipo_caso') not in ids_tipos:
            raise ValueError(f'Tipo de caso que no existe: {e.get("tipo_caso")}')
        arts = e.get('articulos') or {}
        e['articulos'] = {k: [str(a).strip() for a in (arts.get(k) or []) if str(a).strip()] for k in CODIGOS}
    return e


class Catalogo:
    def __init__(self, *, connect: Callable, current_email: Callable, can_edit: Callable, is_superadmin: Callable,
                 table: str, static_dir: Path):
        self.connect, self.current_email, self.can_edit, self.is_superadmin = connect, current_email, can_edit, is_superadmin
        self.table, self.static_dir = table, static_dir
        with connect() as c, c.cursor() as cur:
            cur.execute(SCHEMA)
            cur.execute("SELECT 1 FROM consulta_catalogo WHERE id = 1")
            if not cur.fetchone() and YAML_INICIAL.exists():
                doc = yaml.safe_load(YAML_INICIAL.read_text())
                cur.execute("INSERT INTO consulta_catalogo (id, doc, actualizado_por) VALUES (1, %s::jsonb, 'yaml inicial')",
                            (json.dumps(doc, ensure_ascii=False),))
                self._log(cur, 'cargar_yaml', {'archivo': YAML_INICIAL.name, 'md5': md5_de(doc)}, None)
            c.commit()
        self.router = self._make_router()

    # ── datos ─────────────────────────────────────────────────────────────────────
    def _log(self, cur, accion: str, detalle: dict, email: str | None):
        cur.execute("INSERT INTO consulta_catalogo_log (accion, detalle, por) VALUES (%s, %s::jsonb, %s)",
                    (accion, json.dumps(detalle, ensure_ascii=False), email))

    def leer(self) -> tuple[dict, str | None, str | None]:
        with self.connect() as c, c.cursor() as cur:
            cur.execute("SELECT doc, actualizado_por, updated_at::text FROM consulta_catalogo WHERE id = 1")
            fila = cur.fetchone()
        return (fila[0], fila[1], fila[2]) if fila else ({}, None, None)

    def guardar_entrada(self, parte: str, e: dict, email: str, original_id: str | None = None) -> dict:
        """Crea o reemplaza una entrada (por id). `original_id` permite cambiar el id."""
        with self.connect() as c, c.cursor() as cur:
            cur.execute("SELECT doc FROM consulta_catalogo WHERE id = 1 FOR UPDATE")
            doc = cur.fetchone()[0]
            e = validar_entrada(parte, e, doc)
            lista = doc.setdefault(parte, [])
            buscar = original_id or e['id']
            idx = next((i for i, x in enumerate(lista) if x.get('id') == buscar), None)
            if e['id'] != buscar and any(x.get('id') == e['id'] for x in lista):
                raise ValueError(f'Ya existe «{e["id"]}».')
            antes = lista[idx] if idx is not None else None
            if idx is None:
                lista.append(e)
            else:
                lista[idx] = e
            if parte == 'tipos_caso' and antes and antes['id'] != e['id']:   # renombrar en las reglas
                for r in doc.get('reglas', []):
                    if r.get('tipo_caso') == antes['id']:
                        r['tipo_caso'] = e['id']
            cur.execute("UPDATE consulta_catalogo SET doc = %s::jsonb, actualizado_por = %s, updated_at = now() WHERE id = 1",
                        (json.dumps(doc, ensure_ascii=False), email))
            self._log(cur, 'guardar', {'parte': parte, 'antes': antes, 'despues': e}, email)
            c.commit()
        return e

    def reemplazar(self, doc: dict, email: str, base_md5: str | None = None) -> str:
        """Reemplaza el catálogo completo (editor YAML). Valida ids y referencias. Si `base_md5` no es el de la versión
        actual, alguien más guardó mientras tanto: se rechaza para no pisar sus cambios."""
        if not isinstance(doc, dict):
            raise ValueError('El YAML debe ser un documento con datos, tipos_caso y reglas.')
        for parte in PARTES:
            if not isinstance(doc.get(parte), list):
                raise ValueError(f'Falta la lista «{parte}».')
            ids = [e.get('id') if isinstance(e, dict) else None for e in doc[parte]]
            repetidos = sorted({i for i in ids if ids.count(i) > 1}, key=str)
            if repetidos:
                raise ValueError(f'ids repetidos en {parte}: {", ".join(map(str, repetidos))}')
            doc[parte] = [validar_entrada(parte, e, doc) for e in doc[parte]]
        with self.connect() as c, c.cursor() as cur:
            cur.execute("SELECT doc FROM consulta_catalogo WHERE id = 1 FOR UPDATE")
            if base_md5 and md5_de(cur.fetchone()[0]) != base_md5:
                raise ConflictoError('Alguien más guardó el catálogo mientras editabas. Recarga la página; tus cambios '
                                     'no se guardaron (cópialos antes de recargar).')
            cur.execute("UPDATE consulta_catalogo SET doc = %s::jsonb, actualizado_por = %s, updated_at = now() WHERE id = 1",
                        (json.dumps(doc, ensure_ascii=False), email))
            self._log(cur, 'importar', {'md5': md5_de(doc)}, email)
            c.commit()
        return md5_de(doc)

    def articulo(self, codigo: str, num: str) -> dict:
        """Texto de un artículo del corpus (juntando sus fragmentos)."""
        source = CODIGOS.get(codigo)
        if not source:
            raise ValueError('Código desconocido.')
        objetivo = _norm('Artículo ' + num)
        primero = re.split(r'\s+', num.strip())[0]
        with self.connect() as c, c.cursor() as cur:
            cur.execute(f"SELECT hierarchy, text FROM {self.table} WHERE source = %s AND hierarchy ILIKE %s "
                        f"ORDER BY position, part", (source, f'%Artículo {primero}%'))
            filas = [(h, t) for h, t in cur.fetchall() if _norm(h.split(' > ')[-1]) == objetivo]
        if not filas:
            return {'encontrado': False, 'codigo': codigo, 'num': num}
        partes = []
        for h, t in filas:
            k = t.find(h)
            partes.append(t[k + len(h):].strip() if k >= 0 else t)
        return {'encontrado': True, 'codigo': codigo, 'num': num, 'ruta': filas[0][0], 'texto': '\n\n'.join(partes)}

    # ── rutas ─────────────────────────────────────────────────────────────────────
    def _make_router(self) -> APIRouter:
        r = APIRouter()

        def bad(msg, code=400):
            return JSONResponse({'error': msg}, status_code=code)

        @r.get('/catalogo')
        def pagina():
            return FileResponse(self.static_dir / 'catalogo.html', headers={'Cache-Control': 'no-store'})

        @r.get('/api/catalogo')
        def obtener(request: Request):
            doc, por, at = self.leer()
            email = self.current_email(request)
            return {'catalogo': doc, 'yaml': a_yaml(doc), 'md5': md5_de(doc), 'actualizado_por': por, 'updated_at': at,
                    'puede_editar': bool(self.can_edit(email)), 'codigos': list(CODIGOS)}

        @r.put('/api/catalogo/{parte}')
        async def guardar(parte: str, request: Request):
            email = self.current_email(request)
            if not self.can_edit(email):
                return bad('No tienes permiso para editar el catálogo.', 403)
            b = await request.json()
            try:
                return {'entrada': self.guardar_entrada(parte, b.get('entrada'), email, b.get('original_id'))}
            except ValueError as e:
                return bad(str(e))

        @r.get('/api/catalogo/articulo')
        def articulo(codigo: str, num: str):
            try:
                return self.articulo(codigo, num)
            except ValueError as e:
                return bad(str(e))

        @r.get('/api/catalogo/yaml')
        def descargar():
            doc, _, _ = self.leer()
            return Response(a_yaml(doc), media_type='text/yaml; charset=utf-8',
                            headers={'Content-Disposition': f'attachment; filename="catalogo_casos_{md5_de(doc)[:8]}.yaml"'})

        @r.put('/api/catalogo')
        async def guardar_yaml(request: Request):
            email = self.current_email(request)
            if not self.can_edit(email):
                return bad('No tienes permiso para editar el catálogo.', 403)
            try:
                doc = yaml.safe_load(await request.body())
            except yaml.YAMLError as e:
                m = getattr(e, 'problem_mark', None)
                return JSONResponse({'error': f'YAML inválido: {getattr(e, "problem", e)}',
                                     'linea': m.line if m else None}, status_code=400)
            try:
                return {'md5': self.reemplazar(doc, email, request.headers.get('X-Base-MD5'))}
            except ConflictoError as e:
                return bad(str(e), 409)
            except ValueError as e:
                return bad(str(e))

        return r
