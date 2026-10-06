"""Rutas HTTP del asistente de trámites (/tramites) y de la administración de formularios (/formularios).

Privacidad: /api/tramites/turno no guarda nada ni lo escribe en logs; el borrador (estado y
respuestas de la persona) vive en su navegador y viaja en cada petición.
"""
from __future__ import annotations

import re
import unicodedata

import time

from fastapi import APIRouter, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, Response

from forms import asistente
from forms.ia import Medidor
from forms.store import Conflicto
from forms.validar import ESTADOS, cargar, validar
from forms.plantilla import fill


def _fold(s: str) -> str:
    s = unicodedata.normalize('NFD', s or '').encode('ascii', 'ignore').decode().lower()
    return ' ' + re.sub(r'[^a-z0-9]+', ' ', s).strip() + ' '


def make_router(*, forms, ia, static_dir, current_email, can_ingest, can_upload_topic) -> APIRouter:
    r = APIRouter()

    def es_admin(email, tema) -> bool:
        return bool(can_ingest(email) and can_upload_topic(email, tema))

    def catalogo_para(request) -> dict:
        email = current_email(request)
        return forms.catalogo(lambda tema: es_admin(email, tema))

    def err(msg, status=400):
        return JSONResponse({'error': msg}, status_code=status)

    # ── Páginas ─────────────────────────────────────────────────────────────────
    @r.get('/tramites')
    def page_tramites():
        return FileResponse(static_dir / 'tramites.html', headers={'Cache-Control': 'no-store'})

    @r.get('/formularios')
    def page_formularios():
        return FileResponse(static_dir / 'formularios.html', headers={'Cache-Control': 'no-store'})

    # ── Asistente (público) ─────────────────────────────────────────────────────
    @r.post('/api/tramites/turno')
    async def tramite_turno(request: Request):
        b = await request.json()
        catalogo = catalogo_para(request)
        medidor, t0 = Medidor(ia), time.time()
        try:
            # En un hilo: las llamadas a Gemma bloquean; así un turno lento (p. ej. una duda que va
            # al RAG) no hace esperar a las demás personas que usan la app.
            borrador, vista = await run_in_threadpool(
                asistente.turno, b.get('borrador'), catalogo, medidor,
                mensaje=str(b.get('mensaje') or '')[:4000], evento=str(b.get('evento') or ''),
                campo=str(b.get('campo') or ''))
        except ValueError as e:
            return err(str(e))
        total = round(time.time() - t0, 2)
        llm = sum(x['llm'] for x in medidor.llamadas)
        vista['debug']['tiempo'] = {'total_s': total, 'llamadas_llm': llm, 'detalle': medidor.llamadas}
        # Registro sin datos personales: estado, duración y llamadas.
        print(f"tramites: turno {vista['estado']} {total}s · {llm} llamada(s) LLM "
              f"[{', '.join(f'{x['tarea']} {x['segundos']}s' for x in medidor.llamadas)}]", flush=True)
        return {'borrador': borrador, 'vista': vista}

    @r.post('/api/tramites/sugerir')
    async def tramite_sugerir(request: Request):
        """¿Lo que escribió la persona en el chat RAG sugiere un trámite? Por palabras clave
        (`disparadores` del formulario), sin LLM, para no hacer más lento el chat."""
        texto = _fold(str((await request.json()).get('texto') or '')[:4000])
        out = []
        for fid, spec in catalogo_para(request).items():
            hits = [d for d in spec.get('disparadores') or [] if _fold(d) in texto]
            if hits:
                out.append({'id': fid, 'titulo': spec['titulo'], 'por': hits[:3],
                            'borrador': spec.get('estado') != 'publicado'})
        return {'sugerencias': out}

    # ── Administración ──────────────────────────────────────────────────────────
    @r.get('/api/formularios')
    def form_lista(request: Request):
        email = current_email(request)
        return [dict(f, puede_editar=es_admin(email, f['tema'])) for f in forms.lista()
                if f['estado'] == 'publicado' or es_admin(email, f['tema'])]

    @r.get('/api/formularios/{fid}')
    def form_get(fid: str, request: Request):
        f = forms.obtener(fid)
        if not f:
            return err('no existe', 404)
        if not es_admin(current_email(request), f['tema']):
            return err('Sin permiso sobre el tema de este formulario.', 403)
        return f

    @r.post('/api/formularios/vista_previa')
    async def form_preview(request: Request):
        """Valida y llena la plantilla con un ejemplo, sin guardar (para el editor)."""
        b = await request.json()
        errs = validar(b.get('spec_yaml', ''), b.get('plantilla', ''), b.get('ejemplos_yaml', ''))
        _, ejemplos, _ = cargar(b.get('spec_yaml', ''), b.get('ejemplos_yaml', ''))
        nombre = b.get('ejemplo') or next(iter(ejemplos), None)
        doc, faltan = '', []
        try:
            doc, faltan = fill(b.get('plantilla', ''), ejemplos.get(nombre) or {})
        except ValueError:
            pass
        return {'errores': errs, 'ejemplos': list(ejemplos), 'ejemplo': nombre, 'documento': doc, 'faltan': faltan}

    @r.put('/api/formularios/{fid}')
    async def form_save(fid: str, request: Request):
        b, email = await request.json(), current_email(request)
        f = forms.obtener(fid)
        if f is None:
            spec, _, _ = cargar(b.get('spec_yaml', ''))
            if not spec or not es_admin(email, spec.get('tema')):
                return err('Sin permiso para crear formularios en ese tema.', 403)
            out = forms.crear(b.get('spec_yaml', ''), b.get('plantilla', ''), b.get('ejemplos_yaml', ''), email)
        else:
            nuevo, _, _ = cargar(b.get('spec_yaml', ''))
            if not es_admin(email, f['tema']) or (nuevo and not es_admin(email, nuevo.get('tema'))):
                return err('Sin permiso sobre el tema de este formulario.', 403)
            try:
                out = forms.guardar(fid, b.get('spec_yaml', ''), b.get('plantilla', ''), b.get('ejemplos_yaml', ''),
                                    int(b.get('version') or 0), email)
            except Conflicto as e:
                return err(str(e), 409)
        return JSONResponse(out, status_code=400 if out.get('errores') else 200)

    @r.post('/api/formularios/{fid}/estado')
    async def form_estado(fid: str, request: Request):
        b, email = await request.json(), current_email(request)
        f = forms.obtener(fid)
        if not f:
            return err('no existe', 404)
        if not es_admin(email, f['tema']):
            return err('Sin permiso sobre el tema de este formulario.', 403)
        if b.get('estado') not in ESTADOS:
            return err(f'estado debe ser uno de {", ".join(ESTADOS)}')
        return forms.cambiar_estado(fid, b['estado'], email)

    @r.post('/api/formularios/{fid}/fuente')
    async def form_fuente(fid: str, request: Request, archivo: UploadFile):
        f = forms.obtener(fid)
        if not f or not es_admin(current_email(request), f['tema']):
            return err('Sin permiso sobre el tema de este formulario.', 403)
        data = await archivo.read()
        if len(data) > 50 * 1024 * 1024:
            return err('El archivo pesa más de 50 MB.')
        return {'fuente_key': forms.subir_fuente(fid, archivo.filename or 'fuente', data,
                                                 archivo.content_type or 'application/octet-stream')}

    @r.get('/api/formularios/{fid}/fuente')
    def form_fuente_get(fid: str, request: Request):
        f = forms.obtener(fid)
        if not f or not f.get('fuente_key') or not es_admin(current_email(request), f['tema']):
            return err('no disponible', 404)
        nombre = f['fuente_key'].rsplit('/', 1)[-1]
        return Response(forms.objects.get_bytes(f['fuente_key']), media_type='application/octet-stream',
                        headers={'Content-Disposition': f'attachment; filename="{nombre}"'})

    return r
