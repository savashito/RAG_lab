"""
Benchmark de la consulta (ronda 3), en 🧪 Benchmark → «Consulta (catálogo)»: simula cada caso con la máquina de estados
(consulta/maquina.py), el LLM de la app (clasificar y extraer) y el catálogo de la base, hasta llegar a la orientación, y
mide si el expediente quedó bien.

  · tipos      los tipos de caso esperados quedaron en el expediente
  · datos      cada dato esperado tiene el valor esperado (acierta, falta o equivocado)
  · reglas     las reglas esperadas aplican y las de `reglas_no` no
  · preguntas  cuántas preguntas hizo antes de orientar (y si pasó de max_preguntas)
  · orienta    llegó a la orientación en a lo más MAX_MENSAJES mensajes de la persona

Configuración de cada corrida (CONFIG, se elige en la página):
  · preguntas      'catalogo' (texto fijo) o 'llm' (las redacta el LLM; cambia lo que ve el extractor)
  · reglas         'todas' o 'confirmadas'
  · repeticiones   cuántas veces se corre cada caso (el LLM no responde igual cada vez)
Mide el cuestionario: termina cuando el expediente está completo y la máquina decide qué reglas aplican. La orientación
(lo que redacta el LLM después) es otro benchmark.

Los casos (inventados, sin datos de participantes) viven en la base (tabla bench_consulta_casos, un YAML) para que se
editen desde la página sin tocar el repo; el primero se carga de 06_evaluation/…/bench_consulta/casos.yaml. Cada corrida
se guarda en bench_consulta_corridas con el md5 del catálogo, el commit y las filas por caso.
"""
from __future__ import annotations

import json
import subprocess
import threading
import time
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Callable

import yaml
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from consulta import maquina as M
from consulta.orientar import mensajes_pregunta
from consulta.catalogo import md5_de

MAX_MENSAJES = 10
NO_SE = 'no sé'
CONFIG = {'preguntas': 'catalogo', 'reglas': 'todas', 'repeticiones': 1}
REPO = Path(__file__).resolve().parents[3]
CASOS_INICIALES = REPO / '06_evaluation' / 'estudio_ronda3_2026-11-10' / 'bench_consulta' / 'casos.yaml'

SCHEMA = """
CREATE TABLE IF NOT EXISTS bench_consulta_casos (
    id int PRIMARY KEY, yaml text NOT NULL, actualizado_por text, updated_at timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS bench_consulta_corridas (
    id serial PRIMARY KEY, creada timestamptz DEFAULT now(), por text, catalogo_md5 text, commit text,
    estado text DEFAULT 'corriendo', resumen jsonb, filas jsonb, error text);
ALTER TABLE bench_consulta_corridas ADD COLUMN IF NOT EXISTS config jsonb;
"""
_STALE_SQL = "UPDATE bench_consulta_corridas SET estado = 'interrumpida' WHERE estado = 'corriendo'"


# ── simular y calificar ───────────────────────────────────────────────────────────────────────────────────────────
def respuesta(caso: dict, dato: str, veces: Counter) -> str:
    """Lo que contesta la persona cuando le piden `dato` (una lista: una respuesta por cada vez)."""
    r = (caso.get('respuestas') or {}).get(dato)
    if isinstance(r, list):
        r = r[min(veces[dato], len(r) - 1)] if r else None
    veces[dato] += 1
    return str(r) if r is not None else NO_SE


def simular(caso: dict, catalogo: dict, ia, config: dict | None = None, redactar: Callable | None = None) -> dict:
    """`redactar(mensajes) → str`: con config preguntas = 'llm', redacta la pregunta como en Preguntar (Catálogo)."""
    config = {**CONFIG, **(config or {})}
    estado = exp = orientacion = None
    historial, preguntas, complementarios, veces = [], [], [], Counter()
    evento = {'tipo': 'mensaje', 'texto': caso['relato']}
    salida, t0 = {}, time.time()
    for _ in range(MAX_MENSAJES):
        estado, exp, salida, _ = M.turno(estado, exp, {**evento, 'historial': list(historial)}, catalogo, ia,
                                         solo_confirmadas=config['reglas'] == 'confirmadas')
        if evento['tipo'] == 'mensaje':
            historial.append({'role': 'user', 'content': evento['texto']})
        if salida['tipo'] == 'orientar':
            orientacion = orientacion or salida      # las reglas se califican con la primera orientación
            if not salida.get('pregunta'):
                break
            # Después de orientar se contestan los datos complementarios (ahí se reescribe la lista de hechos).
            historial.append({'role': 'assistant', 'content': f'[orientación]\n\n{salida["pregunta"]["texto"]}'})
            complementarios.append(salida['pregunta']['dato'])
            evento = {'tipo': 'mensaje', 'texto': respuesta(caso, salida['pregunta']['dato'], veces)}
            continue
        historial.append({'role': 'assistant', 'content': salida['texto']})
        if salida['tipo'] == 'elegir_tipo':                  # elige el primer tipo esperado que esté entre las opciones
            ids = [o['id'] for o in salida['opciones']]
            valor = next((t for t in caso['esperado'].get('tipos', []) if t in ids), M.OTRO)
            preguntas.append('(elegir tipo)')
            historial.append({'role': 'user', 'content': f'▸ {valor}'})
            evento = {'tipo': 'elegir_tipo', 'valor': valor}
            continue
        if salida['tipo'] == 'pregunta' and config['preguntas'] == 'llm' and redactar:   # la pregunta como la ve la persona
            conversacion = '\n'.join(f'{"Persona" if m["role"] == "user" else "Asistente"}: {m["content"]}' for m in historial[:-1])
            texto = (redactar(mensajes_pregunta(conversacion, salida, catalogo, exp)) or '').strip()
            if texto:
                historial[-1] = {'role': 'assistant', 'content': texto}
        (complementarios if orientacion else preguntas).append(salida['dato'])
        evento = {'tipo': 'mensaje', 'texto': respuesta(caso, salida['dato'], veces)}
    return {'estado': estado, 'expediente': exp or {}, 'salida': orientacion or salida, 'preguntas': preguntas,
            'complementarios': complementarios, 'conversacion': historial, 'segundos': round(time.time() - t0, 1)}


def _norm(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', str(s).lower()) if unicodedata.category(c) != 'Mn')


def hechos_conservados(esperados: list[str], hechos: list[str]) -> dict[str, bool]:
    """Cada hecho esperado es una o más palabras separadas por «|» («pistola|arma»): se conserva si alguna aparece en
    la lista de hechos del expediente (sin acentos ni mayúsculas)."""
    texto = _norm(' · '.join(hechos or []))
    return {h: any(_norm(a).strip() in texto for a in h.split('|')) for h in esperados or []}


def calificar(caso: dict, r: dict) -> dict:
    esp, exp, s = caso['esperado'], r['expediente'], r['salida']
    reglas = set(s.get('reglas') or []) if s.get('tipo') == 'orientar' else set()
    datos = {}
    for k, v in (esp.get('datos') or {}).items():
        got = exp.get('datos', {}).get(k)
        datos[k] = 'acierta' if got is not None and str(got) == str(v) else 'falta' if got is None else f'equivocado ({got})'
    preguntas = [p for p in r['preguntas'] if p != '(elegir tipo)']
    return {'orienta': s.get('tipo') == 'orientar',
            'hechos': hechos_conservados(esp.get('hechos'), exp.get('hechos')),
            'tipos': set(esp.get('tipos', [])) <= set(exp.get('tipos_caso', [])),
            'datos': datos,
            'reglas_faltan': sorted(set(esp.get('reglas', [])) - reglas),
            'reglas_de_mas': sorted(set(esp.get('reglas_no', [])) & reglas),
            'n_preguntas': len(preguntas),
            'preguntas_de_mas': max(0, len(preguntas) - esp['max_preguntas']) if 'max_preguntas' in esp else 0}


def fila(caso: dict, catalogo: dict, ia, config: dict | None = None, redactar: Callable | None = None,
         rep: int = 1) -> dict:
    r = simular(caso, catalogo, ia, config, redactar)
    return {'id': caso['id'], 'rep': rep, **calificar(caso, r), 'tipos_caso': r['expediente'].get('tipos_caso'),
            'expediente': r['expediente'].get('datos'), 'no_sabe': r['expediente'].get('no_sabe'),
            'reglas': r['salida'].get('reglas'), 'inciertas': r['salida'].get('inciertas'),
            'preguntas': r['preguntas'], 'complementarios': r['complementarios'], 'lista_hechos': r['expediente'].get('hechos', []),
            'conversacion': r['conversacion'], 'segundos': r['segundos']}


def resumen(filas: list[dict]) -> dict:
    n = len(filas)
    datos = Counter(v.split(' ')[0] for x in filas for v in x['datos'].values())
    por_dato = Counter(k for x in filas for k, v in x['datos'].items() if v != 'acierta')
    return {'casos': n, 'orienta': sum(x['orienta'] for x in filas), 'tipos': sum(x['tipos'] for x in filas),
            'datos_acierta': datos['acierta'], 'datos_total': sum(datos.values()),
            'datos_falta': datos['falta'], 'datos_equivocado': datos['equivocado'],
            'hechos_conservados': sum(v for x in filas for v in x.get('hechos', {}).values()),
            'hechos_total': sum(len(x.get('hechos', {})) for x in filas),
            'reglas': sum(not x['reglas_faltan'] and not x['reglas_de_mas'] for x in filas),
            'preguntas_promedio': round(sum(x['n_preguntas'] for x in filas) / max(n, 1), 2),
            'preguntas_de_mas': sum(bool(x['preguntas_de_mas']) for x in filas),
            'segundos': round(sum(x['segundos'] for x in filas), 1),
            'datos_con_error': dict(por_dato.most_common())}


def validar_casos(texto: str) -> list[dict]:
    try:
        d = yaml.safe_load(texto)
    except yaml.YAMLError as e:
        raise ValueError(f'YAML inválido: {e}')
    casos = (d or {}).get('casos') if isinstance(d, dict) else None
    if not isinstance(casos, list) or not casos:
        raise ValueError('Falta la lista «casos».')
    ids = set()
    for c in casos:
        if not isinstance(c, dict) or not c.get('id') or not c.get('relato') or not isinstance(c.get('esperado'), dict):
            raise ValueError(f'Cada caso necesita id, relato y esperado: {str(c)[:80]}')
        if c['id'] in ids:
            raise ValueError(f'id repetido: {c["id"]}')
        ids.add(c['id'])
    return casos


def _commit() -> str:
    try:
        return subprocess.run(['git', '-C', str(REPO), 'rev-parse', '--short', 'HEAD'], capture_output=True,
                              text=True, timeout=5).stdout.strip()
    except Exception:
        return ''


class BenchConsulta:
    def __init__(self, *, connect: Callable, catalogo: Callable, ia, current_email: Callable, can_run: Callable,
                 redactar: Callable | None = None):
        """`catalogo()` → el doc del catálogo de la base; `ia`: ConsultaIA con el LLM de la app; `redactar(mensajes) → str`:
        la de Preguntar (Catálogo), para las corridas con preguntas redactadas por el LLM."""
        self.connect, self.catalogo, self.ia = connect, catalogo, ia
        self.redactar = redactar
        self.current_email, self.can_run = current_email, can_run
        self._lock = threading.Lock()
        self._corriendo: int | None = None
        with connect() as c, c.cursor() as cur:
            cur.execute(SCHEMA)
            cur.execute(_STALE_SQL)
            cur.execute('SELECT 1 FROM bench_consulta_casos WHERE id = 1')
            if not cur.fetchone() and CASOS_INICIALES.exists():
                cur.execute("INSERT INTO bench_consulta_casos (id, yaml, actualizado_por) VALUES (1, %s, 'casos.yaml')",
                            (CASOS_INICIALES.read_text(),))
            c.commit()
        self.router = self._make_router()

    def casos_yaml(self) -> str:
        with self.connect() as c, c.cursor() as cur:
            cur.execute('SELECT yaml FROM bench_consulta_casos WHERE id = 1')
            row = cur.fetchone()
        return row[0] if row else 'casos: []\n'

    def guardar_casos(self, texto: str, email: str) -> int:
        n = len(validar_casos(texto))
        with self.connect() as c, c.cursor() as cur:
            cur.execute("INSERT INTO bench_consulta_casos (id, yaml, actualizado_por) VALUES (1, %s, %s) "
                        "ON CONFLICT (id) DO UPDATE SET yaml = EXCLUDED.yaml, actualizado_por = EXCLUDED.actualizado_por, "
                        "updated_at = now()", (texto, email))
            c.commit()
        return n

    def corridas(self) -> list[dict]:
        with self.connect() as c, c.cursor() as cur:
            cur.execute('SELECT id, creada, por, catalogo_md5, commit, estado, config, resumen, error FROM bench_consulta_corridas '
                        'ORDER BY id DESC LIMIT 100')
            cols = [d.name for d in cur.description]
            return [{**dict(zip(cols, row)), 'creada': row[1].isoformat()} for row in cur.fetchall()]

    def corrida(self, cid: int) -> dict:
        with self.connect() as c, c.cursor() as cur:
            cur.execute('SELECT filas FROM bench_consulta_corridas WHERE id = %s', (cid,))
            row = cur.fetchone()
        if not row:
            raise ValueError('Esa corrida no existe.')
        return {'filas': row[0] or []}

    def correr(self, email: str, ids: list[str] | None = None, config: dict | None = None) -> int:
        config = {**CONFIG, **{k: v for k, v in (config or {}).items() if k in CONFIG}}
        if config['preguntas'] not in ('catalogo', 'llm') or config['reglas'] not in ('todas', 'confirmadas'):
            raise ValueError(f'Configuración no válida: {config}')
        config['repeticiones'] = max(1, min(10, int(config.get('repeticiones') or 1)))
        casos = validar_casos(self.casos_yaml())
        if ids:
            casos = [c for c in casos if c['id'] in ids]
        with self._lock:
            if self._corriendo:
                raise RuntimeError(f'Ya hay una corrida en curso (#{self._corriendo}).')
            catalogo = self.catalogo()
            with self.connect() as c, c.cursor() as cur:
                cur.execute('INSERT INTO bench_consulta_corridas (por, catalogo_md5, commit, config) VALUES (%s, %s, %s, %s::jsonb) '
                            'RETURNING id', (email, md5_de(catalogo)[:8], _commit(), json.dumps(config)))
                cid = cur.fetchone()[0]
                c.commit()
            self._corriendo = cid
        threading.Thread(target=self._correr, args=(cid, casos, catalogo, config), daemon=True).start()
        return cid

    def _correr(self, cid: int, casos: list[dict], catalogo: dict, config: dict):
        filas, error = [], None
        try:
            for rep in range(1, config['repeticiones'] + 1):
                for caso in casos:
                    filas.append(fila(caso, catalogo, self.ia, config, self.redactar, rep))
                    with self.connect() as c, c.cursor() as cur:   # se ve el avance mientras corre
                        cur.execute('UPDATE bench_consulta_corridas SET filas = %s::jsonb, resumen = %s::jsonb WHERE id = %s',
                                    (json.dumps(filas, ensure_ascii=False), json.dumps(resumen(filas)), cid))
                        c.commit()
        except Exception as e:   # noqa: BLE001 — la corrida queda marcada con el error
            error = f'{type(e).__name__}: {e}'
        finally:
            with self.connect() as c, c.cursor() as cur:
                cur.execute("UPDATE bench_consulta_corridas SET estado = %s, error = %s WHERE id = %s",
                            ('error' if error else 'terminada', error, cid))
                c.commit()
            self._corriendo = None

    def _make_router(self) -> APIRouter:
        r = APIRouter(prefix='/api/bench_consulta')

        def deny():
            return JSONResponse({'error': 'Solo administradores.'}, status_code=403)

        def bad(msg):
            return JSONResponse({'error': msg}, status_code=400)

        @r.get('')
        def inicio(request: Request):
            if not self.can_run(self.current_email(request)):
                return deny()
            return {'casos_yaml': self.casos_yaml(), 'corridas': self.corridas(), 'en_curso': self._corriendo}

        @r.get('/corridas/{cid}')
        def corrida(cid: int, request: Request):
            if not self.can_run(self.current_email(request)):
                return deny()
            try:
                return self.corrida(cid)
            except ValueError as e:
                return bad(str(e))

        @r.put('/casos')
        async def casos(request: Request):
            email = self.current_email(request)
            if not self.can_run(email):
                return deny()
            try:
                return {'casos': self.guardar_casos((await request.body()).decode(), email)}
            except ValueError as e:
                return bad(str(e))

        @r.post('/correr')
        async def correr(request: Request):
            email = self.current_email(request)
            if not self.can_run(email):
                return deny()
            try:
                b = await request.json()
            except Exception:
                b = {}
            try:
                return {'corrida': self.correr(email, b.get('casos'), b.get('config'))}
            except (RuntimeError, ValueError) as e:
                return bad(str(e))

        return r
