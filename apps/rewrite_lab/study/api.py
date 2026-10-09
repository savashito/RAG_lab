"""Rutas HTTP del estudio con usuarios.

  /estudio    página de participantes: entran con su código (sin cuenta de Google).
  /calificar  página de calificación a ciegas: entran con un código de calificador.
  /estudios   administración (requiere sesión de admin): editar el estudio, crear códigos,
              ver avance y exportar.

El código viaja en el encabezado `X-Codigo`, nunca en la URL. Las rutas /api/estudio/p/* y
/api/estudio/c/* son públicas en la puerta de auth (ver auth.PUBLIC_PREFIXES): las protege el código.
"""
from __future__ import annotations

import json
import time

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from study.analisis import lugares_mencionados, rango_gold, resumen
from study.store import NoPermitido
from study.validar import (CITA, DANOS, ESTADOS, GRUPOS, ROLES_CALIFICADOR, SI_NO_NS, VEREDICTOS,
                           escenario_efectivo, limpiar_perfil, vista_publica)

MAX_MENSAJE = 2000


def _err(msg, status=400):
    return JSONResponse({'error': msg}, status_code=status)


def _fuentes(chunks: list[dict]) -> list[dict]:
    """Lo que se guarda (y se muestra) de cada fragmento que el asistente tuvo como contexto."""
    return [{'id': ch.get('id'), 'rank': ch.get('rank'), 'source': ch.get('source'),
             'cita': ch.get('doc_label') or ch.get('citation') or ch.get('source'),
             'jerarquia': ch.get('hierarchy') or ch.get('title') or '', 'texto': ch.get('text') or '',
             'vecino': bool(ch.get('neighbor'))} for ch in chunks or []]


def make_router(*, store, chat, gold_refs, resolver_gold, static_dir, current_email, es_admin,
                chat_stream=None) -> APIRouter:
    """`chat(messages, cfg)` = chat_answer del app con la configuración del estudio; `chat_stream(messages, cfg)`,
    lo mismo como eventos (retrieving → context → token* → done | error) para mostrar la respuesta mientras se escribe.
    `gold_refs(texto)` → grupos de artículos (sin BD); `resolver_gold(grupos)` les pone sus ids."""
    r = APIRouter()

    def acceso(request: Request, tipo: str) -> dict:
        return store.entrar(request.headers.get('x-codigo', ''), tipo)

    def guard(fn):
        """Convierte NoPermitido en 403 sin repetir try/except en cada ruta."""
        async def wrapper(request: Request):
            try:
                return await fn(request)
            except NoPermitido as e:
                return _err(str(e), 403)
        wrapper.__name__ = fn.__name__
        return wrapper

    # ── Páginas ─────────────────────────────────────────────────────────────────
    for path, archivo in (('/estudio', 'estudio.html'), ('/calificar', 'calificar.html'), ('/estudios', 'estudios.html')):
        r.add_api_route(path, (lambda a=archivo: FileResponse(static_dir / a, headers={'Cache-Control': 'no-store'})),
                        methods=['GET'], include_in_schema=False)

    # ── Participantes ───────────────────────────────────────────────────────────
    def estado_participante(a: dict) -> dict:
        p = store.participante(a['codigo'])
        out = {'grupo_es_estudiante': a['grupo'] == 'estudiante', 'consentido': bool(p)}
        if p:
            out.update(vista_publica(a['spec'], p['asignados'], p['variantes']))
            out['intentos'] = store.intentos(a['codigo'])
            out['terminado'] = bool(p['terminado_at'])
            out['tutorial_hecho'] = bool(p['tutorial_at']) or not out.get('tutorial')
            out['practicas'] = p['practicas']
        else:
            out.update({k: v for k, v in vista_publica(a['spec'], []).items() if k != 'escenarios'})
        return out

    @r.post('/api/estudio/p/estado')
    @guard
    async def p_estado(request: Request):
        return estado_participante(acceso(request, 'participante'))

    @r.post('/api/estudio/p/consentir')
    @guard
    async def p_consentir(request: Request):
        a, b = acceso(request, 'participante'), await request.json()
        if not b.get('acepto'):
            return _err('Para participar hay que aceptar el consentimiento.')
        perfil, faltan = limpiar_perfil(a['spec'], b.get('perfil') or {})
        if faltan:
            return _err('Falta contestar: ' + '; '.join(faltan))
        store.consentir(a, perfil)
        return estado_participante(a)

    @r.post('/api/estudio/p/iniciar')
    @guard
    async def p_iniciar(request: Request):
        a, b = acceso(request, 'participante'), await request.json()
        it = store.iniciar(a['codigo'], str(b.get('escenario') or ''))
        return {'intento': it, 'turnos': [{'pregunta': t['pregunta'], 'respuesta': t['respuesta'],
                                           'fuentes': t['contexto'], 'error': t['error']} for t in store.turnos(it['id'])]}

    @r.post('/api/estudio/p/preguntar')
    @guard
    async def p_preguntar(request: Request):
        a, b = acceso(request, 'participante'), await request.json()
        it = store.intento_abierto(a['codigo'], int(b.get('intento') or 0), para_preguntar=True)
        mensaje = str(b.get('mensaje') or '').strip()[:MAX_MENSAJE]
        if not mensaje:
            return _err('Escribe tu pregunta.')
        cfg = a['spec'].get('asistente') or {}
        previos = store.turnos(it['id'])
        if len(previos) >= int(cfg.get('max_turnos', 12)):
            return _err('Llegaste al máximo de preguntas para este escenario. Pasa a las preguntas finales.')
        messages = []
        for t in previos:
            if t['respuesta']:
                messages += [{'role': 'user', 'content': t['pregunta']}, {'role': 'assistant', 'content': t['respuesta']}]
        messages.append({'role': 'user', 'content': mensaje})
        t0, out, error = time.time(), None, None
        try:
            out = await run_in_threadpool(chat, messages, cfg)
            out['contexto'] = _fuentes(out.get('chunks'))
        except Exception as e:  # noqa: BLE001 — se registra el fallo; la persona puede reintentar
            error = f'{type(e).__name__}: {e}'
        store.guardar_turno(it['id'], len(previos) + 1, mensaje, out, error, config=cfg)
        print(f'estudio: turno {len(previos) + 1} · {round(time.time() - t0, 1)}s'
              + (' · error' if error else ''), flush=True)
        if error:
            return _err('El asistente no pudo responder. Intenta de nuevo en un momento.', 502)
        return {'respuesta': out['answer'], 'fuentes': out['contexto']}

    # ── Streaming: la respuesta aparece mientras se escribe ───────────────────────
    def _sse(obj):
        return f'data: {json.dumps(obj, ensure_ascii=False)}\n\n'

    def _stream(messages, cfg, al_terminar):
        """Reenvía al navegador solo lo que la persona necesita ver (estado, texto, fuentes) y, al terminar
        o si se corta, llama `al_terminar(out, error)` con la respuesta completa para guardarla."""
        t0, out, partes, error = time.time(), {}, [], None
        try:
            yield _sse({'stage': 'buscando'})
            for ev in chat_stream(messages, cfg):
                st = ev.get('stage')
                if st == 'context':
                    out.update(contexto=_fuentes(ev.get('chunks')), ranking=ev.get('ranking') or [],
                               search_query=ev.get('search_query'), score_kind=ev.get('score_kind'),
                               rewrite=ev.get('rewrite'))
                    yield _sse({'stage': 'escribiendo'})
                elif st == 'hyde':
                    out['hyde_passage'] = ev.get('passage')
                elif st == 'decompose':
                    out['subqueries'] = ev.get('subqueries')
                elif st == 'route':
                    out['routes'] = ev.get('routes')
                elif st == 'token':
                    partes.append(ev.get('text') or '')
                    yield _sse({'stage': 'token', 'text': ev.get('text') or ''})
                elif st == 'error':
                    error = ev.get('error') or 'error'
                    yield _sse({'stage': 'error', 'error': 'El asistente no pudo responder. Intenta de nuevo en un momento.'})
                    return
            yield _sse({'stage': 'done', 'fuentes': out.get('contexto') or []})
        except GeneratorExit:      # la persona cerró o recargó a media respuesta
            error = error or 'interrumpido: la conexión se cerró antes de terminar'
            raise
        except Exception as e:     # noqa: BLE001
            error = f'{type(e).__name__}: {e}'
            yield _sse({'stage': 'error', 'error': 'El asistente no pudo responder. Intenta de nuevo en un momento.'})
        finally:
            out.update(answer=''.join(partes) or None, seconds=round(time.time() - t0, 1))
            al_terminar(out, error)

    def _respuesta_sse(gen):
        return StreamingResponse(gen, media_type='text/event-stream',
                                 headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    @r.post('/api/estudio/p/preguntar_stream')
    @guard
    async def p_preguntar_stream(request: Request):
        a, b = acceso(request, 'participante'), await request.json()
        it = store.intento_abierto(a['codigo'], int(b.get('intento') or 0), para_preguntar=True)
        mensaje = str(b.get('mensaje') or '').strip()[:MAX_MENSAJE]
        if not mensaje:
            return _err('Escribe tu pregunta.')
        cfg = a['spec'].get('asistente') or {}
        previos = store.turnos(it['id'])
        if len(previos) >= int(cfg.get('max_turnos', 12)):
            return _err('Llegaste al máximo de preguntas para este escenario. Pasa a las preguntas finales.')
        messages = []
        for t in previos:
            if t['respuesta'] and not t['error']:
                messages += [{'role': 'user', 'content': t['pregunta']}, {'role': 'assistant', 'content': t['respuesta']}]
        messages.append({'role': 'user', 'content': mensaje})
        n = len(previos) + 1

        def guardar(out, error):
            store.guardar_turno(it['id'], n, mensaje, out, error, config=cfg)
            print(f'estudio: turno {n} · {out.get("seconds")}s · streaming' + (' · error' if error else ''), flush=True)
        return _respuesta_sse(_stream(messages, cfg, guardar))

    @r.post('/api/estudio/p/practica_stream')
    @guard
    async def p_practica_stream(request: Request):
        """Práctica del tutorial en streaming: no se guarda (solo cuenta cuántas preguntas)."""
        a, b = acceso(request, 'participante'), await request.json()
        if not store.participante(a['codigo']):
            return _err('Primero acepta el consentimiento.')
        mensaje = str(b.get('mensaje') or '').strip()[:MAX_MENSAJE]
        if not mensaje:
            return _err('Escribe una pregunta.')
        maximo = int((a['spec'].get('tutorial') or {}).get('max_preguntas', 2))
        if not store.contar_practica(a['codigo'], maximo):
            return _err('Ya hiciste las preguntas de práctica. Da clic en «Entendido, empezar».')
        return _respuesta_sse(_stream([{'role': 'user', 'content': mensaje}], a['spec'].get('asistente') or {},
                                      lambda out, error: None))

    @r.post('/api/estudio/p/practica')
    @guard
    async def p_practica(request: Request):
        """Pregunta de práctica del tutorial: responde el asistente real, pero no se guarda."""
        a, b = acceso(request, 'participante'), await request.json()
        if not store.participante(a['codigo']):
            return _err('Primero acepta el consentimiento.')
        mensaje = str(b.get('mensaje') or '').strip()[:MAX_MENSAJE]
        if not mensaje:
            return _err('Escribe una pregunta.')
        maximo = int((a['spec'].get('tutorial') or {}).get('max_preguntas', 2))
        if not store.contar_practica(a['codigo'], maximo):
            return _err('Ya hiciste las preguntas de práctica. Da clic en «Entendido, empezar».')
        try:
            out = await run_in_threadpool(chat, [{'role': 'user', 'content': mensaje}], a['spec'].get('asistente') or {})
        except Exception:  # noqa: BLE001
            return _err('El asistente no pudo responder. Intenta de nuevo en un momento.', 502)
        return {'respuesta': out['answer'], 'fuentes': _fuentes(out.get('chunks'))}

    @r.post('/api/estudio/p/tutorial_listo')
    @guard
    async def p_tutorial_listo(request: Request):
        a = acceso(request, 'participante')
        store.tutorial_listo(a['codigo'])
        return estado_participante(a)

    @r.post('/api/estudio/p/a_preguntas')
    @guard
    async def p_a_preguntas(request: Request):
        a, b = acceso(request, 'participante'), await request.json()
        store.a_preguntas(a['codigo'], int(b.get('intento') or 0))
        return {'ok': True}

    @r.post('/api/estudio/p/terminar')
    @guard
    async def p_terminar(request: Request):
        a, b = acceso(request, 'participante'), await request.json()
        confianza = b.get('confianza')
        if confianza not in (1, 2, 3, 4, 5) or b.get('actuaria') not in SI_NO_NS or b.get('detecto') not in SI_NO_NS:
            return _err('Contesta todas las preguntas.')
        store.terminar(a['codigo'], int(b.get('intento') or 0), a['spec'], b.get('respuestas') or {},
                       confianza, b['actuaria'], b['detecto'], str(b.get('detecto_cual') or '')[:2000])
        return estado_participante(a)

    @r.post('/api/estudio/p/cierre')
    @guard
    async def p_cierre(request: Request):
        a, b = acceso(request, 'participante'), await request.json()
        sus = [x for x in (b.get('sus') or []) if x in (1, 2, 3, 4, 5)]
        abiertas = {str(k): str(v)[:2000] for k, v in (b.get('abiertas') or {}).items()}
        store.cerrar(a['codigo'], {'sus': sus, 'abiertas': abiertas})
        return estado_participante(a)

    @r.post('/api/estudio/p/retirar')
    @guard
    async def p_retirar(request: Request):
        store.retirar(acceso(request, 'participante')['codigo'])
        return {'ok': True}

    # ── Kiosco (una computadora en sesión presencial) ───────────────────────────
    @r.post('/api/estudio/k/estado')
    @guard
    async def k_estado(request: Request):
        k = store.kiosco(request.headers.get('x-kiosco', ''))
        spec = store.spec(k['estudio'])
        return {'titulo': k['titulo'], 'duracion': spec.get('duracion') or 'unos 15 minutos',
                'situaciones': len(spec.get('escenarios') or [])}

    @r.post('/api/estudio/k/nuevo')
    @guard
    async def k_nuevo(request: Request):
        return {'codigo': store.nuevo_desde_kiosco(request.headers.get('x-kiosco', ''))}

    # ── Calificación a ciegas ───────────────────────────────────────────────────
    def tarea(a: dict, turno_id: int | None) -> dict:
        out = {'rol': a['grupo'], **store.progreso_calificador(a)}
        if turno_id is None:
            return {**out, 'turno': None}
        t = store.para_calificar(turno_id)
        esc = escenario_efectivo(next((e for e in a['spec']['escenarios'] if e['id'] == t['escenario']), {}), t['variante'])
        gold = [x['label'] for g in esc.get('gold') or [] for grupo in gold_refs(g) for x in grupo]
        # Ciego: no se muestra el grupo de la persona ni ningún veredicto de un LLM.
        return {**out, 'turno': {'id': t['id'], 'n': t['n'], 'pregunta': t['pregunta'], 'respuesta': t['respuesta'],
                                 'fuentes': t['contexto'], 'previos': t['previos']},
                'escenario': {'titulo': esc.get('titulo'), 'texto': esc.get('texto'),
                              'referencia': esc.get('referencia'), 'gold': gold}}

    @r.post('/api/estudio/c/siguiente')
    @guard
    async def c_siguiente(request: Request):
        a = acceso(request, 'calificador')
        return tarea(a, store.siguiente(a))

    @r.post('/api/estudio/c/calificar')
    @guard
    async def c_calificar(request: Request):
        a, b = acceso(request, 'calificador'), await request.json()
        c = {'veredicto': b.get('veredicto'), 'dano': b.get('dano'), 'error_jurisdiccion': b.get('error_jurisdiccion'),
             'cita': b.get('cita'), 'notas': str(b.get('notas') or '')[:3000]}
        if (c['veredicto'] not in VEREDICTOS or c['dano'] not in DANOS or c['error_jurisdiccion'] not in SI_NO_NS
                or c['cita'] not in CITA):
            return _err('Faltan campos de la calificación.')
        store.calificar(a, int(b.get('turno') or 0), c)
        return tarea(a, store.siguiente(a))

    # ── Administración ──────────────────────────────────────────────────────────
    def admin(request) -> str | None:
        email = current_email(request)
        return email if es_admin(email) else None

    @r.get('/api/estudios')
    def adm_lista(request: Request):
        if not admin(request):
            return _err('Solo administradores.', 403)
        return store.lista()

    @r.get('/api/estudios/{eid}')
    def adm_get(eid: str, request: Request):
        if not admin(request):
            return _err('Solo administradores.', 403)
        e = store.obtener(eid)
        return e or _err('no existe', 404)

    @r.put('/api/estudios/{eid}')
    async def adm_guardar(eid: str, request: Request):
        email = admin(request)
        if not email:
            return _err('Solo administradores.', 403)
        b = await request.json()
        out = store.guardar(None if eid == '_nuevo' else eid, b.get('spec_yaml', ''), int(b.get('version') or 0), email)
        return JSONResponse(out, status_code=409 if out.get('conflicto') else 400 if out.get('errores') else 200)

    @r.post('/api/estudios/{eid}/estado')
    async def adm_estado(eid: str, request: Request):
        email = admin(request)
        if not email:
            return _err('Solo administradores.', 403)
        estado = (await request.json()).get('estado')
        if estado not in ESTADOS:
            return _err(f'estado debe ser uno de {", ".join(ESTADOS)}')
        return store.cambiar_estado(eid, estado, email)

    @r.get('/api/estudios/{eid}/codigos')
    def adm_codigos(eid: str, request: Request):
        if not admin(request):
            return _err('Solo administradores.', 403)
        return store.codigos(eid)

    @r.post('/api/estudios/{eid}/codigos')
    async def adm_crear_codigos(eid: str, request: Request):
        email = admin(request)
        if not email:
            return _err('Solo administradores.', 403)
        b = await request.json()
        tipo, grupo, n = b.get('tipo'), b.get('grupo'), int(b.get('n') or 0)
        validos = GRUPOS if tipo == 'participante' else ROLES_CALIFICADOR if tipo == 'calificador' else ()
        if grupo not in validos or not 1 <= n <= 200 or not store.obtener(eid):
            return _err('tipo/grupo inválido o n fuera de 1–200.')
        return {'codigos': store.crear_codigos(eid, tipo, grupo, n, str(b.get('nota') or '')[:200], email)}

    @r.post('/api/estudios/{eid}/codigos/{codigo}/activo')
    async def adm_activar(eid: str, codigo: str, request: Request):
        if not admin(request):
            return _err('Solo administradores.', 403)
        store.activar_codigo(codigo, bool((await request.json()).get('activo')))
        return {'ok': True}

    @r.get('/api/estudios/{eid}/kioscos')
    def adm_kioscos(eid: str, request: Request):
        if not admin(request):
            return _err('Solo administradores.', 403)
        return store.kioscos(eid)

    @r.post('/api/estudios/{eid}/kioscos')
    async def adm_crear_kiosco(eid: str, request: Request):
        email = admin(request)
        if not email:
            return _err('Solo administradores.', 403)
        b = await request.json()
        if b.get('grupo', 'general') not in GRUPOS or not store.obtener(eid):
            return _err('grupo inválido.')
        return {'token': store.crear_kiosco(eid, b.get('grupo', 'general'), str(b.get('nota') or '')[:200], email)}

    @r.post('/api/estudios/{eid}/kioscos/{kid}/activo')
    async def adm_activar_kiosco(eid: str, kid: int, request: Request):
        if not admin(request):
            return _err('Solo administradores.', 403)
        store.activar_kiosco(eid, kid, bool((await request.json()).get('activo')))
        return {'ok': True}

    def _export(eid: str) -> dict:
        datos = store.export(eid)
        spec = store.spec(eid)
        por_id = {e['id']: e for e in spec.get('escenarios') or []}
        gold = {}
        for i in datos['intentos']:
            clave = (i['escenario'], i['variante'])
            if clave not in gold and i['escenario'] in por_id:
                ef = escenario_efectivo(por_id[i['escenario']], i['variante'])
                gold[clave] = resolver_gold([grupo for g in ef.get('gold') or [] for grupo in gold_refs(g)])
        esc_de = {i['id']: (i['escenario'], i['variante']) for i in datos['intentos']}
        for t in datos['turnos']:
            grupos = gold.get(esc_de.get(t['intento_id'])) or []
            t['gold'] = [[x['label'] for x in g] for g in grupos]
            t['rangos'] = rango_gold(grupos, t.get('ranking') or [])
            t['lugares_mencionados'] = lugares_mencionados(t['pregunta'])
        datos['resumen'] = resumen(datos)
        return datos

    @r.get('/api/estudios/{eid}/export')
    async def adm_export(eid: str, request: Request):
        if not admin(request):
            return _err('Solo administradores.', 403)
        datos = await run_in_threadpool(_export, eid)
        return JSONResponse(datos, headers={'Content-Disposition': f'attachment; filename="estudio_{eid}.json"'})

    @r.get('/api/estudios/{eid}/resumen')
    async def adm_resumen(eid: str, request: Request):
        if not admin(request):
            return _err('Solo administradores.', 403)
        return (await run_in_threadpool(_export, eid))['resumen']

    return r
