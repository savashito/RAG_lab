"""
apps/rewrite_lab/bench.py — tab "🧪 Benchmark": evalúa la RESPUESTA del LLM (no solo el
retrieval, que ya mide el Rewrite Lab).

Modelo de datos (Postgres, porque se edita desde la UI y se filtra):
  bench_sets        conjunto de preguntas de un tema (topic)
  bench_questions   pregunta + respuesta de referencia opcional + notas
  bench_components  lo que la respuesta DEBE contener: texto + tipo + peso
                      must      — obligatorio (define si la pregunta "pasa")
                      should    — deseable (suma al score, no reprueba)
                      must_not  — no debe aparecer (alucinación, cita inventada…)
  bench_runs        una corrida: config (método, k, HyDE, rerank, prompt), métricas,
                    y la llave del artefacto en el object store
  bench_results     por pregunta: score, pasa/no, veredicto por componente (snapshot)
  bench_reviews     revisión HUMANA de un resultado (una por revisor): veredicto por
                    componente, calificación 1–5 y comentario. Sirve para evaluar las
                    respuestas y para medir cuánto coincide el juez con una persona.

El detalle pesado de cada corrida (respuesta completa, chunks, prompt, salida cruda del
juez) va al object store (MinIO) en `bench/runs/<id>.json`; ver shared/object_store.py.

Juez: el LLM recibe la pregunta, los componentes (numerados y SIN decirle cuáles son
must_not, para que solo DETECTE presencia) y la respuesta, y devuelve un veredicto por
componente: presente / parcial / ausente. La inversión de los must_not y el cálculo del
score se hacen aquí en código, no en el LLM — un modelo chico (Gemma-4B) detecta mejor
de lo que razona sobre reglas de puntuación.
"""

from __future__ import annotations

import http.client
import json
import re
import threading
import time
import traceback
import urllib.error
from typing import Callable

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

KINDS = ('must', 'should', 'must_not')
# Dificultad de la pregunta (criterio del set penal):
#   facil   — pregunta directa sobre un artículo o caso específico bien definido de la ley
#   mediano — definición, clasificación o explicación de un tema específico
#   dificil — analogía y análisis de varias legislaciones sobre un mismo tema
DIFFICULTIES = ('facil', 'mediano', 'dificil')
_DIFF_ALIASES = {'facil': 'facil', 'fácil': 'facil', 'easy': 'facil',
                 'mediano': 'mediano', 'medio': 'mediano', 'media': 'mediano', 'medium': 'mediano',
                 'dificil': 'dificil', 'difícil': 'dificil', 'hard': 'dificil'}


def norm_difficulty(v):
    """'Fácil'/'medio'/'hard'… → id canónico; '' o None → None; desconocido → False."""
    if v is None or not str(v).strip():
        return None
    return _DIFF_ALIASES.get(str(v).strip().lower(), False)
VERDICT_VALUE = {'presente': 1.0, 'parcial': 0.5, 'ausente': 0.0}
# Sinónimos que un modelo chico suele devolver en lugar del término pedido.
_VERDICT_ALIASES = {
    'presente': 'presente', 'present': 'presente', 'sí': 'presente', 'si': 'presente',
    'yes': 'presente', 'cumple': 'presente', 'completo': 'presente',
    'parcial': 'parcial', 'partial': 'parcial', 'parcialmente': 'parcial',
    'ausente': 'ausente', 'absent': 'ausente', 'no': 'ausente', 'falta': 'ausente',
    'no cumple': 'ausente',
}
# Si la pregunta no tiene componentes pero sí respuesta de referencia, se evalúa contra
# este componente implícito (así un set "pregunta + respuesta" también funciona).
IMPLICIT_COMPONENT = 'Coincide en lo esencial con la respuesta de referencia (mismos hechos, artículos y conclusión).'

JUDGE_SYSTEM = (
    'Eres un evaluador estricto y objetivo. Recibes una PREGUNTA, una RESPUESTA a evaluar y '
    'una lista numerada de ELEMENTOS. Para CADA elemento decide si la RESPUESTA lo contiene:\n'
    '- "presente": la respuesta lo afirma de forma clara y correcta (aunque use otras palabras).\n'
    '- "parcial": lo menciona de forma incompleta, imprecisa o ambigua.\n'
    '- "ausente": no lo menciona.\n'
    'Juzga SOLO lo que dice la respuesta; no uses tu propio conocimiento para completarla. '
    'Un número de artículo o de ley distinto al del elemento NO cuenta como presente.\n'
    'Devuelve ÚNICAMENTE un JSON con esta forma exacta, un objeto por elemento y en el mismo orden:\n'
    '{"elementos": [{"n": 1, "veredicto": "presente", "evidencia": "frase breve copiada de la respuesta o vacío"}]}'
)


# ── Lógica pura (probada en tests/test_bench.py) ──────────────────────────────────

def effective_components(question: dict) -> list[dict]:
    comps = [c for c in (question.get('components') or []) if (c.get('text') or '').strip()]
    if not comps and (question.get('expected_answer') or '').strip():
        comps = [{'id': None, 'text': IMPLICIT_COMPONENT, 'kind': 'must', 'weight': 1.0}]
    return comps


def build_judge_prompt(question: str, answer: str, components: list[dict],
                       expected_answer: str = '') -> str:
    items = '\n'.join(f'{i}. {c["text"].strip()}' for i, c in enumerate(components, 1))
    ref = f'\nRESPUESTA DE REFERENCIA (solo para interpretar los elementos):\n{expected_answer.strip()}\n' \
        if (expected_answer or '').strip() else ''
    return (f'PREGUNTA:\n{question.strip()}\n{ref}\nELEMENTOS:\n{items}\n\n'
            f'RESPUESTA A EVALUAR:\n{answer.strip()}\n\n'
            f'Devuelve el JSON con los {len(components)} elementos.')


def _norm_verdict(v) -> str | None:
    s = str(v or '').strip().lower().strip('."\' ')
    return _VERDICT_ALIASES.get(s)


def parse_judge(raw: str, n: int) -> list[dict]:
    """Salida cruda del juez → lista de n veredictos {verdict, evidence}. Tolera texto
    alrededor del JSON, bloques ```json y claves en inglés. Elementos que falten o no se
    entiendan quedan como verdict=None (se cuentan como ausentes y se marcan en la UI)."""
    out = [{'verdict': None, 'evidence': ''} for _ in range(n)]
    txt = (raw or '').strip()
    m = re.search(r'\{.*\}', txt, re.S)
    data = None
    if m:
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            data = None
    items = []
    if isinstance(data, dict):
        items = data.get('elementos') or data.get('elements') or data.get('items') or []
    elif isinstance(data, list):
        items = data
    for pos, it in enumerate(items):
        if not isinstance(it, dict):
            continue
        idx = it.get('n', it.get('id', pos + 1))
        try:
            idx = int(idx) - 1
        except (TypeError, ValueError):
            idx = pos
        if 0 <= idx < n:
            out[idx] = {'verdict': _norm_verdict(it.get('veredicto', it.get('verdict'))),
                        'evidence': str(it.get('evidencia', it.get('evidence', '')) or '')[:400]}
    return out


def score_question(components: list[dict], verdicts: list[dict]) -> dict:
    """score ∈ [0,1] = (Σ peso·valor de must/should − Σ peso·valor de must_not violados)
    / Σ peso de must/should. `passed` = todos los must presentes y ningún must_not presente
    (parcial de un must_not NO reprueba, pero sí resta la mitad de su peso)."""
    pos_w = pos_got = neg = 0.0
    must_total = must_ok = violations = 0
    for c, v in zip(components, verdicts):
        w = float(c.get('weight') or 1.0)
        val = VERDICT_VALUE.get(v.get('verdict') or 'ausente', 0.0)
        if c['kind'] == 'must_not':
            neg += w * val
            violations += v.get('verdict') == 'presente'
        else:
            pos_w += w
            pos_got += w * val
            if c['kind'] == 'must':
                must_total += 1
                must_ok += v.get('verdict') == 'presente'
    score = max(0.0, min(1.0, (pos_got - neg) / pos_w)) if pos_w else (0.0 if neg else 1.0)
    return {'score': round(score, 4), 'passed': must_ok == must_total and violations == 0,
            'must_total': must_total, 'must_ok': must_ok, 'violations': violations}


# ── Recuperación del artículo correcto (sin LLM) ─────────────────────────────────
# Los `must` de cita ("Cita el art. 179 del Código Penal de la Ciudad de México") dicen QUÉ
# artículo necesita la respuesta. Aquí se convierten en referencias (documento, artículo) y,
# en cada corrida, se mide si ese chunk llegó al contexto del LLM: separa "la búsqueda no lo
# trajo" de "lo tenía y respondió mal", y no depende del juez (no tiene ruido).
LAW_SOURCES = [   # (patrón en el texto, documento del corpus o None si no está ingestado)
    # Los más específicos primero: "Código Nacional de Procedimientos Civiles y Familiares" contiene
    # "Nacional de Procedimientos" (CNPP) y los códigos familiares de Morelos contienen "Morelos".
    (r'Procedimientos Civiles y Familiares|\bCNPCF\b', 'Código Nacional de Procedimientos Civiles y Familiares.md'),
    (r'C[óo]digo Procesal Familiar|\bCPROFAMEM\b', 'CPROFAMEM.md'),
    (r'C[óo]digo Familiar|\bCFAMILIAREM\b', 'CFAMILIAREM.md'),
    (r'Ciudad de M[ée]xico|Distrito Federal|\bCDMX\b|\bCPCDMX\b', 'Código Penal de la Ciudad de México.md'),
    (r'Estado de M[ée]xico|\bCPEM\b|\bEdomex\b', 'Código Penal del Estado de México.md'),
    (r'C[óo]digo Penal Federal|\bCPF\b', 'Código Penal Federal.md'),
    (r'Procedimientos Penales|\bCNPP\b', 'Código Nacional de Procedimientos Penales.md'),
    (r'Morelos', 'Código PENALEM.md'),
    (r'Quer[ée]taro', 'Código Penal del Estado de Querétaro.md'),
]
_SUFFIX = r'(?:\s*(?:o\b|bis\b|ter\b|qu[aá]ter\b|quintus\b|quinquies\b))?'
_ART_LIST_RE = re.compile(   # "art. 179", "arts. 269 y 269 Bis", "artículos 261, 262 y 266"
    r'(?i)\bart(?:[íi]culos?|s?\.)\s*(\d+' + _SUFFIX + r'(?:\s*(?:,|\by\b)\s*\d+' + _SUFFIX + r')*)')
_ART_ONE_RE = re.compile(r'(?i)\d+' + _SUFFIX)


def _laws_in(text: str) -> list:
    """Leyes mencionadas, en orden de aparición, como (patrón, documento)."""
    hits = []
    for rx, src in LAW_SOURCES:
        m = re.search('(?i)' + rx, text or '')
        if m:
            hits.append((m.start(), rx, src))
    return [(rx, src) for _, rx, src in sorted(hits)]


def _label(raw: str) -> str:
    return re.sub(r'\s+', ' ', raw.strip())


def gold_refs(question: str, components: list[dict]) -> list[list[dict]]:
    """Grupos de artículos que la respuesta necesita, leídos de los MUST. Cada grupo es una
    lista de alternativas [{'source', 'article', 'label'}]: basta con recuperar una ("Cita al
    menos uno…"). `source` None = ley que no está en LAW_SOURCES; si el documento no está
    ingestado, resolve_gold no le encuentra chunks y cuenta como fuera del corpus."""
    q_laws = _laws_in(question)
    groups, seen = [], set()
    for c in components or []:
        if c.get('kind') != 'must':
            continue
        text = c.get('text') or ''
        if re.match(r'(?i)\s*cita al menos uno', text):
            alts = []
            for part in text.split(':', 1)[-1].split(';'):
                laws = _laws_in(part)
                for m in _ART_LIST_RE.finditer(part):
                    for a in _ART_ONE_RE.findall(m.group(1)):
                        if laws:
                            alts.append({'source': laws[0][1], 'article': _label(a)})
            chunks = [alts] if alts else []
        else:
            chunks = []
            for m in _ART_LIST_RE.finditer(text):
                # Ley: la que se nombra DESPUÉS del artículo en el mismo must, si no la primera
                # del must, si no la única de la pregunta.
                after = _laws_in(text[m.end():m.end() + 80])
                laws = after or _laws_in(text) or (q_laws if len(q_laws) == 1 else [])
                if not laws:
                    continue
                for a in _ART_ONE_RE.findall(m.group(1)):
                    chunks.append([{'source': laws[0][1], 'article': _label(a)}])
        for g in chunks:
            key = tuple(sorted((x['source'] or '', x['article'].lower()) for x in g))
            if key not in seen:
                seen.add(key)
                groups.append(g)
    for g in groups:
        for x in g:
            short = next((k for k, v in (('CNPCF', 'Civiles y Familiares'), ('CFM', 'CFAMILIAREM'),
                                         ('CPFM', 'CPROFAMEM'), ('CDMX', 'Ciudad'), ('CPEM', 'Estado de M'),
                                         ('CPF', 'Federal'), ('CNPP', 'Procedimientos Penales'),
                                         ('Morelos', 'PENALEM'), ('Querétaro', 'Querétaro'))
                          if x['source'] and v in x['source']),
                         '?')
            x['label'] = f"{short} {x['article']}"
    return groups


def _article_rx(article: str):
    toks = article.split()
    return re.compile(r'(?i)> art[íi]culo\s+' + r'\s*'.join(map(re.escape, toks)) + r'[oº°]?\.?$')


def resolve_gold(cur, table: str, groups: list[list[dict]]) -> list[list[dict]]:
    """Añade a cada alternativa los `ids` de sus chunks: por jerarquía ("> Artículo 179") y,
    si el documento no está partido por artículo (p. ej. Morelos), por el texto."""
    cache = {}
    for g in groups:
        for x in g:
            src = x['source']
            if src is None:
                x['ids'] = []
                continue
            if src not in cache:
                cur.execute(f"SELECT id, hierarchy, text FROM {table} WHERE source = %s", (src,))
                cache[src] = cur.fetchall()
            rx = _article_rx(x['article'])
            ids = [i for i, h, _ in cache[src] if rx.search(h or '')]
            if not ids:
                # Documento sin chunk propio para ese artículo (p. ej. "ARTÍCULO *65.-" de Morelos,
                # que el chunker no separa): primero el chunk donde el artículo EMPIEZA (encabezado
                # de línea) y, solo si no hay, cualquier mención — una referencia cruzada como
                # "…los artículos 65 y 737…" no debe contar como el artículo.
                num = re.escape(x['article'].split()[0])
                start = re.compile(r'(?im)^[\s#>*_]*art[íi]c?u?lo\s*\**\s*' + num + r'(?![0-9])')
                ids = [i for i, _, t in cache[src] if start.search(t or '')]
                if not ids:
                    trx = re.compile(r'(?i)art[íi]culo\W{0,4}' + num + r'(?![0-9])')
                    ids = [i for i, _, t in cache[src] if trx.search(t or '')]
            x['ids'] = ids
    return groups


def retrieval_check(groups: list[list[dict]], context_ids: list[int]) -> dict:
    """¿Llegó cada artículo necesario al contexto? rank = posición (1 = primero) o None."""
    pos = {cid: i + 1 for i, cid in enumerate(context_ids)}
    out = []
    for g in groups:
        ranks = [pos[i] for x in g for i in x.get('ids', []) if i in pos]
        out.append({'labels': [x['label'] for x in g], 'rank': min(ranks) if ranks else None,
                    'in_corpus': any(x.get('ids') for x in g)})
    hit = sum(o['rank'] is not None for o in out)
    attainable = sum(o['in_corpus'] for o in out)
    return {'groups': out, 'hit': hit, 'total': len(out), 'attainable': attainable}


def aggregate(results: list[dict]) -> dict:
    ok = [r for r in results if not r.get('error')]
    n = len(ok)
    must_total = sum(r['must_total'] for r in ok)
    return {
        'n': len(results), 'errors': len(results) - n,
        'score': round(sum(r['score'] for r in ok) / n, 4) if n else None,
        'pass_rate': round(sum(r['passed'] for r in ok) / n, 4) if n else None,
        'must_coverage': round(sum(r['must_ok'] for r in ok) / must_total, 4) if must_total else None,
        'violations': sum(r['violations'] for r in ok),
        'avg_seconds': round(sum(r.get('seconds') or 0 for r in ok) / n, 1) if n else None,
        **_retrieval_agg(ok),
    }


def _retrieval_agg(ok: list[dict]) -> dict:
    rs = [r['retrieval'] for r in ok if r.get('retrieval') and r['retrieval'].get('attainable')]
    if not rs:
        return {}
    hit = sum(min(r['hit'], r['attainable']) for r in rs)
    att = sum(r['attainable'] for r in rs)
    return {'retrieval_recall': round(hit / att, 4) if att else None,          # artículos que llegaron
            'retrieval_full': round(sum(r['hit'] >= r['attainable'] for r in rs) / len(rs), 4),  # preguntas completas
            'retrieval_n': len(rs)}


# ── Revisión humana ──────────────────────────────────────────────────────────────
# Una persona marca cada componente del resultado (presente/parcial/ausente), igual que el
# juez, y califica la respuesta de 1 a 5. Con eso se calcula el score humano (misma fórmula)
# y el ACUERDO con el juez: si es alto, el benchmark automático es creíble.

def clean_review(payload, n_components: int) -> tuple[dict | None, str | None]:
    """Valida el cuerpo de una revisión → (revisión limpia, error)."""
    if not isinstance(payload, dict):
        return None, 'cuerpo inválido'
    vs = payload.get('verdicts')
    if not isinstance(vs, list) or len(vs) != n_components:
        return None, f'se esperaban {n_components} veredictos'
    verdicts = [_norm_verdict(v) for v in vs]
    if any(v is None for v in verdicts):
        return None, 'marca todos los componentes (presente / parcial / ausente)'
    rating = payload.get('rating')
    if rating in ('', None):
        rating = None
    else:
        try:
            rating = int(rating)
        except (TypeError, ValueError):
            return None, 'calificación inválida'
        if not 1 <= rating <= 5:
            return None, 'la calificación va de 1 a 5'
    return {'verdicts': verdicts, 'rating': rating,
            'comment': str(payload.get('comment') or '').strip()[:4000]}, None


def score_review(judge_verdicts: list[dict], human: list[str]) -> dict:
    """Score humano con la misma fórmula que el juez. `judge_verdicts` son los del resultado
    (traen kind/weight de cada componente, congelados en la corrida)."""
    return score_question(judge_verdicts, [{'verdict': v} for v in human])


def review_stats(results: list[dict], reviews: list[dict]) -> dict:
    """Métricas de las revisiones humanas de una corrida y su acuerdo con el juez.
    Con varios revisores por pregunta, cada revisión cuenta por separado."""
    by_q = {r['question_id']: r for r in results if not r.get('error')}
    revs = [rv for rv in reviews if rv.get('question_id') in by_q]
    if not revs:
        return {'n_reviews': 0, 'n_questions': 0}
    comp_n = comp_same = pass_same = 0
    judge_scores, human_scores, ratings = [], [], []
    confusion = {}   # (juez, humano) → n, para ver hacia dónde se equivoca el juez
    for rv in revs:
        res = by_q[rv['question_id']]
        for jv, hv in zip(res.get('verdicts') or [], rv['verdicts']):
            j = jv.get('verdict') or 'ausente'
            comp_n += 1
            comp_same += j == hv
            confusion[f'{j}→{hv}'] = confusion.get(f'{j}→{hv}', 0) + 1
        pass_same += bool(res.get('passed')) == bool(rv['passed'])
        judge_scores.append(res['score'])
        human_scores.append(rv['score'])
        if rv.get('rating'):
            ratings.append(rv['rating'])
    n = len(revs)
    return {
        'n_reviews': n, 'n_questions': len({rv['question_id'] for rv in revs}),
        'human_score': round(sum(human_scores) / n, 4),
        'human_pass_rate': round(sum(bool(rv['passed']) for rv in revs) / n, 4),
        'judge_score': round(sum(judge_scores) / n, 4),      # del juez, en las MISMAS preguntas
        'judge_pass_rate': round(sum(bool(by_q[rv['question_id']].get('passed')) for rv in revs) / n, 4),
        'comp_agreement': round(comp_same / comp_n, 4) if comp_n else None,
        'pass_agreement': round(pass_same / n, 4),
        'avg_rating': round(sum(ratings) / len(ratings), 2) if ratings else None,
        'confusion': confusion,
    }


def validate_set_payload(payload, existing_ids=frozenset()) -> list[str]:
    """Errores del JSON de un set tal como lo edita /benchmark/editor (estricto: el editor no
    "arregla" en silencio como el import). `existing_ids` = ids de preguntas del set; un
    `id` ajeno o repetido es error (evita mover preguntas entre sets o duplicarlas)."""
    errs = []
    if not isinstance(payload, dict):
        return ['El JSON debe ser un objeto { … }.']
    for f in ('name', 'topic'):
        if not str(payload.get(f) or '').strip():
            errs.append(f'Falta "{f}".')
    qs = payload.get('questions')
    if not isinstance(qs, list):
        return errs + ['"questions" debe ser una lista [ … ].']
    seen = set()
    for i, q in enumerate(qs, 1):
        where = f'Pregunta #{i}'
        if not isinstance(q, dict):
            errs.append(f'{where}: debe ser un objeto {{ … }}.')
            continue
        if not str(q.get('question') or '').strip():
            errs.append(f'{where}: "question" está vacío.')
        qid = q.get('id')
        if qid is not None:
            if not isinstance(qid, int) or qid not in existing_ids:
                errs.append(f'{where}: "id": {qid!r} no pertenece a este set (quítalo para crear una pregunta nueva).')
            elif qid in seen:
                errs.append(f'{where}: "id": {qid} está repetido.')
            seen.add(qid)
        if norm_difficulty(q.get('difficulty')) is False:
            errs.append(f'{where}: "difficulty" debe ser "facil", "mediano" o "dificil" (vino {q.get("difficulty")!r}).')
        comps = q.get('components', [])
        if not isinstance(comps, list):
            errs.append(f'{where}: "components" debe ser una lista.')
            continue
        for j, c in enumerate(comps, 1):
            cw = f'{where}, componente {j}'
            if not isinstance(c, dict):
                errs.append(f'{cw}: debe ser un objeto.')
                continue
            if c.get('kind') not in KINDS:
                errs.append(f'{cw}: "kind" debe ser "must", "should" o "must_not" (vino {c.get("kind")!r}).')
            if not str(c.get('text') or '').strip():
                errs.append(f'{cw}: "text" está vacío.')
            w = c.get('weight', 1)
            if isinstance(w, bool) or not isinstance(w, (int, float)) or w < 0:
                errs.append(f'{cw}: "weight" debe ser un número ≥ 0.')
        if not comps and not str(q.get('expected_answer') or '').strip():
            errs.append(f'{where}: sin componentes ni "expected_answer": no se podría calificar.')
    return errs


# ── Esquema ───────────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS bench_sets (
    id serial PRIMARY KEY, name text NOT NULL, topic text NOT NULL, description text,
    created_by text, created_at timestamptz DEFAULT now(), updated_at timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS bench_questions (
    id serial PRIMARY KEY, set_id int NOT NULL REFERENCES bench_sets(id) ON DELETE CASCADE,
    position int NOT NULL DEFAULT 0, question text NOT NULL, expected_answer text, notes text,
    created_at timestamptz DEFAULT now(), updated_at timestamptz DEFAULT now());
CREATE INDEX IF NOT EXISTS bench_questions_set ON bench_questions (set_id, position);
ALTER TABLE bench_questions ADD COLUMN IF NOT EXISTS difficulty text;
CREATE TABLE IF NOT EXISTS bench_components (
    id serial PRIMARY KEY, question_id int NOT NULL REFERENCES bench_questions(id) ON DELETE CASCADE,
    position int NOT NULL DEFAULT 0, text text NOT NULL,
    kind text NOT NULL DEFAULT 'must' CHECK (kind IN ('must', 'should', 'must_not')),
    weight real NOT NULL DEFAULT 1);
CREATE INDEX IF NOT EXISTS bench_components_q ON bench_components (question_id, position);
CREATE TABLE IF NOT EXISTS bench_runs (
    id serial PRIMARY KEY, set_id int REFERENCES bench_sets(id) ON DELETE SET NULL,
    set_name text, topic text, label text, config jsonb, status text NOT NULL DEFAULT 'running',
    n int NOT NULL DEFAULT 0, done int NOT NULL DEFAULT 0, metrics jsonb, artifact_key text,
    error text, created_by text, created_at timestamptz DEFAULT now(), finished_at timestamptz);
CREATE TABLE IF NOT EXISTS bench_results (
    id serial PRIMARY KEY, run_id int NOT NULL REFERENCES bench_runs(id) ON DELETE CASCADE,
    question_id int, position int, question text, score real, passed boolean,
    must_total int, must_ok int, violations int, verdicts jsonb, seconds real, error text);
CREATE INDEX IF NOT EXISTS bench_results_run ON bench_results (run_id, position);
ALTER TABLE bench_results ADD COLUMN IF NOT EXISTS retrieval jsonb;   -- ¿llegó el artículo correcto al contexto?
-- Latido de la corrida: se actualiza con cada pregunta terminada (ver STALE_MINUTES).
ALTER TABLE bench_runs ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();
CREATE TABLE IF NOT EXISTS bench_reviews (
    id serial PRIMARY KEY, run_id int NOT NULL REFERENCES bench_runs(id) ON DELETE CASCADE,
    question_id int NOT NULL, reviewer text NOT NULL,
    verdicts jsonb NOT NULL, score real, passed boolean, rating int, comment text,
    created_at timestamptz DEFAULT now(), updated_at timestamptz DEFAULT now(),
    UNIQUE (run_id, question_id, reviewer));
"""

# Una corrida 'running' sin avance en este tiempo se da por muerta (el proceso que la corría
# se reinició). NO basta con ver status='running' al arrancar: la BD es compartida (prod y una
# app local por túnel), y otro proceso puede tener una corrida viva. Una pregunta tarda
# segundos; el peor caso (timeouts de LLM y juez) ronda 6 min.
STALE_MINUTES = 15
_STALE_SQL = ("UPDATE bench_runs SET status = 'interrupted', finished_at = now() "
              "WHERE status = 'running' AND coalesce(updated_at, created_at) < now() - %s * interval '1 minute'")


# Errores de red/servidor del LLM (se reinicia, corta respuestas largas): se reintentan. Un
# error de lógica (ValueError, KeyError…) no se reintenta: fallaría igual.
_TRANSIENT = (ConnectionError, TimeoutError, urllib.error.URLError, http.client.HTTPException)
RETRY_WAITS = (5, 15)


def _retry(fn, cancel: threading.Event | None = None):
    for wait in RETRY_WAITS:
        try:
            return fn()
        except _TRANSIENT as e:
            print(f'bench: error transitorio ({type(e).__name__}: {e}); reintento en {wait}s')
            if cancel is not None and cancel.wait(wait):
                raise
            if cancel is None:
                time.sleep(wait)
    return fn()


class Bench:
    """Encapsula el estado del benchmark y expone `router` (se monta en main.py).
    Recibe sus dependencias inyectadas para no importar main (evita el ciclo)."""

    def __init__(self, *, connect: Callable, ask: Callable, judge, store,
                 system_for: Callable, current_email: Callable, can_edit_topic: Callable,
                 can_run: Callable, topic_label: Callable, table: str | None = None):
        self.connect, self.ask, self.judge, self.store = connect, ask, judge, store
        self.table = table   # tabla de chunks: para ubicar los artículos de los must (recuperación)
        self.system_for, self.current_email = system_for, current_email
        self.can_edit_topic, self.can_run, self.topic_label = can_edit_topic, can_run, topic_label
        self._lock = threading.Lock()
        self._running: int | None = None    # id de la corrida en curso (una a la vez)
        self._cancel = threading.Event()
        with connect() as c, c.cursor() as cur:
            cur.execute(SCHEMA)
            cur.execute(_STALE_SQL, (STALE_MINUTES,))   # corridas huérfanas de un reinicio
            c.commit()
        self.router = self._make_router()

    # ── lectura ───────────────────────────────────────────────────────────────────
    def load_set(self, cur, set_id: int) -> dict | None:
        cur.execute("SELECT id, name, topic, description, created_by, created_at::text, updated_at::text "
                    "FROM bench_sets WHERE id = %s", (set_id,))
        row = cur.fetchone()
        if not row:
            return None
        s = dict(zip(['id', 'name', 'topic', 'description', 'created_by', 'created_at', 'updated_at'], row))
        s['topic_label'] = self.topic_label(s['topic'])
        cur.execute("SELECT id, position, question, expected_answer, notes, difficulty FROM bench_questions "
                    "WHERE set_id = %s ORDER BY position, id", (set_id,))
        qs = [dict(zip(['id', 'position', 'question', 'expected_answer', 'notes', 'difficulty'], r)) for r in cur.fetchall()]
        by_id = {q['id']: q for q in qs}
        for q in qs:
            q['components'] = []
        if qs:
            cur.execute("SELECT question_id, id, text, kind, weight FROM bench_components "
                        "WHERE question_id = ANY(%s) ORDER BY position, id", (list(by_id),))
            for qid, cid, text, kind, w in cur.fetchall():
                by_id[qid]['components'].append({'id': cid, 'text': text, 'kind': kind, 'weight': w})
        s['questions'] = qs
        return s

    # ── escritura ─────────────────────────────────────────────────────────────────
    @staticmethod
    def _clean_components(comps) -> list[dict]:
        out = []
        for c in comps or []:
            text = (c.get('text') or '').strip()
            if not text:
                continue
            kind = c.get('kind') if c.get('kind') in KINDS else 'must'
            try:
                w = max(0.0, float(c.get('weight', 1) or 1))
            except (TypeError, ValueError):
                w = 1.0
            out.append({'text': text, 'kind': kind, 'weight': w})
        return out

    def _write_components(self, cur, qid: int, comps) -> None:
        cur.execute("DELETE FROM bench_components WHERE question_id = %s", (qid,))
        for pos, c in enumerate(self._clean_components(comps)):
            cur.execute("INSERT INTO bench_components (question_id, position, text, kind, weight) "
                        "VALUES (%s, %s, %s, %s, %s)", (qid, pos, c['text'], c['kind'], c['weight']))

    def _insert_question(self, cur, set_id: int, q: dict, position: int | None = None) -> int:
        if position is None:
            cur.execute("SELECT coalesce(max(position), -1) + 1 FROM bench_questions WHERE set_id = %s", (set_id,))
            position = cur.fetchone()[0]
        pos = position
        cur.execute("INSERT INTO bench_questions (set_id, position, question, expected_answer, notes, difficulty) "
                    "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                    (set_id, pos, q['question'].strip(), (q.get('expected_answer') or '').strip() or None,
                     (q.get('notes') or '').strip() or None, norm_difficulty(q.get('difficulty')) or None))
        qid = cur.fetchone()[0]
        self._write_components(cur, qid, q.get('components'))
        cur.execute("UPDATE bench_sets SET updated_at = now() WHERE id = %s", (set_id,))
        return qid

    def _set_topic(self, cur, set_id: int) -> str | None:
        cur.execute("SELECT topic FROM bench_sets WHERE id = %s", (set_id,))
        r = cur.fetchone()
        return r[0] if r else None

    def export_set(self, s: dict, with_ids: bool = False) -> dict:
        """Formato portable — el mismo que acepta el import. `with_ids` añade el `id` de cada
        pregunta (lo usa el editor JSON para actualizar en su lugar sin romper comparaciones)."""
        def q_out(q):
            d = {'id': q['id']} if with_ids else {}
            d.update(question=q['question'], difficulty=q.get('difficulty') or '',
                     expected_answer=q.get('expected_answer') or '',
                     notes=q.get('notes') or '',
                     components=[{'kind': c['kind'], 'text': c['text'], 'weight': c['weight']}
                                 for c in q['components']])
            return d
        return {'format': 'rag-lab-bench/v1', 'name': s['name'], 'topic': s['topic'],
                'description': s.get('description') or '', 'questions': [q_out(q) for q in s['questions']]}

    def sync_set(self, cur, sid: int, payload: dict, dry_run: bool) -> dict:
        """Deja el set igual al JSON del editor: preguntas con `id` se actualizan (conservan su
        id → las corridas siguen siendo comparables), sin `id` se crean, y las del set que no
        vienen se borran. El orden del JSON define la posición. Valida antes de tocar nada."""
        s = self.load_set(cur, sid)
        existing = {q['id']: q for q in s['questions']}
        errs = validate_set_payload(payload, frozenset(existing))
        if errs:
            return {'errors': errs}
        qs = payload['questions']
        keep = {q['id'] for q in qs if q.get('id') is not None}
        plan = {'updated': len(keep), 'created': sum(q.get('id') is None for q in qs),
                'deleted': [{'id': q['id'], 'question': q['question']} for q in s['questions'] if q['id'] not in keep],
                'changed': sum(1 for q in qs if q.get('id') is not None and self._q_changed(existing[q['id']], q))}
        if dry_run:
            return plan
        cur.execute("UPDATE bench_sets SET name = %s, topic = %s, description = %s, updated_at = now() WHERE id = %s",
                    (payload['name'].strip(), payload['topic'].strip(),
                     (payload.get('description') or '').strip() or None, sid))
        for d in plan['deleted']:
            cur.execute("DELETE FROM bench_questions WHERE id = %s AND set_id = %s", (d['id'], sid))
        for pos, q in enumerate(qs):
            if q.get('id') is None:
                self._insert_question(cur, sid, q, position=pos)
                continue
            cur.execute("UPDATE bench_questions SET position = %s, question = %s, expected_answer = %s, notes = %s, "
                        "difficulty = %s, updated_at = now() WHERE id = %s",
                        (pos, q['question'].strip(), (q.get('expected_answer') or '').strip() or None,
                         (q.get('notes') or '').strip() or None, norm_difficulty(q.get('difficulty')) or None, q['id']))
            self._write_components(cur, q['id'], q.get('components'))
        return plan

    def _q_changed(self, old: dict, new: dict) -> bool:
        norm = lambda q: (q['question'].strip(), (q.get('expected_answer') or '').strip(),  # noqa: E731
                          (q.get('notes') or '').strip(), norm_difficulty(q.get('difficulty')) or None,
                          [(c['kind'], c['text'].strip(), float(c.get('weight', 1))) for c in q.get('components') or []])
        return norm(old) != norm(new)

    # ── corrida ───────────────────────────────────────────────────────────────────
    def judge_model(self) -> str:
        try:
            return self.judge.model
        except Exception:  # noqa: BLE001 — solo informativo
            return '?'

    def grade(self, question: str, answer: str, components: list[dict], expected: str = '') -> dict:
        prompt = build_judge_prompt(question, answer, components, expected)
        raw = self.judge.chat(JUDGE_SYSTEM, prompt, temperature=0.0, max_tokens=1200, timeout=180,
                              extra={'response_format': {'type': 'json_object'}})
        verdicts = parse_judge(raw, len(components))
        return {'prompt': prompt, 'raw': raw, 'verdicts': verdicts}

    def start_run(self, set_id: int, cfg: dict, label: str, email: str | None) -> int:
        with self._lock:
            if self._running is not None:
                raise RuntimeError(f'Ya hay una corrida en curso (#{self._running}). Espera o cancélala.')
            with self.connect() as c, c.cursor() as cur:
                cur.execute(_STALE_SQL, (STALE_MINUTES,))
                cur.execute("SELECT id FROM bench_runs WHERE status = 'running' LIMIT 1")
                other = cur.fetchone()
                if other:   # viva en OTRO proceso (p. ej. prod mientras se prueba local)
                    raise RuntimeError(f'Ya hay una corrida en curso (#{other[0]}). Espera o cancélala.')
                s = self.load_set(cur, set_id)
                if not s:
                    raise ValueError('el set no existe')
                qs = [q for q in s['questions'] if effective_components(q)]
                if not qs:
                    raise ValueError('ninguna pregunta tiene componentes ni respuesta de referencia')
                if cfg.get('question_ids'):   # corrida parcial: solo esas preguntas, en el orden del set
                    want = set(cfg['question_ids'])
                    qs = [q for q in qs if q['id'] in want]
                    if not qs:
                        raise ValueError('ninguna de las preguntas elegidas está en el set (o no tiene criterios)')
                    cfg = dict(cfg, question_ids=[q['id'] for q in qs], set_total=len(s['questions']))
                cfg = dict(cfg, system=(cfg.get('system') or '').strip() or self.system_for(s['topic']),
                           judge_model=self.judge_model())
                cur.execute("INSERT INTO bench_runs (set_id, set_name, topic, label, config, n, created_by) "
                            "VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s) RETURNING id",
                            (set_id, s['name'], s['topic'], label or None, json.dumps(cfg, ensure_ascii=False),
                             len(qs), email))
                rid = cur.fetchone()[0]
                c.commit()
            self._running = rid
            self._cancel.clear()
        threading.Thread(target=self._run, args=(rid, s, qs, cfg), daemon=True).start()
        return rid

    def _run(self, rid: int, s: dict, qs: list[dict], cfg: dict) -> None:
        results, detail = [], []
        status, err = 'done', None
        gold = {}
        if self.table:
            try:
                with self.connect() as c, c.cursor() as cur:
                    gold = {q['id']: resolve_gold(cur, self.table, gold_refs(q['question'], effective_components(q)))
                            for q in qs}
            except Exception:  # noqa: BLE001 — sin gold la corrida sigue (solo falta la métrica)
                traceback.print_exc()
        try:
            for pos, q in enumerate(qs):
                if self._cancel.is_set():
                    status = 'cancelled'
                    break
                comps = effective_components(q)
                t0 = time.time()
                row = {'question_id': q['id'], 'position': pos, 'question': q['question'],
                       'score': 0.0, 'passed': False, 'must_total': 0, 'must_ok': 0, 'violations': 0,
                       'verdicts': [], 'seconds': None, 'error': None, 'retrieval': None}
                det = {'question_id': q['id'], 'question': q['question'],
                       'expected_answer': q.get('expected_answer') or '', 'difficulty': q.get('difficulty'),
                       'components': comps}
                try:
                    a = _retry(lambda: self.ask(q['question'], cfg['setting'], cfg['k'], cfg['system'], s['topic'],
                                                cfg.get('jurisdictions') or None, cfg['neighbors'], cfg['hyde'],
                                                cfg['rerank'], decompose=cfg.get('decompose', False)), self._cancel)
                    g = _retry(lambda: self.grade(q['question'], a['answer'], comps, q.get('expected_answer') or ''),
                               self._cancel)
                    sc = score_question(comps, g['verdicts'])
                    row.update(sc)
                    if gold.get(q['id']):
                        row['retrieval'] = retrieval_check(gold[q['id']], [ch.get('id') for ch in a.get('chunks', [])])
                    row['verdicts'] = [{'text': c['text'], 'kind': c['kind'], 'weight': c['weight'], **v}
                                       for c, v in zip(comps, g['verdicts'])]
                    det.update(answer=a['answer'], chunks=[{k: ch.get(k) for k in
                                                            ('rank', 'id', 'source', 'hierarchy', 'score', 'neighbor', 'text')}
                                                           for ch in a.get('chunks', [])],
                               rewrite=a.get('rewrite'), score_kind=a.get('score_kind'), hyde_passage=a.get('hyde_passage'),
                               judge_prompt=g['prompt'], judge_raw=g['raw'], answer_seconds=a.get('seconds'),
                               retrieval=row['retrieval'], subqueries=a.get('subqueries'))
                except Exception as e:  # noqa: BLE001 — una pregunta que falla no tumba la corrida
                    row['error'] = det['error'] = f'{type(e).__name__}: {e}'
                row['seconds'] = round(time.time() - t0, 1)
                results.append(row)
                detail.append(dict(det, **{k: row[k] for k in ('score', 'passed', 'verdicts', 'error')}))
                with self.connect() as c, c.cursor() as cur:
                    cur.execute(
                        "INSERT INTO bench_results (run_id, question_id, position, question, score, passed, "
                        "must_total, must_ok, violations, verdicts, seconds, error, retrieval) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s::jsonb)",
                        (rid, row['question_id'], pos, row['question'], row['score'], row['passed'],
                         row['must_total'], row['must_ok'], row['violations'],
                         json.dumps(row['verdicts'], ensure_ascii=False), row['seconds'], row['error'],
                         json.dumps(row['retrieval'], ensure_ascii=False) if row['retrieval'] else None))
                    cur.execute("UPDATE bench_runs SET done = %s, metrics = %s::jsonb, updated_at = now() WHERE id = %s",
                                (len(results), json.dumps(aggregate(results)), rid))
                    c.commit()
        except Exception as e:  # noqa: BLE001
            status, err = 'error', f'{type(e).__name__}: {e}'
            traceback.print_exc()
        key = None
        try:
            key = self.store.put_json(f'bench/runs/{rid}.json', {
                'run_id': rid, 'set': self.export_set(s), 'config': cfg,
                'metrics': aggregate(results), 'status': status, 'results': detail})
        except Exception as e:  # noqa: BLE001 — sin artefacto la corrida sigue valiendo (métricas en PG)
            err = (err + ' · ' if err else '') + f'artefacto no guardado: {type(e).__name__}: {e}'
        with self.connect() as c, c.cursor() as cur:
            cur.execute("UPDATE bench_runs SET status = %s, error = %s, artifact_key = %s, metrics = %s::jsonb, "
                        "finished_at = now() WHERE id = %s",
                        (status, err, key, json.dumps(aggregate(results)), rid))
            c.commit()
        with self._lock:
            self._running = None

    # ── rutas ─────────────────────────────────────────────────────────────────────
    def _make_router(self) -> APIRouter:
        r = APIRouter(prefix='/api/bench')

        def deny(msg='Solo los administradores del tema pueden modificar este set.'):
            return JSONResponse({'error': msg}, status_code=403)

        def bad(msg):
            return JSONResponse({'error': msg}, status_code=400)

        @r.get('/info')
        def info():
            return {'storage': self.store.describe(), 'running': self._running,
                    'judge_url': getattr(self.judge, 'url', ''), 'kinds': list(KINDS)}

        @r.get('/sets')
        def sets():
            with self.connect() as c, c.cursor() as cur:
                cur.execute("""SELECT s.id, s.name, s.topic, s.description, s.updated_at::text,
                                      (SELECT count(*) FROM bench_questions q WHERE q.set_id = s.id),
                                      (SELECT count(*) FROM bench_runs r WHERE r.set_id = s.id)
                               FROM bench_sets s ORDER BY s.topic, s.name""")
                cols = ['id', 'name', 'topic', 'description', 'updated_at', 'n_questions', 'n_runs']
                rows = [dict(zip(cols, x)) for x in cur.fetchall()]
            for x in rows:
                x['topic_label'] = self.topic_label(x['topic'])
            return rows

        @r.post('/sets')
        async def set_create(req: Request):
            b = await req.json()
            name, topic = (b.get('name') or '').strip(), (b.get('topic') or '').strip()
            if not name or not topic:
                return bad('nombre y tema son obligatorios')
            if not self.can_edit_topic(self.current_email(req), topic):
                return deny('No tienes permiso sobre ese tema.')
            with self.connect() as c, c.cursor() as cur:
                cur.execute("INSERT INTO bench_sets (name, topic, description, created_by) VALUES (%s,%s,%s,%s) "
                            "RETURNING id", (name, topic, (b.get('description') or '').strip() or None,
                                             self.current_email(req)))
                sid = cur.fetchone()[0]
                c.commit()
            return {'id': sid}

        @r.post('/sets/import')
        async def set_import(req: Request):
            b = await req.json()
            name, topic = (b.get('name') or '').strip(), (b.get('topic') or '').strip()
            qs = [q for q in (b.get('questions') or []) if (q.get('question') or '').strip()]
            if not name or not topic:
                return bad('el JSON necesita "name" y "topic"')
            if not self.can_edit_topic(self.current_email(req), topic):
                return deny('No tienes permiso sobre ese tema.')
            with self.connect() as c, c.cursor() as cur:
                cur.execute("INSERT INTO bench_sets (name, topic, description, created_by) VALUES (%s,%s,%s,%s) "
                            "RETURNING id", (name, topic, (b.get('description') or '').strip() or None,
                                             self.current_email(req)))
                sid = cur.fetchone()[0]
                for q in qs:
                    self._insert_question(cur, sid, q)
                c.commit()
            return {'id': sid, 'questions': len(qs)}

        @r.get('/sets/{sid}')
        def set_get(sid: int):
            with self.connect() as c, c.cursor() as cur:
                s = self.load_set(cur, sid)
            return s or JSONResponse({'error': 'no existe'}, status_code=404)

        @r.post('/sets/{sid}')
        async def set_update(sid: int, req: Request):
            b = await req.json()
            email = self.current_email(req)
            with self.connect() as c, c.cursor() as cur:
                topic = self._set_topic(cur, sid)
                if topic is None:
                    return JSONResponse({'error': 'no existe'}, status_code=404)
                new_topic = (b.get('topic') or topic).strip()
                if not (self.can_edit_topic(email, topic) and self.can_edit_topic(email, new_topic)):
                    return deny()
                cur.execute("UPDATE bench_sets SET name = coalesce(nullif(%s, ''), name), topic = %s, "
                            "description = %s, updated_at = now() WHERE id = %s",
                            ((b.get('name') or '').strip(), new_topic,
                             (b.get('description') or '').strip() or None, sid))
                c.commit()
            return {'ok': True}

        @r.delete('/sets/{sid}')
        def set_delete(sid: int, request: Request):
            with self.connect() as c, c.cursor() as cur:
                topic = self._set_topic(cur, sid)
                if topic is None:
                    return JSONResponse({'error': 'no existe'}, status_code=404)
                if not self.can_edit_topic(self.current_email(request), topic):
                    return deny()
                cur.execute("DELETE FROM bench_sets WHERE id = %s", (sid,))
                c.commit()
            return {'ok': True}

        @r.get('/sets/{sid}/export')
        def set_export(sid: int, ids: bool = False):
            with self.connect() as c, c.cursor() as cur:
                s = self.load_set(cur, sid)
            return self.export_set(s, with_ids=ids) if s else JSONResponse({'error': 'no existe'}, status_code=404)

        @r.post('/sets/{sid}/content')
        async def set_content(sid: int, req: Request):
            """Guarda el JSON completo del editor. {payload, dry_run}: con dry_run sólo
            devuelve el plan (cuántas se actualizan/crean/borran) para confirmarlo."""
            b = await req.json()
            payload, dry = b.get('payload'), bool(b.get('dry_run'))
            email = self.current_email(req)
            with self.connect() as c, c.cursor() as cur:
                topic = self._set_topic(cur, sid)
                if topic is None:
                    return JSONResponse({'error': 'no existe'}, status_code=404)
                new_topic = str((payload or {}).get('topic') or topic).strip() if isinstance(payload, dict) else topic
                if not (self.can_edit_topic(email, topic) and self.can_edit_topic(email, new_topic)):
                    return deny()
                out = self.sync_set(cur, sid, payload, dry)
                if out.get('errors'):
                    return JSONResponse({'error': 'El JSON tiene errores.', 'errors': out['errors']}, status_code=400)
                if not dry:
                    c.commit()
            return out

        @r.post('/sets/{sid}/backup')
        def set_backup(sid: int, request: Request):
            """Snapshot del set en el object store (bench/exports/…)."""
            with self.connect() as c, c.cursor() as cur:
                s = self.load_set(cur, sid)
            if not s:
                return JSONResponse({'error': 'no existe'}, status_code=404)
            if not self.can_edit_topic(self.current_email(request), s['topic']):
                return deny()
            key = self.store.put_json(f'bench/exports/set-{sid}-{time.strftime("%Y%m%d-%H%M%S")}.json',
                                      self.export_set(s))
            return {'key': key, **self.store.describe()}

        @r.post('/sets/{sid}/questions')
        async def q_create(sid: int, req: Request):
            b = await req.json()
            if not (b.get('question') or '').strip():
                return bad('la pregunta está vacía')
            with self.connect() as c, c.cursor() as cur:
                topic = self._set_topic(cur, sid)
                if topic is None:
                    return JSONResponse({'error': 'no existe'}, status_code=404)
                if not self.can_edit_topic(self.current_email(req), topic):
                    return deny()
                qid = self._insert_question(cur, sid, b)
                c.commit()
            return {'id': qid}

        def _q_topic(cur, qid):
            cur.execute("SELECT s.topic, q.set_id FROM bench_questions q JOIN bench_sets s ON s.id = q.set_id "
                        "WHERE q.id = %s", (qid,))
            return cur.fetchone()

        @r.post('/questions/{qid}')
        async def q_update(qid: int, req: Request):
            b = await req.json()
            if not (b.get('question') or '').strip():
                return bad('la pregunta está vacía')
            with self.connect() as c, c.cursor() as cur:
                row = _q_topic(cur, qid)
                if not row:
                    return JSONResponse({'error': 'no existe'}, status_code=404)
                if not self.can_edit_topic(self.current_email(req), row[0]):
                    return deny()
                cur.execute("UPDATE bench_questions SET question = %s, expected_answer = %s, notes = %s, "
                            "difficulty = %s, updated_at = now() WHERE id = %s",
                            (b['question'].strip(), (b.get('expected_answer') or '').strip() or None,
                             (b.get('notes') or '').strip() or None, norm_difficulty(b.get('difficulty')) or None, qid))
                self._write_components(cur, qid, b.get('components'))
                cur.execute("UPDATE bench_sets SET updated_at = now() WHERE id = %s", (row[1],))
                c.commit()
            return {'ok': True}

        @r.delete('/questions/{qid}')
        def q_delete(qid: int, request: Request):
            with self.connect() as c, c.cursor() as cur:
                row = _q_topic(cur, qid)
                if not row:
                    return JSONResponse({'error': 'no existe'}, status_code=404)
                if not self.can_edit_topic(self.current_email(request), row[0]):
                    return deny()
                cur.execute("DELETE FROM bench_questions WHERE id = %s", (qid,))
                c.commit()
            return {'ok': True}

        @r.post('/run')
        async def run(req: Request):
            b = await req.json()
            email = self.current_email(req)
            if not self.can_run(email):
                return deny('Solo los administradores pueden correr el benchmark.')
            try:
                cfg = {'setting': b.get('setting') or 'híbrido', 'k': int(b.get('k') or 10),
                       'neighbors': bool(b.get('neighbors', True)), 'hyde': bool(b.get('hyde', False)),
                       'rerank': bool(b.get('rerank', False)), 'decompose': bool(b.get('decompose', False)),
                       'system': b.get('system') or '',
                       'jurisdictions': b.get('jurisdictions') or []}
                qids = [int(x) for x in (b.get('question_ids') or [])]
                if qids:   # subconjunto («🎯 Qué preguntas correr»); `subset` describe el criterio
                    cfg.update(question_ids=qids, subset=str(b.get('subset') or '')[:200])
                rid = self.start_run(int(b.get('set_id')), cfg, (b.get('label') or '').strip(), email)
            except (RuntimeError, ValueError, TypeError) as e:
                return bad(str(e))
            return {'run_id': rid}

        @r.post('/runs/{rid}/cancel')
        def run_cancel(rid: int, request: Request):
            if not self.can_run(self.current_email(request)):
                return deny('Solo los administradores pueden cancelar corridas.')
            if self._running != rid:
                return bad('esa corrida no está en curso')
            self._cancel.set()
            return {'ok': True}

        @r.get('/runs')
        def runs(set_id: int | None = None):
            with self.connect() as c, c.cursor() as cur:
                cur.execute(_STALE_SQL, (STALE_MINUTES,))
                c.commit()
                cur.execute("SELECT id, set_id, set_name, topic, label, config, status, n, done, metrics, "
                            "error, created_by, created_at::text, finished_at::text, "
                            "(SELECT count(DISTINCT question_id) FROM bench_reviews v WHERE v.run_id = bench_runs.id) "
                            "FROM bench_runs "
                            + ("WHERE set_id = %s " if set_id else "") + "ORDER BY id DESC LIMIT 200",
                            (set_id,) if set_id else ())
                cols = ['id', 'set_id', 'set_name', 'topic', 'label', 'config', 'status', 'n', 'done',
                        'metrics', 'error', 'created_by', 'created_at', 'finished_at', 'reviewed']
                return [dict(zip(cols, x)) for x in cur.fetchall()]

        @r.get('/runs/{rid}')
        def run_get(rid: int):
            with self.connect() as c, c.cursor() as cur:
                cur.execute("SELECT id, set_id, set_name, topic, label, config, status, n, done, metrics, "
                            "error, artifact_key, created_at::text, finished_at::text FROM bench_runs WHERE id = %s",
                            (rid,))
                row = cur.fetchone()
                if not row:
                    return JSONResponse({'error': 'no existe'}, status_code=404)
                cols = ['id', 'set_id', 'set_name', 'topic', 'label', 'config', 'status', 'n', 'done',
                        'metrics', 'error', 'artifact_key', 'created_at', 'finished_at']
                out = dict(zip(cols, row))
                cur.execute("SELECT question_id, position, question, score, passed, must_total, must_ok, "
                            "violations, verdicts, seconds, error, retrieval FROM bench_results WHERE run_id = %s "
                            "ORDER BY position", (rid,))
                rcols = ['question_id', 'position', 'question', 'score', 'passed', 'must_total', 'must_ok',
                         'violations', 'verdicts', 'seconds', 'error', 'retrieval']
                out['results'] = [dict(zip(rcols, x)) for x in cur.fetchall()]
            return out

        @r.get('/runs/{rid}/artifact')
        def run_artifact(rid: int, question_id: int | None = None):
            """Detalle completo desde el object store; con ?question_id= solo esa pregunta."""
            with self.connect() as c, c.cursor() as cur:
                cur.execute("SELECT artifact_key FROM bench_runs WHERE id = %s", (rid,))
                row = cur.fetchone()
            if not row or not row[0]:
                return JSONResponse({'error': 'esta corrida no tiene artefacto (¿sigue en curso?)'}, status_code=404)
            try:
                art = self.store.get_json(row[0].removeprefix(self.store.prefix))
            except Exception as e:  # noqa: BLE001
                return JSONResponse({'error': f'no pude leer {row[0]}: {type(e).__name__}: {e}'}, status_code=502)
            if question_id is not None:
                hit = next((x for x in art.get('results', []) if x.get('question_id') == question_id), None)
                return hit or JSONResponse({'error': 'pregunta no está en la corrida'}, status_code=404)
            return art

        # ── revisión humana ──
        def _load_reviews(cur, rid):
            cur.execute("SELECT question_id, reviewer, verdicts, score, passed, rating, comment, updated_at::text "
                        "FROM bench_reviews WHERE run_id = %s ORDER BY question_id, reviewer", (rid,))
            cols = ['question_id', 'reviewer', 'verdicts', 'score', 'passed', 'rating', 'comment', 'updated_at']
            return [dict(zip(cols, x)) for x in cur.fetchall()]

        def _results(cur, rid):
            cur.execute("SELECT question_id, score, passed, verdicts, error FROM bench_results WHERE run_id = %s",
                        (rid,))
            return [dict(zip(['question_id', 'score', 'passed', 'verdicts', 'error'], x)) for x in cur.fetchall()]

        @r.get('/runs/{rid}/reviews')
        def reviews_get(rid: int, request: Request):
            with self.connect() as c, c.cursor() as cur:
                revs = _load_reviews(cur, rid)
                stats = review_stats(_results(cur, rid), revs)
            return {'me': self.current_email(request), 'reviews': revs, 'stats': stats}

        @r.post('/runs/{rid}/reviews/{qid}')
        async def review_save(rid: int, qid: int, req: Request):
            email = self.current_email(req)
            if not email or not self.can_run(email):
                return deny('Solo los administradores pueden calificar respuestas.')
            with self.connect() as c, c.cursor() as cur:
                cur.execute("SELECT verdicts, error FROM bench_results WHERE run_id = %s AND question_id = %s",
                            (rid, qid))
                row = cur.fetchone()
                if not row:
                    return JSONResponse({'error': 'esa pregunta no está en la corrida'}, status_code=404)
                if row[1]:
                    return bad('esta pregunta falló en la corrida: no hay respuesta que revisar')
                rv, err = clean_review(await req.json(), len(row[0] or []))
                if err:
                    return bad(err)
                sc = score_review(row[0], rv['verdicts'])
                cur.execute(
                    "INSERT INTO bench_reviews (run_id, question_id, reviewer, verdicts, score, passed, rating, comment) "
                    "VALUES (%s,%s,%s,%s::jsonb,%s,%s,%s,%s) ON CONFLICT (run_id, question_id, reviewer) DO UPDATE SET "
                    "verdicts = EXCLUDED.verdicts, score = EXCLUDED.score, passed = EXCLUDED.passed, "
                    "rating = EXCLUDED.rating, comment = EXCLUDED.comment, updated_at = now()",
                    (rid, qid, email, json.dumps(rv['verdicts']), sc['score'], sc['passed'], rv['rating'],
                     rv['comment'] or None))
                c.commit()
            return {'ok': True, 'score': sc['score'], 'passed': sc['passed']}

        @r.delete('/runs/{rid}/reviews/{qid}')
        def review_delete(rid: int, qid: int, request: Request):
            email = self.current_email(request)
            if not email or not self.can_run(email):
                return deny('Solo los administradores pueden calificar respuestas.')
            with self.connect() as c, c.cursor() as cur:   # cada quien borra solo la suya
                cur.execute("DELETE FROM bench_reviews WHERE run_id = %s AND question_id = %s AND reviewer = %s",
                            (rid, qid, email))
                c.commit()
            return {'ok': True}

        @r.delete('/runs/{rid}')
        def run_delete(rid: int, request: Request):
            if not self.can_run(self.current_email(request)):
                return deny('Solo los administradores pueden borrar corridas.')
            if self._running == rid:
                return bad('cancélala primero')
            with self.connect() as c, c.cursor() as cur:
                cur.execute("DELETE FROM bench_runs WHERE id = %s RETURNING artifact_key", (rid,))
                row = cur.fetchone()
                c.commit()
            if row and row[0]:
                try:
                    self.store.delete(row[0].removeprefix(self.store.prefix))
                except Exception:  # noqa: BLE001 — el artefacto huérfano no es grave
                    pass
            return {'ok': True}

        return r
