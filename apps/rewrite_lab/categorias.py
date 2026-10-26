"""
👤 Categorías de la persona (📥 Ingestar): de qué depende que una ley aplique, además del lugar de los hechos.

Ejemplo: la Ley General de Acceso de las Mujeres a una Vida Libre de Violencia aplica si la persona es mujer; algunas
reglas, si es menor de edad. Los editores crean categorías (p. ej. «Sexo de la persona») con sus valores («mujer»,
«hombre») y marcan cada documento con los valores a los que aplica. Un documento sin marca aplica a todas las personas.
El valor «no lo dijo» está implícito en cada categoría: es lo que usará el filtro cuando la persona no lo diga.

Fase 1 (25-oct): solo etiquetas. La búsqueda NO las usa todavía; el filtro por persona (fase 2) las leerá.

Tablas: categorias_persona, documento_categorias (documento completo × valor) y categorias_persona_log (quién cambió
qué y cuándo).
"""
from __future__ import annotations

import json
from typing import Callable

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

SCHEMA = """
CREATE TABLE IF NOT EXISTS categorias_persona (
    id serial PRIMARY KEY, nombre text NOT NULL UNIQUE, descripcion text, valores jsonb NOT NULL,
    creado_por text, created_at timestamptz DEFAULT now(), actualizado_por text, updated_at timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS documento_categorias (
    source text NOT NULL, categoria_id int NOT NULL REFERENCES categorias_persona(id) ON DELETE CASCADE,
    valor text NOT NULL, por text, at timestamptz DEFAULT now(), PRIMARY KEY (source, categoria_id, valor));
CREATE TABLE IF NOT EXISTS categorias_persona_log (
    id serial PRIMARY KEY, accion text NOT NULL, detalle jsonb, por text, at timestamptz DEFAULT now());
"""
NO_LO_DIJO = 'no lo dijo'


def normalizar_categoria(b: dict) -> dict:
    """Valida lo que manda la página. Devuelve {nombre, descripcion, valores} o lanza ValueError con el motivo.
    «no lo dijo» no se guarda como valor: está implícito en todas las categorías."""
    nombre = ' '.join(str(b.get('nombre') or '').split())
    if not 1 <= len(nombre) <= 80:
        raise ValueError('El nombre de la categoría debe tener entre 1 y 80 caracteres.')
    descripcion = str(b.get('descripcion') or '').strip()[:1000]
    crudos = b.get('valores')
    if isinstance(crudos, str):
        crudos = crudos.split(',')
    valores, vistos = [], set()
    for v in crudos or []:
        v = ' '.join(str(v).split())
        if not v or v.lower() == NO_LO_DIJO or v.lower() in vistos:
            continue
        if len(v) > 60:
            raise ValueError(f'El valor «{v[:30]}…» es muy largo (máximo 60 caracteres).')
        vistos.add(v.lower())
        valores.append(v)
    if not valores:
        raise ValueError('Agrega al menos un valor (por ejemplo «mujer», «hombre»). «No lo dijo» ya está incluido.')
    if len(valores) > 20:
        raise ValueError('Máximo 20 valores por categoría.')
    return {'nombre': nombre, 'descripcion': descripcion, 'valores': valores}


def normalizar_etiquetas(etiquetas, categorias: dict[int, dict]) -> list[tuple[int, str]]:
    """[{categoria_id, valor}] → [(categoria_id, valor)] sin repetidos; solo valores que existen en su categoría."""
    out = []
    for e in etiquetas or []:
        try:
            cid = int(e.get('categoria_id'))
        except (TypeError, ValueError):
            raise ValueError('Etiqueta sin categoría.') from None
        cat = categorias.get(cid)
        if not cat:
            raise ValueError(f'No existe la categoría {cid}.')
        valor = str(e.get('valor') or '')
        if valor not in cat['valores']:
            raise ValueError(f'«{valor}» no es un valor de «{cat["nombre"]}».')
        if (cid, valor) not in out:
            out.append((cid, valor))
    return out


class Categorias:
    def __init__(self, *, connect: Callable, current_email: Callable, can_edit: Callable, can_tag: Callable):
        """can_edit(email): crear/editar/borrar categorías. can_tag(email, source): marcar ese documento."""
        self.connect, self.current_email, self.can_edit, self.can_tag = connect, current_email, can_edit, can_tag
        with connect() as c, c.cursor() as cur:
            cur.execute(SCHEMA)
            c.commit()
        self.router = self._make_router()

    # ── datos ─────────────────────────────────────────────────────────────────────
    def _log(self, cur, accion: str, detalle: dict, email: str | None):
        cur.execute("INSERT INTO categorias_persona_log (accion, detalle, por) VALUES (%s, %s::jsonb, %s)",
                    (accion, json.dumps(detalle, ensure_ascii=False), email))

    def listar(self) -> list[dict]:
        with self.connect() as c, c.cursor() as cur:
            cur.execute("SELECT k.id, k.nombre, k.descripcion, k.valores, k.actualizado_por, k.updated_at::text, "
                        "(SELECT count(DISTINCT d.source) FROM documento_categorias d WHERE d.categoria_id = k.id) "
                        "FROM categorias_persona k ORDER BY k.nombre")
            return [{'id': i, 'nombre': n, 'descripcion': d, 'valores': v, 'actualizado_por': por, 'updated_at': at,
                     'documentos': nd} for i, n, d, v, por, at, nd in cur.fetchall()]

    def _por_id(self, cur) -> dict[int, dict]:
        cur.execute("SELECT id, nombre, valores FROM categorias_persona")
        return {i: {'nombre': n, 'valores': v} for i, n, v in cur.fetchall()}

    def guardar(self, cid: int | None, b: dict, email: str) -> dict:
        """Crea (cid None) o edita una categoría. Al quitar un valor, se borran las marcas de documentos con ese valor."""
        cat = normalizar_categoria(b)
        with self.connect() as c, c.cursor() as cur:
            cur.execute("SELECT id FROM categorias_persona WHERE lower(nombre) = lower(%s) AND id IS DISTINCT FROM %s",
                        (cat['nombre'], cid))
            if cur.fetchone():
                raise ValueError(f'Ya existe una categoría «{cat["nombre"]}».')
            quitadas = 0
            if cid is None:
                cur.execute("INSERT INTO categorias_persona (nombre, descripcion, valores, creado_por, actualizado_por) "
                            "VALUES (%s, %s, %s::jsonb, %s, %s) RETURNING id",
                            (cat['nombre'], cat['descripcion'], json.dumps(cat['valores'], ensure_ascii=False), email, email))
                cid = cur.fetchone()[0]
                self._log(cur, 'crear', {'id': cid, **cat}, email)
            else:
                cur.execute("UPDATE categorias_persona SET nombre=%s, descripcion=%s, valores=%s::jsonb, actualizado_por=%s, "
                            "updated_at=now() WHERE id=%s RETURNING id",
                            (cat['nombre'], cat['descripcion'], json.dumps(cat['valores'], ensure_ascii=False), email, cid))
                if not cur.fetchone():
                    raise ValueError('Esa categoría ya no existe.')
                cur.execute("DELETE FROM documento_categorias WHERE categoria_id = %s AND NOT (valor = ANY(%s))",
                            (cid, cat['valores']))
                quitadas = cur.rowcount
                self._log(cur, 'editar', {'id': cid, **cat, 'marcas_quitadas': quitadas}, email)
            c.commit()
        return {'id': cid, 'marcas_quitadas': quitadas}

    def borrar(self, cid: int, email: str) -> dict:
        with self.connect() as c, c.cursor() as cur:
            cur.execute("DELETE FROM categorias_persona WHERE id = %s RETURNING nombre", (cid,))
            fila = cur.fetchone()
            if not fila:
                raise ValueError('Esa categoría ya no existe.')
            self._log(cur, 'borrar', {'id': cid, 'nombre': fila[0]}, email)   # sus marcas se borran en cascada
            c.commit()
        return {'id': cid}

    def etiquetas(self) -> dict[str, list[dict]]:
        """source → [{categoria_id, categoria, valor}] (solo documentos marcados)."""
        with self.connect() as c, c.cursor() as cur:
            cur.execute("SELECT d.source, d.categoria_id, k.nombre, d.valor FROM documento_categorias d "
                        "JOIN categorias_persona k ON k.id = d.categoria_id ORDER BY d.source, k.nombre, d.valor")
            out: dict[str, list[dict]] = {}
            for s, cid, n, v in cur.fetchall():
                out.setdefault(s, []).append({'categoria_id': cid, 'categoria': n, 'valor': v})
            return out

    def marcar(self, source: str, etiquetas, email: str) -> list[dict]:
        """Reemplaza las marcas de un documento completo. Lista vacía = aplica a todas las personas."""
        with self.connect() as c, c.cursor() as cur:
            pares = normalizar_etiquetas(etiquetas, self._por_id(cur))
            cur.execute("DELETE FROM documento_categorias WHERE source = %s", (source,))
            for cid, v in pares:
                cur.execute("INSERT INTO documento_categorias (source, categoria_id, valor, por) VALUES (%s, %s, %s, %s)",
                            (source, cid, v, email))
            self._log(cur, 'marcar', {'source': source, 'etiquetas': [{'categoria_id': a, 'valor': b} for a, b in pares]}, email)
            c.commit()
        return self.etiquetas().get(source, [])

    # ── rutas ─────────────────────────────────────────────────────────────────────
    def _make_router(self) -> APIRouter:
        r = APIRouter(prefix='/api/categorias')

        def deny(msg='No tienes permiso para editar categorías.'):
            return JSONResponse({'error': msg}, status_code=403)

        def bad(msg):
            return JSONResponse({'error': msg}, status_code=400)

        @r.get('')
        def listar(request: Request):
            email = self.current_email(request)
            return {'categorias': self.listar(), 'puede_editar': bool(self.can_edit(email))}

        @r.post('')
        async def crear(request: Request):
            email = self.current_email(request)
            if not self.can_edit(email):
                return deny()
            try:
                return self.guardar(None, await request.json(), email)
            except ValueError as e:
                return bad(str(e))

        @r.put('/{cid:int}')
        async def editar(cid: int, request: Request):
            email = self.current_email(request)
            if not self.can_edit(email):
                return deny()
            try:
                return self.guardar(cid, await request.json(), email)
            except ValueError as e:
                return bad(str(e))

        @r.delete('/{cid:int}')
        def borrar(cid: int, request: Request):
            email = self.current_email(request)
            if not self.can_edit(email):
                return deny()
            try:
                return self.borrar(cid, email)
            except ValueError as e:
                return bad(str(e))

        @r.get('/documentos')
        def etiquetas(request: Request):
            return self.etiquetas()

        @r.put('/documentos')
        async def marcar(request: Request):
            email = self.current_email(request)
            b = await request.json()
            source = str(b.get('source') or '')
            if not self.can_tag(email, source):
                return deny('No tienes permiso sobre ese documento.')
            try:
                return {'source': source, 'etiquetas': self.marcar(source, b.get('etiquetas'), email)}
            except ValueError as e:
                return bad(str(e))

        return r
