"""Pruebas por componente (🧪 Benchmark → 🧩 Componentes).

El benchmark normal mide el sistema completo: si el score baja, no se sabe qué pieza falló. Aquí se prueba UNA llamada
al LLM contra su propio objetivo, con casos «entrada → salida esperada» y sin juez:

  filtro       ¿detecta el estado de los hechos, el tipo de asunto, si es teórica?   (jurisdiction_gate.extraer_lugares)
  descomponer  ¿divide solo las preguntas que comparan, en las entidades correctas?  (llm.decompose)
  por_delito   ¿encuentra cada conducta del relato, sin nombrar estados?             (main.decompose_conducts)
  hyde         ¿el borrador respeta sus reglas (sin número de artículo, sin estados ajenos)?

Cada corrida guarda el md5 del prompt que probó, para ver si un cambio de prompt mejora o empeora su prueba.
Los casos viven en la base (comp_casos); los iniciales se cargan de componentes_casos.json solo si el componente no
tiene casos. Las funciones que llaman al LLM se inyectan desde main.py (`runners`), como en bench.Bench.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from shared.code_routes import codes_in, fold

COMPONENTES = {
    'filtro': {'nombre': 'Filtro por estado', 'icono': '🚧',
               'objetivo': 'Detectar el estado donde ocurrieron los hechos (y distinguirlo de donde la persona vive o '
                           'trabaja), el tipo de asunto y si la pregunta es teórica.'},
    'descomponer': {'nombre': 'Descomponer', 'icono': '🧩',
                    'objetivo': 'Dividir solo las preguntas que comparan dos o más entidades, una búsqueda por entidad; '
                                'devolver sin dividir las que no comparan (aunque pregunten varios aspectos).'},
    'por_delito': {'nombre': 'Descomponer por delito', 'icono': '⚖️',
                   'objetivo': 'Escribir una búsqueda por cada conducta del relato que pueda ser delito, sin inventar '
                               'conductas y sin nombrar estados ni códigos.'},
    'desc_solo_lugar': {'nombre': 'Descomponer · solo por lugar', 'icono': '🧩',
                        'objetivo': 'Versión del prompt que divide SOLO las preguntas que comparan estados, códigos o '
                                    'conceptos; las que hacen varias preguntas sobre lo mismo quedan enteras.'},
    'desc_solo_pregunta': {'nombre': 'Descomponer · solo por pregunta', 'icono': '🧩',
                           'objetivo': 'Versión del prompt que divide SOLO los mensajes con varias preguntas («¿es '
                                       'delito y cuánta cárcel le dan?»), una búsqueda por pregunta; no divide por estado.'},
    'desc_lugar_y_pregunta': {'nombre': 'Descomponer · por lugar y por pregunta', 'icono': '🧩',
                              'objetivo': 'Versión del prompt que divide las comparaciones (por lugar) y los mensajes '
                                          'con varias preguntas (por pregunta).'},
    'desc_libre': {'nombre': 'Descomponer · libre', 'icono': '🧩',
                   'objetivo': 'Versión del prompt en la que el LLM decide cómo dividir. Solo se revisan sus reglas: '
                               'máximo 4 búsquedas y sin nombrar estados que la pregunta no nombra.'},
    'desc_libre_corto': {'nombre': 'Descomponer · libre (prompt mínimo)', 'icono': '🧩',
                         'objetivo': 'Como «libre», con un prompt de una línea. Solo se revisan sus reglas.'},
    'desc_libre_max2': {'nombre': 'Descomponer · libre, máximo 2', 'icono': '🧩',
                        'objetivo': 'Como «libre», pero con máximo 2 búsquedas (más rápido). Solo se revisan sus reglas.'},
    'division_recall': {'nombre': 'División: recall', 'icono': '🎯',
                        'objetivo': 'Para cada pregunta con artículos esperados (sets 3 y 14): cuántos salen entre los '
                                    '10 primeros resultados del buscador con cada forma de dividir (sin dividir, solo '
                                    'por lugar, solo por pregunta, solo por delito, combinaciones, libre). Decide qué '
                                    'versión ayuda más al buscador.', 'efecto': True},
    'hyde_recall': {'nombre': 'HyDE: recall', 'icono': '🎯',
                    'objetivo': 'Para cada pregunta con artículos esperados (sets 3, 13 y 14): cuántos salen entre los 10 '
                                'primeros resultados del buscador con y sin HyDE.', 'efecto': True},
    'hyde': {'nombre': 'HyDE', 'icono': '🧪',
             'objetivo': 'Escribir un borrador del artículo que respondería, sin inventar números de artículo y sin '
                         'nombrar estados que la pregunta no nombra.'},
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS comp_casos (
    id serial PRIMARY KEY, componente text NOT NULL, entrada text NOT NULL, esperado jsonb NOT NULL,
    fuente text, nota text, revisado boolean NOT NULL DEFAULT false, creado_por text,
    created_at timestamptz DEFAULT now(), updated_at timestamptz DEFAULT now());
CREATE INDEX IF NOT EXISTS comp_casos_c ON comp_casos (componente, id);
CREATE TABLE IF NOT EXISTS comp_corridas (
    id serial PRIMARY KEY, componente text NOT NULL, prompt_md5 text, prompt text, status text NOT NULL DEFAULT 'running',
    n int NOT NULL DEFAULT 0, done int NOT NULL DEFAULT 0, metricas jsonb, error text, creado_por text,
    created_at timestamptz DEFAULT now(), finished_at timestamptz);
CREATE INDEX IF NOT EXISTS comp_corridas_c ON comp_corridas (componente, id);
CREATE TABLE IF NOT EXISTS comp_resultados (
    id serial PRIMARY KEY, corrida_id int NOT NULL REFERENCES comp_corridas(id) ON DELETE CASCADE,
    caso_id int, entrada text, esperado jsonb, salida jsonb, ok boolean, detalle jsonb, segundos real, error text);
CREATE INDEX IF NOT EXISTS comp_resultados_c ON comp_resultados (corrida_id, id);
"""
# Una corrida que quedó 'running' tras un reinicio de la app nunca terminará.
_STALE_SQL = "UPDATE comp_corridas SET status = 'interrumpida', finished_at = now() WHERE status = 'running'"

CASOS_INICIALES = Path(__file__).resolve().parent / 'componentes_casos.json'
# Costo y efecto de cada opción en los benchmarks (comparaciones pareadas ya hechas, con su fuente). Se actualiza a mano.
EFECTOS = Path(__file__).resolve().parent / 'componentes_efectos.json'

# Estados del corpus como los nombra code_routes (codes_in → 'label'); los demás labels son leyes (CPF, CNPP…).
ESTATALES = {'CDMX', 'CPEM', 'Morelos', 'Querétaro'}
ART_RE = re.compile(r'(?i)\bart[íi]culos?\s+\d+|\bart\.\s*\d+')


CONCEPTOS_RE = re.compile(r'(?i)diferencias?\s+(hay\s+)?entre|distingue|\bvs\.?\b|frente\s+a')
_OTRA_PREGUNTA = re.compile(r'(?i)[,;]?\s+(?:y|o)\s+(?:qu[eé]|cu[aá]nt\w*|c[oó]mo|d[oó]nde|qui[eé]n\w*|cu[aá]l\w*|ante\s+qui[eé]n|si\s)')


def contar_preguntas(texto: str) -> int:
    """Cuántas preguntas hace el mensaje: cada «¿…?» cuenta una, más cada «… y qué/cuánto/cómo…» dentro de ella
    («¿Es delito y cuánta cárcel le dan?» = 2). Aproximado: las etiquetas generadas así quedan como no revisadas."""
    partes = re.findall(r'¿[^?]*\?', texto or '') or [texto or '']
    return sum(1 + len(_OTRA_PREGUNTA.findall(p)) for p in partes)


def compara(texto: str) -> bool:
    """¿La pregunta compara? Nombra 2+ códigos o estados (la regex del routing) o dice «diferencia entre / vs»."""
    return len({h['label'] for h in codes_in(texto or '')}) >= 2 or bool(CONCEPTOS_RE.search(texto or ''))


def tipos_pregunta(texto: str, conductas: int = 0) -> list[str]:
    """Tipos para separar los resultados de la prueba de recall (una pregunta puede tener varios)."""
    t = (['comparativa'] if compara(texto) else []) + (['varias preguntas'] if contar_preguntas(texto) >= 2 else [])
    return t + (['varias conductas'] if conductas >= 2 else [])


def md5(texto: str | None) -> str:
    return hashlib.md5((texto or '').encode()).hexdigest()


# ── Evaluadores: (esperado, salida) → (ok, detalle). Puros: se prueban sin LLM (tests/test_componentes.py) ────────
def eval_filtro(esp: dict, sal: dict) -> tuple[bool, dict]:
    """`esp` trae solo los campos que el caso prueba: estados (todos los mencionados), hechos/otros (por papel),
    depende (del estado), federal (delito federal), teorica."""
    lug = [x for x in sal.get('lugares') or [] if x.get('estado')]
    obtenido = {
        'estados': sorted({x['estado'] for x in lug}),
        'hechos': sorted({x['estado'] for x in lug if x.get('rol', 'hechos') == 'hechos'}),
        'otros': sorted({x['estado'] for x in lug if x.get('rol') == 'otro'} - {x['estado'] for x in lug if x.get('rol', 'hechos') == 'hechos'}),
        'depende': bool(sal.get('depende_del_estado')), 'federal': bool(sal.get('delito_federal')),
        'teorica': bool(sal.get('teorica')),
    }
    fallas = []
    for k, v in esp.items():
        got = obtenido.get(k)
        if (sorted(v) if isinstance(v, list) else v) != got:
            fallas.append(k)
    return not fallas, {'obtenido': {k: obtenido[k] for k in esp if k in obtenido}, 'fallas': fallas,
                        'tipo': sal.get('tipo')}


def _menciona(entidad: str, texto: str) -> bool:
    """¿La sub-búsqueda nombra la entidad? Con codes_in para códigos y estados (CDMX = Ciudad de México = DF…) y, si
    no, por texto plano (conceptos: «estupro»)."""
    if entidad in {h['label'] for h in codes_in(texto)}:
        return True
    return fold(entidad) in fold(texto)


def eval_descomponer(esp: dict, sal: list[str]) -> tuple[bool, dict]:
    """esp = {'compara': bool, 'entidades': [...] opcional}. No comparativa → una sola búsqueda. Comparativa → al menos
    dos búsquedas (máximo 4) y cada entidad esperada nombrada en alguna. Si sobran búsquedas (p. ej. «qué es» + una por
    estado) se anota como advertencia, no como fallo: lo grave es dividir lo que no compara o dejar fuera una entidad."""
    n = len(sal)
    if not esp.get('compara'):
        return n == 1, {'busquedas': n, 'falla': None if n == 1 else 'dividió una pregunta que no compara'}
    ents = esp.get('entidades') or []
    faltan = [e for e in ents if not any(_menciona(e, s) for s in sal)]
    if n < 2:
        return False, {'busquedas': n, 'falla': 'no dividió una pregunta que compara'}
    if faltan:
        return False, {'busquedas': n, 'faltan': faltan, 'falla': f'ninguna búsqueda nombra {", ".join(faltan)}'}
    if n > 4:
        return False, {'busquedas': n, 'falla': 'más de 4 búsquedas'}
    aviso = f'{n} búsquedas para {len(ents)} entidades' if ents and n != len(ents) else None
    return True, {'busquedas': n, 'aviso': aviso}


def _division_esperada(regla: str, esp: dict) -> bool:
    """¿Debe dividirse según la regla de la versión? esp: compara (por lugar) y preguntas (cuántas hace el mensaje)."""
    lugar, pregunta = bool(esp.get('compara')), (esp.get('preguntas') or 1) >= 2
    return {'solo_lugar': lugar, 'solo_pregunta': pregunta, 'lugar_y_pregunta': lugar or pregunta}[regla]


def eval_division(regla: str):
    """Evaluador de obediencia de una versión del prompt de descomponer: divide solo cuando su regla lo pide; si
    divide por lugar, nombra cada entidad esperada; máximo 4 búsquedas. 'libre' no tiene salida esperada: solo se
    revisan sus reglas (máximo 4, sin estados que la pregunta no nombra)."""
    def evaluar(esp: dict, sal: list[str]) -> tuple[bool, dict]:
        n, tope = len(sal), 2 if regla == 'libre_max2' else 4
        if n > tope:
            return False, {'busquedas': n, 'falla': f'más de {tope} búsquedas'}
        if regla.startswith('libre'):
            ajenos = sorted({h['label'] for s in sal for h in codes_in(s)} - set(esp.get('nombrados') or []))
            return not ajenos, {'busquedas': n, 'falla': ('nombra ' + ', '.join(ajenos)) if ajenos else None}
        if not _division_esperada(regla, esp):
            return n == 1, {'busquedas': n, 'falla': None if n == 1 else 'dividió algo que su regla no pide dividir'}
        if n < 2:
            return False, {'busquedas': n, 'falla': 'no dividió algo que su regla pide dividir'}
        if regla != 'solo_pregunta' and esp.get('compara'):
            faltan = [e for e in esp.get('entidades') or [] if not any(_menciona(e, s) for s in sal)]
            if faltan:
                return False, {'busquedas': n, 'faltan': faltan, 'falla': f'ninguna búsqueda nombra {", ".join(faltan)}'}
        return True, {'busquedas': n}
    return evaluar


def eval_recall(esp: dict, sal: dict) -> tuple[bool, dict]:
    """La prueba de recall no tiene «aprobado»: lo que importa son los conteos por versión (ver metricas)."""
    return True, {'gold': sal.get('gold'), 'aciertos': sal.get('aciertos')}


def eval_por_delito(esp: dict, sal: list[str]) -> tuple[bool, dict]:
    """esp = {'conductas': [[raíces alternativas], …]}: cada conducta debe aparecer en alguna búsqueda (por cualquiera
    de sus raíces), máximo 4 búsquedas, y ninguna nombra un estado o código. Si el número de búsquedas no coincide con
    el de conductas, se anota como advertencia (dos búsquedas para la misma conducta no hacen daño)."""
    cond = esp.get('conductas') or []
    halladas = [any(any(fold(r) in fold(s) for r in alts) for s in sal) for alts in cond]
    estados = sorted({h['label'] for s in sal for h in codes_in(s)})
    fallas = []
    if not all(halladas):
        fallas.append('falta: ' + ', '.join(alts[0] for alts, h in zip(cond, halladas) if not h))
    if len(sal) > 4:
        fallas.append('más de 4 búsquedas')
    if estados:
        fallas.append('nombra ' + ', '.join(estados))
    aviso = f'{len(sal)} búsquedas para {len(cond)} conductas' if len(sal) != len(cond) else None
    return not fallas, {'busquedas': len(sal), 'conductas_halladas': sum(halladas), 'conductas': len(cond),
                        'fallas': fallas, 'aviso': aviso}


def eval_hyde(esp: dict, sal: str) -> tuple[bool, dict]:
    """El borrador no trae números de artículo ni nombra estados que la pregunta no nombra (esp['permitidos'])."""
    articulo = bool(ART_RE.search(sal or ''))
    ajenos = sorted({h['label'] for h in codes_in(sal or '')} & ESTATALES - set(esp.get('permitidos') or []))
    fallas = (['trae número de artículo'] if articulo else []) + (['nombra ' + ', '.join(ajenos)] if ajenos else [])
    return not fallas, {'fallas': fallas, 'palabras': len((sal or '').split())}


EVALUADORES = {'filtro': eval_filtro, 'descomponer': eval_descomponer, 'por_delito': eval_por_delito, 'hyde': eval_hyde,
               'desc_solo_lugar': eval_division('solo_lugar'), 'desc_solo_pregunta': eval_division('solo_pregunta'),
               'desc_lugar_y_pregunta': eval_division('lugar_y_pregunta'), 'desc_libre': eval_division('libre'),
               'desc_libre_corto': eval_division('libre_corto'), 'desc_libre_max2': eval_division('libre_max2'),
               'division_recall': eval_recall, 'hyde_recall': eval_recall}

# Formas de dividir que compara la prueba de recall: (descomponer, descomponer por delito). descomponer = False, True
# (prompt actual) o el nombre de una versión del prompt (shared/llm_client.DECOMPOSE_VARIANTES).
VERSIONES_DIVISION = {
    'sin dividir': (False, False), 'solo por lugar': ('solo_lugar', False), 'solo por pregunta': ('solo_pregunta', False),
    'solo por delito': (False, True), 'por lugar y por pregunta': ('lugar_y_pregunta', False),
    'por lugar y por delito (actual)': (True, True), 'libre': ('libre', False),
    'libre (prompt mínimo)': ('libre_corto', False), 'libre, máximo 2': ('libre_max2', False),
}


def metricas(componente: str, filas: list[dict]) -> dict:
    """Aciertos totales y, donde aplica, por tipo de caso (para descomponer: comparativas vs no comparativas)."""
    ok = [f for f in filas if not f.get('error')]
    if componente in ('division_recall', 'hyde_recall'):
        return metricas_recall(filas)
    out = {'n': len(filas), 'errores': len(filas) - len(ok), 'aciertos': sum(f['ok'] for f in ok),
           'tasa': round(sum(f['ok'] for f in ok) / len(ok), 4) if ok else None}
    grupos: dict[str, list[bool]] = {}
    for f in ok:
        g = grupo(componente, f['esperado'])
        if g:
            grupos.setdefault(g, []).append(f['ok'])
    if grupos:
        out['por_grupo'] = {g: {'aciertos': sum(v), 'n': len(v)} for g, v in sorted(grupos.items())}
    segs = [f['segundos'] for f in ok if f.get('segundos') is not None]
    if segs:
        out['segundos_media'] = round(sum(segs) / len(segs), 2)
    return out


def metricas_recall(filas: list[dict]) -> dict:
    """Por versión: artículos esperados entre los 10 primeros resultados ÷ artículos esperados en el corpus, en total,
    por set («set 3») y por tipo de pregunta (una pregunta puede ser de varios tipos)."""
    ok = [f for f in filas if not f.get('error') and f.get('salida')]
    tot: dict[str, dict] = {}
    for f in ok:
        sal = f['salida']
        tipos = ['todas'] + (sal.get('tipos') or ['otra'])
        for v, h in (sal.get('aciertos') or {}).items():
            for t in tipos:
                c = tot.setdefault(v, {}).setdefault(t, {'aciertos': 0, 'gold': 0, 'preguntas': 0})
                c['aciertos'] += h; c['gold'] += sal.get('gold') or 0; c['preguntas'] += 1
    por_version = {v: {t: {**c, 'recall': round(c['aciertos'] / c['gold'], 4) if c['gold'] else None}
                       for t, c in ts.items()} for v, ts in tot.items()}
    # Tiempo de la búsqueda completa de cada versión (HyDE + división + búsquedas): media y desviación estándar.
    for v in por_version:
        ts = [f['salida']['segundos'][v] for f in ok if v in (f['salida'].get('segundos') or {})]
        if ts:
            media = sum(ts) / len(ts)
            por_version[v]['segundos'] = {'media': round(media, 2), 'de': round((sum((x - media) ** 2 for x in ts) / len(ts)) ** 0.5, 2)}
    segs = [f['segundos'] for f in ok if f.get('segundos') is not None]
    return {'n': len(filas), 'errores': len(filas) - len(ok), 'por_version': por_version,
            'segundos_media': round(sum(segs) / len(segs), 2) if segs else None}


def grupo(componente: str, esp: dict) -> str | None:
    if componente == 'descomponer':
        return 'comparativas' if esp.get('compara') else 'no comparativas'
    if componente.startswith('desc_') and not componente.startswith('desc_libre'):
        return 'debe dividir' if _division_esperada(componente[5:], esp) else 'no debe dividir'
    if componente == 'filtro':
        return ('papel del lugar' if 'hechos' in esp or 'otros' in esp else 'estados' if 'estados' in esp
                else 'teórica' if 'teorica' in esp else 'tipo de asunto')
    return None


class Componentes:
    """Estado de las pruebas por componente y su `router` (se monta en main.py).
    runners: componente → función(entrada) → salida del LLM. prompts: componente → función() → texto del prompt."""

    def __init__(self, *, connect: Callable, runners: dict[str, Callable], prompts: dict[str, Callable],
                 current_email: Callable, can_run: Callable):
        self.connect, self.runners, self.prompts = connect, runners, prompts
        self.current_email, self.can_run = current_email, can_run
        self._lock = threading.Lock()
        self._running: dict[str, int] = {}   # componente → corrida en curso (una por componente)
        with connect() as c, c.cursor() as cur:
            cur.execute(SCHEMA)
            cur.execute(_STALE_SQL)
            self._sembrar(cur)
            c.commit()
        self.router = self._make_router()

    def _sembrar(self, cur) -> None:
        """Carga los casos iniciales de un componente solo si todavía no tiene ninguno."""
        if not CASOS_INICIALES.exists():
            return
        datos = json.loads(CASOS_INICIALES.read_text())
        for comp, casos in datos.items():
            cur.execute("SELECT 1 FROM comp_casos WHERE componente = %s LIMIT 1", (comp,))
            if cur.fetchone():
                continue
            for k in casos:
                cur.execute("INSERT INTO comp_casos (componente, entrada, esperado, fuente, nota, revisado, creado_por) "
                            "VALUES (%s, %s, %s::jsonb, %s, %s, %s, 'casos iniciales')",
                            (comp, k['entrada'], json.dumps(k['esperado'], ensure_ascii=False), k.get('fuente'),
                             k.get('nota'), bool(k.get('revisado'))))

    # ── lectura ───────────────────────────────────────────────────────────────────
    def resumen(self) -> list[dict]:
        out = []
        with self.connect() as c, c.cursor() as cur:
            for comp, meta in COMPONENTES.items():
                cur.execute("SELECT count(*), count(*) FILTER (WHERE revisado) FROM comp_casos WHERE componente = %s", (comp,))
                n, rev = cur.fetchone()
                cur.execute("SELECT id, prompt_md5, status, metricas, created_at::text FROM comp_corridas "
                            "WHERE componente = %s ORDER BY id DESC LIMIT 1", (comp,))
                ult = cur.fetchone()
                texto = self._prompt(comp)
                out.append({'id': comp, **meta, 'casos': n, 'revisados': rev, 'prompt_md5': md5(texto),
                            'prompt': texto, 'corriendo': self._running.get(comp),
                            'ultima': dict(zip(['id', 'prompt_md5', 'status', 'metricas', 'fecha'], ult)) if ult else None})
        return out

    def _prompt(self, comp: str) -> str:
        try:
            return self.prompts[comp]() or ''
        except Exception:  # noqa: BLE001 — sin prompt la página sigue
            return ''

    def casos(self, comp: str) -> list[dict]:
        with self.connect() as c, c.cursor() as cur:
            cur.execute("SELECT id, entrada, esperado, fuente, nota, revisado FROM comp_casos WHERE componente = %s "
                        "ORDER BY id", (comp,))
            return [dict(zip(['id', 'entrada', 'esperado', 'fuente', 'nota', 'revisado'], r)) for r in cur.fetchall()]

    def corridas(self, comp: str) -> list[dict]:
        with self.connect() as c, c.cursor() as cur:
            cur.execute("SELECT id, prompt_md5, status, n, done, metricas, error, creado_por, created_at::text, "
                        "finished_at::text FROM comp_corridas WHERE componente = %s ORDER BY id DESC LIMIT 50", (comp,))
            cols = ['id', 'prompt_md5', 'status', 'n', 'done', 'metricas', 'error', 'creado_por', 'fecha', 'fin']
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    def resultados(self, rid: int) -> list[dict]:
        with self.connect() as c, c.cursor() as cur:
            cur.execute("SELECT caso_id, entrada, esperado, salida, ok, detalle, segundos, error FROM comp_resultados "
                        "WHERE corrida_id = %s ORDER BY ok NULLS FIRST, id", (rid,))
            cols = ['caso_id', 'entrada', 'esperado', 'salida', 'ok', 'detalle', 'segundos', 'error']
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    # ── escritura ─────────────────────────────────────────────────────────────────
    def guardar_casos(self, comp: str, casos: list[dict], email: str | None) -> int:
        """Reemplaza los casos del componente (el JSON completo que edita la página). Las corridas viejas guardan su
        propia copia de la entrada y lo esperado, así que no se pierden."""
        limpios = []
        for k in casos:
            if not isinstance(k, dict) or not str(k.get('entrada') or '').strip() or not isinstance(k.get('esperado'), dict):
                raise ValueError('cada caso necesita "entrada" (texto) y "esperado" (objeto)')
            limpios.append(k)
        with self.connect() as c, c.cursor() as cur:
            cur.execute("DELETE FROM comp_casos WHERE componente = %s", (comp,))
            for k in limpios:
                cur.execute("INSERT INTO comp_casos (componente, entrada, esperado, fuente, nota, revisado, creado_por) "
                            "VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s)",
                            (comp, k['entrada'].strip(), json.dumps(k['esperado'], ensure_ascii=False), k.get('fuente'),
                             k.get('nota'), bool(k.get('revisado')), email))
            c.commit()
        return len(limpios)

    def correr(self, comp: str, email: str | None) -> int:
        with self._lock:
            if comp in self._running:
                raise RuntimeError(f'Ya hay una prueba de este componente en curso (#{self._running[comp]}).')
            casos = self.casos(comp)
            if not casos:
                raise ValueError('este componente no tiene casos')
            texto = self._prompt(comp)
            with self.connect() as c, c.cursor() as cur:
                cur.execute("INSERT INTO comp_corridas (componente, prompt_md5, prompt, n, creado_por) VALUES "
                            "(%s, %s, %s, %s, %s) RETURNING id", (comp, md5(texto), texto, len(casos), email))
                rid = cur.fetchone()[0]
                c.commit()
            self._running[comp] = rid
        threading.Thread(target=self._correr, args=(comp, rid, casos), daemon=True).start()
        return rid

    def _correr(self, comp: str, rid: int, casos: list[dict]) -> None:
        filas, error = [], None
        try:
            for k in casos:
                t0, fila = time.time(), {'caso_id': k['id'], 'entrada': k['entrada'], 'esperado': k['esperado'],
                                         'salida': None, 'ok': None, 'detalle': None, 'error': None}
                try:
                    fila['salida'] = self.runners[comp](k['entrada'])
                    fila['ok'], fila['detalle'] = EVALUADORES[comp](k['esperado'], fila['salida'])
                except Exception as e:  # noqa: BLE001 — un caso que falla no tumba la corrida
                    fila['error'] = f'{type(e).__name__}: {e}'
                fila['segundos'] = round(time.time() - t0, 2)
                filas.append(fila)
                with self.connect() as c, c.cursor() as cur:
                    cur.execute("INSERT INTO comp_resultados (corrida_id, caso_id, entrada, esperado, salida, ok, detalle, "
                                "segundos, error) VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s, %s::jsonb, %s, %s)",
                                (rid, fila['caso_id'], fila['entrada'], json.dumps(fila['esperado'], ensure_ascii=False),
                                 json.dumps(fila['salida'], ensure_ascii=False), fila['ok'],
                                 json.dumps(fila['detalle'], ensure_ascii=False), fila['segundos'], fila['error']))
                    cur.execute("UPDATE comp_corridas SET done = done + 1 WHERE id = %s", (rid,))
                    c.commit()
        except Exception as e:  # noqa: BLE001
            error = f'{type(e).__name__}: {e}'
        finally:
            with self.connect() as c, c.cursor() as cur:
                cur.execute("UPDATE comp_corridas SET status = %s, metricas = %s::jsonb, error = %s, finished_at = now() "
                            "WHERE id = %s", ('error' if error else 'done', json.dumps(metricas(comp, filas)), error, rid))
                c.commit()
            self._running.pop(comp, None)

    # ── rutas ─────────────────────────────────────────────────────────────────────
    def _make_router(self) -> APIRouter:
        r = APIRouter(prefix='/api/componentes')

        def deny(msg='Solo los administradores pueden correr o editar pruebas.'):
            return JSONResponse({'error': msg}, status_code=403)

        def bad(msg):
            return JSONResponse({'error': msg}, status_code=400)

        def valido(comp):
            return comp in COMPONENTES

        @r.get('')
        def lista(request: Request):
            if not self.can_run(self.current_email(request)):
                return deny('Solo los administradores pueden ver las pruebas por componente.')
            return self.resumen()

        @r.get('/efectos')
        def efectos(request: Request):
            if not self.can_run(self.current_email(request)):
                return deny()
            return json.loads(EFECTOS.read_text()) if EFECTOS.exists() else {'opciones': []}

        @r.get('/{comp}/casos')
        def casos(comp: str, request: Request):
            if not self.can_run(self.current_email(request)):
                return deny()
            return self.casos(comp) if valido(comp) else bad('componente desconocido')

        @r.put('/{comp}/casos')
        async def guardar(comp: str, request: Request):
            email = self.current_email(request)
            if not self.can_run(email):
                return deny()
            if not valido(comp):
                return bad('componente desconocido')
            try:
                return {'casos': self.guardar_casos(comp, await request.json(), email)}
            except (ValueError, TypeError) as e:
                return bad(str(e))

        @r.post('/{comp}/correr')
        def correr(comp: str, request: Request):
            email = self.current_email(request)
            if not self.can_run(email):
                return deny()
            if not valido(comp):
                return bad('componente desconocido')
            try:
                return {'corrida': self.correr(comp, email)}
            except (RuntimeError, ValueError) as e:
                return bad(str(e))

        @r.get('/{comp}/corridas')
        def corridas(comp: str, request: Request):
            if not self.can_run(self.current_email(request)):
                return deny()
            return self.corridas(comp) if valido(comp) else bad('componente desconocido')

        @r.get('/corridas/{rid}')
        def resultados(rid: int, request: Request):
            if not self.can_run(self.current_email(request)):
                return deny()
            return self.resultados(rid)

        return r
