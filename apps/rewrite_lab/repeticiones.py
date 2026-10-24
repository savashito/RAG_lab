"""
Página «🔁 Ronda 1 real» del Benchmark: vuelve a pasar las conversaciones REALES de la ronda 1 del estudio
(piloto_penal) por el asistente del estudio con otra configuración, y compara.

Cada conversación se repite en orden: los mensajes de la persona son los reales; el asistente responde de nuevo y su
respuesta entra al historial. Cada respuesta se mide sin juez con study.analisis.analizar_respuesta (incluye las
métricas corregidas del 24-oct: «nombra el código penal de otro estado» y «pide el estado»).

Muestra los mensajes de las personas participantes: solo para administradores (como /estudios).

Tablas: rep_corridas (una por configuración × repetición) y rep_conversaciones (una fila por conversación repetida).
"""
from __future__ import annotations

import hashlib
import json
import random
import statistics as st
import threading
import time
from collections import defaultdict
from typing import Callable

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from study.analisis import analizar_respuesta
from study.validar import escenario_efectivo

ESTUDIO = 'piloto_penal'
SCHEMA = """
CREATE TABLE IF NOT EXISTS rep_corridas (
    id serial PRIMARY KEY, nombre text NOT NULL, config jsonb NOT NULL, prompt_tag text, prompt_md5 text,
    repeticion int NOT NULL DEFAULT 1, multiturno boolean NOT NULL DEFAULT false, n int NOT NULL DEFAULT 0,
    done int NOT NULL DEFAULT 0, status text NOT NULL DEFAULT 'running', error text, nota text, creado_por text,
    created_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz);
CREATE TABLE IF NOT EXISTS rep_conversaciones (
    id serial PRIMARY KEY, corrida_id int NOT NULL REFERENCES rep_corridas(id) ON DELETE CASCADE,
    intento_id int NOT NULL, escenario text, variante text, turnos jsonb NOT NULL);
CREATE INDEX IF NOT EXISTS rep_conversaciones_corrida ON rep_conversaciones(corrida_id);
"""
_STALE_SQL = "UPDATE rep_corridas SET status = 'error', error = 'interrumpida (la app se reinició)' WHERE status = 'running'"
# Lo que se puede elegir al lanzar (todo lo demás es la configuración del estudio de la ronda 1).
OPCIONES = ('filtro_estado', 'condensa', 'rerank', 'seguir_remisiones', 'descomponer', 'route', 'hyde')
METRICAS = {
    'otro_codigo': ('Nombra el código penal de otro estado', lambda a: bool(a.get('otro_codigo_estatal'))),
    'ley_correcta': ('Cita la ley correcta de la situación', lambda a: bool(a.get('cita_ley_gold'))),
    'articulo_correcto': ('Cita el artículo correcto', lambda a: bool(a.get('cita_articulo_gold'))),
}


def md5(t: str) -> str:
    return hashlib.md5((t or '').encode()).hexdigest()


def _media(xs):
    xs = [x for x in xs if x is not None]
    return round(100 * st.mean(xs), 1) if xs else None


def _ic(d: list[float], seed: int = 1) -> list[float] | None:
    """IC 95 % del promedio por bootstrap (remuestrea las conversaciones)."""
    if len(d) < 2:
        return None
    rng = random.Random(seed)
    bs = sorted(st.mean(rng.choices(d, k=len(d))) for _ in range(4000))
    return [round(100 * bs[100], 1), round(100 * bs[3899], 1)]


def medir_turno(t: dict) -> dict:
    """Métricas de un turno ya medido: las de la ronda 1 más «pide el estado» separado por lo que sabía el filtro."""
    a = t.get('analisis') or {}
    fl = t.get('filtro')
    sabe = None if fl is None else bool((fl or {}).get('estados'))
    out = {k: f(a) for k, (_, f) in METRICAS.items()}
    out['pide'] = bool(a.get('pide_lugar_estricto'))
    out['sabe_estado'] = sabe
    return out


def resumir(convs: list[dict]) -> dict:
    """convs: [{'intento_id', 'escenario', 'turnos': [...]}] (todas las repeticiones de una configuración).
    Primer mensaje vs mensajes siguientes; «pide el estado» separado en «sin estado» (debe pedirlo) y «ya lo sabía»."""
    g = defaultdict(list)
    seg = []
    for c in convs:
        for j, t in enumerate(c['turnos']):
            m = medir_turno(t)
            parte = 'primer' if j == 0 else 'siguientes'
            for k in METRICAS:
                g[f'{parte}.{k}'].append(m[k])
            if m['sabe_estado'] is True:
                g[f'{parte}.repregunta'].append(m['pide'])
            elif m['sabe_estado'] is False:
                g[f'{parte}.pide_sin_estado'].append(m['pide'])
            else:
                g[f'{parte}.pide_sin_filtro'].append(m['pide'])
            if t.get('segundos') is not None:
                seg.append(t['segundos'])
    out = {k: {'pct': _media(v), 'n': len(v)} for k, v in g.items()}
    out['segundos'] = round(st.mean(seg), 1) if seg else None
    out['conversaciones'] = len({c['intento_id'] for c in convs})
    return out


def por_conversacion(convs: list[dict], parte: str, metrica: str) -> dict:
    """intento_id → promedio entre repeticiones de la métrica (primer mensaje, o proporción en los siguientes)."""
    v = defaultdict(list)
    for c in convs:
        ts = c['turnos'][:1] if parte == 'primer' else c['turnos'][1:]
        if ts:
            v[c['intento_id']].append(st.mean(METRICAS[metrica][1](t.get('analisis') or {}) for t in ts))
    return {k: st.mean(x) for k, x in v.items()}


class Repeticiones:
    def __init__(self, *, connect: Callable, chat_stream: Callable, study_store, resolver: Callable, gold_refs: Callable,
                 current_email: Callable, can_run: Callable, prompts: Callable | None = None):
        self.connect, self.chat_stream, self.store = connect, chat_stream, study_store
        self.prompts = prompts or (lambda: [])   # () → [{'nombre', 'texto', 'nota'}]: los prompts que se pueden cambiar aquí
        self.resolver, self.gold_refs = resolver, gold_refs
        self.current_email, self.can_run = current_email, can_run
        self._lock = threading.Lock()
        self._running: int | None = None
        with connect() as c, c.cursor() as cur:
            cur.execute(SCHEMA)
            cur.execute(_STALE_SQL)
            c.commit()
        self.router = self._make_router()

    # ── datos de la ronda 1 ───────────────────────────────────────────────────────
    def _ronda1(self) -> dict:
        datos = self.store.export(ESTUDIO)
        spec = self.store.spec(ESTUDIO)
        por_id = {e['id']: e for e in spec['escenarios']}
        gold = {}
        for i in datos['intentos']:
            k = (i['escenario'], i['variante'])
            if k not in gold and i['escenario'] in por_id:
                ef = escenario_efectivo(por_id[i['escenario']], i['variante'])
                gold[k] = self.resolver([g for x in ef.get('gold') or [] for g in self.gold_refs(x)])
        turnos = defaultdict(list)
        for t in datos['turnos']:
            turnos[t['intento_id']].append(t)
        for v in turnos.values():
            v.sort(key=lambda t: t['n'])
        cond = {p['codigo']: p['condicion'] or 'piloto' for p in datos['participantes']}
        return {'spec': spec, 'gold': gold, 'turnos': turnos, 'cond': cond,
                'intentos': [i for i in datos['intentos'] if turnos.get(i['id'])]}

    def _original(self, r1: dict) -> dict[str, list[dict]]:
        """Las respuestas que se guardaron en la ronda 1, como si fueran una corrida más (una por condición)."""
        out = defaultdict(list)
        for i in r1['intentos']:
            g = r1['gold'].get((i['escenario'], i['variante'])) or []
            ts = [{'n': t['n'], 'respuesta': t['respuesta'], 'filtro': None, 'segundos': t['segundos'],
                   'analisis': analizar_respuesta(t['respuesta'] or '', g)} for t in r1['turnos'][i['id']] if t['respuesta']]
            if ts:
                out[f'ronda1 · {r1["cond"].get(i["codigo"], "?")}'].append(
                    {'intento_id': i['id'], 'escenario': i['escenario'], 'variante': i['variante'], 'turnos': ts})
        return out

    # ── correr ────────────────────────────────────────────────────────────────────
    def correr(self, body: dict, email: str | None) -> list[int]:
        nombre = str(body.get('nombre') or '').strip()[:60]
        tag = str(body.get('prompt_tag') or '').strip()
        reps = max(1, min(3, int(body.get('repeticiones') or 1)))
        if not nombre or not tag:
            raise ValueError('Falta el nombre de la configuración o el prompt.')
        with self.connect() as c, c.cursor() as cur:
            cur.execute('SELECT text FROM bench_prompt_tags WHERE tag = %s', (tag,))
            fila = cur.fetchone()
        if not fila:
            raise ValueError(f'No hay ningún prompt con la etiqueta «{tag}» (🗂️ Prompts).')
        r1 = self._ronda1()
        cfg = dict(r1['spec']['asistente'], sistema=fila[0])
        for k in OPCIONES:
            if k in body:
                cfg[k] = body[k] if k == 'condensa' else bool(body[k])
        multiturno = bool(body.get('multiturno'))
        intentos = [i for i in r1['intentos'] if len(r1['turnos'][i['id']]) >= (2 if multiturno else 1)]
        with self._lock:
            if self._running:
                raise RuntimeError(f'Ya hay una repetición en curso (#{self._running}).')
            ids = []
            with self.connect() as c, c.cursor() as cur:
                for rep in range(1, reps + 1):
                    cur.execute("INSERT INTO rep_corridas (nombre, config, prompt_tag, prompt_md5, repeticion, multiturno, n, nota, creado_por) "
                                "VALUES (%s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                                (nombre, json.dumps({k: v for k, v in cfg.items() if k != 'sistema'}, ensure_ascii=False), tag,
                                 md5(fila[0]), rep, multiturno, len(intentos), str(body.get('nota') or '')[:300] or None, email))
                    ids.append(cur.fetchone()[0])
                c.commit()
            self._running = ids[0]
        threading.Thread(target=self._correr, args=(ids, cfg, intentos, r1), daemon=True).start()
        return ids

    def _correr(self, ids: list[int], cfg: dict, intentos: list[dict], r1: dict) -> None:
        for rid in ids:
            self._running, error = rid, None
            try:
                for i in intentos:
                    self._guardar(rid, i, self._repetir(cfg, i, r1))
            except Exception as e:  # noqa: BLE001
                error = f'{type(e).__name__}: {e}'
            with self.connect() as c, c.cursor() as cur:
                cur.execute("UPDATE rep_corridas SET status = %s, error = %s, finished_at = now() WHERE id = %s",
                            ('error' if error else 'done', error, rid))
                c.commit()
        self._running = None

    def _repetir(self, cfg: dict, i: dict, r1: dict) -> list[dict]:
        gold = r1['gold'].get((i['escenario'], i['variante'])) or []
        msgs, filas = [], []
        for t in r1['turnos'][i['id']]:
            msgs.append({'role': 'user', 'content': t['pregunta']})
            t0, partes, filtro, busqueda, err = time.time(), [], None, None, None
            for ev in self.chat_stream(msgs, cfg):
                st_ = ev.get('stage')
                if st_ == 'token':
                    partes.append(ev.get('text') or '')
                elif st_ == 'filtro':
                    filtro = {k: ev.get(k) for k in ('estados', 'otros', 'faltan', 'tipo')}
                elif st_ == 'search':
                    busqueda = ev.get('query')
                elif st_ == 'error':
                    err = ev.get('error')
            resp = ''.join(partes)
            msgs.append({'role': 'assistant', 'content': resp})
            filas.append({'n': t['n'], 'turno_original': t['id'], 'segundos': round(time.time() - t0, 1), 'error': err,
                          'filtro': filtro, 'busqueda': busqueda, 'respuesta': resp, 'analisis': analizar_respuesta(resp, gold)})
        return filas

    def _guardar(self, rid: int, i: dict, turnos: list[dict]) -> None:
        with self.connect() as c, c.cursor() as cur:
            cur.execute("INSERT INTO rep_conversaciones (corrida_id, intento_id, escenario, variante, turnos) "
                        "VALUES (%s, %s, %s, %s, %s::jsonb)",
                        (rid, i['id'], i['escenario'], i['variante'], json.dumps(turnos, ensure_ascii=False)))
            cur.execute('UPDATE rep_corridas SET done = done + 1 WHERE id = %s', (rid,))
            c.commit()

    def importar(self, nombre: str, config: dict, prompt_tag: str, repeticion: int, multiturno: bool, filas: list[dict],
                 nota: str | None = None) -> int:
        """Carga una repetición hecha con el script (06_evaluation/replay_ronda1_2026-10-24/repetir_ronda1.py).
        Vuelve a medir cada respuesta, para que todas tengan las métricas corregidas."""
        r1 = self._ronda1()
        with self.connect() as c, c.cursor() as cur:
            cur.execute('SELECT md5 FROM bench_prompt_tags WHERE tag = %s', (prompt_tag,))
            pm = (cur.fetchone() or [None])[0]
            cur.execute("INSERT INTO rep_corridas (nombre, config, prompt_tag, prompt_md5, repeticion, multiturno, n, done, status, "
                        "nota, creado_por, finished_at) VALUES (%s, %s::jsonb, %s, %s, %s, %s, %s, %s, 'done', %s, 'script', now()) "
                        "RETURNING id", (nombre, json.dumps(config, ensure_ascii=False), prompt_tag, pm, repeticion,
                                         multiturno, len(filas), len(filas), nota))
            rid = cur.fetchone()[0]
            for x in filas:
                g = r1['gold'].get((x['escenario'], x['variante'])) or []
                for t in x['turnos']:
                    t['analisis'] = analizar_respuesta(t.get('respuesta') or '', g)
                cur.execute("INSERT INTO rep_conversaciones (corrida_id, intento_id, escenario, variante, turnos) "
                            "VALUES (%s, %s, %s, %s, %s::jsonb)",
                            (rid, x['intento_id'], x['escenario'], x['variante'], json.dumps(x['turnos'], ensure_ascii=False)))
            c.commit()
        return rid

    # ── leer ──────────────────────────────────────────────────────────────────────
    def corridas(self) -> list[dict]:
        with self.connect() as c, c.cursor() as cur:
            cur.execute("SELECT id, nombre, config, prompt_tag, prompt_md5, repeticion, multiturno, n, done, status, error, nota, "
                        "creado_por, created_at::text, finished_at::text FROM rep_corridas ORDER BY id DESC")
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    def _convs(self, nombres: list[str] | None = None) -> dict[str, list[dict]]:
        with self.connect() as c, c.cursor() as cur:
            cur.execute("SELECT r.nombre, v.intento_id, v.escenario, v.variante, v.turnos, r.repeticion FROM rep_conversaciones v "
                        "JOIN rep_corridas r ON r.id = v.corrida_id WHERE r.status = 'done'" +
                        (" AND r.nombre = ANY(%s)" if nombres else ''), (nombres,) if nombres else ())
            out = defaultdict(list)
            for nombre, iid, esc, var, turnos, rep in cur.fetchall():
                out[nombre].append({'intento_id': iid, 'escenario': esc, 'variante': var, 'turnos': turnos, 'rep': rep})
            return out

    def resumen(self) -> dict:
        convs = self._convs()
        r1 = self._ronda1()
        convs.update(self._original(r1))
        meta = defaultdict(dict)
        for x in self.corridas():
            m = meta[x['nombre']]
            m.setdefault('reps', set()).add(x['repeticion'])
            m.update(config=x['config'], prompt_tag=x['prompt_tag'], multiturno=x['multiturno'], nota=x['nota'] or m.get('nota'))
        filas = []
        for nombre, cs in convs.items():
            m = meta.get(nombre, {})
            filas.append({'nombre': nombre, 'original': nombre.startswith('ronda1 · '), 'reps': sorted(m.get('reps', [])),
                          'config': m.get('config'), 'prompt_tag': m.get('prompt_tag'), 'multiturno': m.get('multiturno'),
                          'nota': m.get('nota'), **resumir(cs)})
        filas.sort(key=lambda f: (not f['original'], f['nombre']))
        return {'configuraciones': filas, 'metricas': {k: v[0] for k, v in METRICAS.items()},
                'en_curso': self._running, 'conversaciones_ronda1': len(r1['intentos'])}

    def comparar(self, a: str, b: str) -> dict:
        convs = self._convs([a, b])
        if a.startswith('ronda1 · ') or b.startswith('ronda1 · '):
            convs.update(self._original(self._ronda1()))
        out = {}
        for parte in ('primer', 'siguientes'):
            for k in METRICAS:
                va, vb = por_conversacion(convs.get(a, []), parte, k), por_conversacion(convs.get(b, []), parte, k)
                d = [vb[i] - va[i] for i in va if i in vb]
                out[f'{parte}.{k}'] = {'dif': round(100 * st.mean(d), 1) if d else None, 'ic': _ic(d), 'n': len(d)}
        return {'a': a, 'b': b, 'diferencias': out}

    def conversaciones(self) -> list[dict]:
        r1 = self._ronda1()
        return [{'intento_id': i['id'], 'escenario': i['escenario'], 'variante': i['variante'],
                 'condicion': r1['cond'].get(i['codigo']), 'mensajes': len(r1['turnos'][i['id']])} for i in r1['intentos']]

    def conversacion(self, intento_id: int, nombres: list[str]) -> dict:
        r1 = self._ronda1()
        i = next((x for x in r1['intentos'] if x['id'] == intento_id), None)
        if not i:
            raise ValueError('esa conversación no está en la ronda 1')
        g = r1['gold'].get((i['escenario'], i['variante'])) or []
        original = [{'n': t['n'], 'pregunta': t['pregunta'], 'respuesta': t['respuesta'],
                     'analisis': analizar_respuesta(t['respuesta'] or '', g)} for t in r1['turnos'][intento_id]]
        convs = self._convs(nombres)
        reps = {n: sorted([c for c in convs.get(n, []) if c['intento_id'] == intento_id], key=lambda c: c['rep'])
                for n in nombres}
        return {'intento_id': intento_id, 'escenario': i['escenario'], 'variante': i['variante'],
                'condicion': r1['cond'].get(i['codigo']), 'gold': [[x['label'] for x in grupo] for grupo in g],
                'original': original, 'repeticiones': reps}

    # ── rutas ─────────────────────────────────────────────────────────────────────
    def _make_router(self) -> APIRouter:
        r = APIRouter(prefix='/api/repeticiones')

        def deny():
            return JSONResponse({'error': 'Solo administradores: esta página muestra mensajes de participantes.'}, status_code=403)

        def bad(msg):
            return JSONResponse({'error': msg}, status_code=400)

        @r.get('')
        def resumen(request: Request):
            return self.resumen() if self.can_run(self.current_email(request)) else deny()

        @r.get('/prompts')
        def prompts(request: Request):
            return self.prompts() if self.can_run(self.current_email(request)) else deny()

        @r.get('/corridas')
        def corridas(request: Request):
            return self.corridas() if self.can_run(self.current_email(request)) else deny()

        @r.get('/comparar')
        def comparar(a: str, b: str, request: Request):
            return self.comparar(a, b) if self.can_run(self.current_email(request)) else deny()

        @r.get('/conversaciones')
        def conversaciones(request: Request):
            return self.conversaciones() if self.can_run(self.current_email(request)) else deny()

        @r.get('/conversaciones/{intento_id}')
        def conversacion(intento_id: int, request: Request, nombres: str = ''):
            if not self.can_run(self.current_email(request)):
                return deny()
            try:
                return self.conversacion(intento_id, [n for n in nombres.split('|') if n])
            except ValueError as e:
                return bad(str(e))

        @r.post('/correr')
        async def correr(request: Request):
            email = self.current_email(request)
            if not self.can_run(email):
                return deny()
            try:
                return {'corridas': self.correr(await request.json(), email)}
            except (RuntimeError, ValueError) as e:
                return bad(str(e))

        return r
