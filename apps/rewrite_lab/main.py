"""
apps/rewrite_lab/main.py — backend FastAPI del laboratorio de query rewriting.

Calcula EN VIVO, contra los modelos y la BD:
  * la reescritura de cada pregunta (LLM local, shared.llm_client),
  * el rank del gold chunk con la consulta original, con la reescrita sola y con
    multi-query (RRF), recuperando el denso desde pgvector,
  * métricas agregadas (recall@k, MRR).

La UI vive en static/index.html (se sirve estática y pide /api/config al cargar).

Config por env (ver README):
  LLM_URL, TEI_URL, RAG_DB_*, LEGAL_TABLE, HOST, PORT
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

HERE = Path(__file__).resolve().parent
LABS = HERE.parents[1]
sys.path.insert(0, str(LABS))
sys.path.insert(0, str(HERE))   # para importar módulos del propio app (auth) con uvicorn o script

# Config del app (auth, DB, URLs de TEI/LLM) desde apps/rewrite_lab/.env. Se carga
# ANTES de shared.db (que carga el .env de la raíz): así este .env manda en prod.
from dotenv import load_dotenv  # noqa: E402

load_dotenv(HERE / '.env')

from shared.db import connect
from shared.lexical import BM25, rank_indices_by_score, rrf, tokenize
from shared.llm_client import REWRITE_SYSTEM, LlamaClient
from shared.tei_client import TEIClient

from ingest_service import IngestManager

EXPLO = LABS / 'exploracion_datos'
STATIC = HERE / 'static'
TABLE = os.environ.get('LEGAL_TABLE', 'sistema_penal__qwen06__legal')
# Dónde persisten los .md limpios (visualizables) y dónde caen los PDFs subidos.
CLEAN_DIR = Path(os.environ.get('CLEAN_MD_DIR', LABS / 'ingestion' / 'out_clean' / 'Sistema Penal Acusatorio'))
UPLOAD_DIR = Path(os.environ.get('UPLOAD_DIR', LABS / 'ingestion' / '.uploads'))
Q_INSTRUCT = 'Instruct: Recupera el pasaje del código o la doctrina que responde la pregunta.\nQuery: '
KS = (5, 10, 20)
N_DENSE = 1500   # profundidad del ranking denso traído de pgvector para calcular el rank


def list_goldens():
    """Test sets disponibles: los golden*.json de exploracion_datos/."""
    return sorted(p.name for p in EXPLO.glob('golden*.json'))


DEFAULT_GOLDEN = 'golden_penal.json' if (EXPLO / 'golden_penal.json').exists() else (list_goldens() or [''])[0]

tei = TEIClient()     # embebe en vivo (sin caché); TEI_URL por env
llm = LlamaClient()   # LLM_URL por env, modelo auto-detectado


def rank_in(ids, gid) -> int | None:
    for r, j in enumerate(ids, 1):
        if j in gid:
            return r
    return None


def dense_ids(cur, qvec) -> list[int]:
    """Ranking denso desde pgvector, reusando el cursor que le pasen (una conexión
    por corrida, no una por query)."""
    cur.execute(f"SELECT id FROM {TABLE} ORDER BY embedding <=> %s LIMIT %s", (qvec, N_DENSE))
    return [r[0] for r in cur.fetchall()]


RUNS_TABLE = 'rewrite_lab_runs'
GOLD_CACHE = HERE / '.gold_ids_cache.json'
# No llamamos a llm.model aquí: auto-detectarlo pega al LLM, y si está caído no debe
# impedir que la app arranque. El rewrite (que sí necesita el LLM) falla por-request.
print(f'Cargando: tabla {TABLE} · sets {list_goldens()} · LLM en {llm.url}')
with connect() as _c, _c.cursor() as _cur:
    _cur.execute(f"""CREATE TABLE IF NOT EXISTS {RUNS_TABLE} (
        id serial PRIMARY KEY, created_at timestamptz DEFAULT now(),
        label text, prompt text, subset text, n int, metrics jsonb, rows jsonb)""")
    _cur.execute(f"ALTER TABLE {RUNS_TABLE} ADD COLUMN IF NOT EXISTS golden text")  # qué set se evaluó
    _c.commit()

# Datasets cargados bajo demanda: name -> {'golden': [...], 'gold_ids': [set,...]}.
DATASETS: dict[str, dict] = {}
_ORIG: dict[tuple, list[int]] = {}   # (golden_name, i) -> ids del ranking base (perezoso)


def _compute_gold_ids(name, golden):
    """Ids de los chunks que contienen la frase-ancla de cada pregunta (LIKE, solo ids).
    Cacheado a disco por (tabla, set): tras la 1a vez es instantáneo."""
    key = f'{TABLE}|{name}'
    if GOLD_CACHE.exists():
        cache = json.load(open(GOLD_CACHE))
        if key in cache and len(cache[key]) == len(golden):
            return [set(x) for x in cache[key]]
    out = []
    with connect() as c, c.cursor() as cur:
        for g in golden:
            cur.execute(f"SELECT id FROM {TABLE} WHERE text LIKE %s", (f"%{g['answer']}%",))
            out.append({r[0] for r in cur.fetchall()})
    cache = json.load(open(GOLD_CACHE)) if GOLD_CACHE.exists() else {}
    cache[key] = [sorted(s) for s in out]
    json.dump(cache, open(GOLD_CACHE, 'w'))
    return out


def get_dataset(name):
    if name not in DATASETS:
        golden = json.load(open(EXPLO / name))
        gold_ids = _compute_gold_ids(name, golden)
        miss = sum(1 for s in gold_ids if not s)
        if miss:
            print(f'  aviso [{name}]: {miss} preguntas sin gold chunk en la tabla')
        DATASETS[name] = {'golden': golden, 'gold_ids': gold_ids}
    return DATASETS[name]


def orig_ids_for(cur, name, golden, i) -> list[int]:
    k = (name, i)
    if k not in _ORIG:
        qv = tei.embed([Q_INSTRUCT + golden[i]['q']], use_cache=False)[0]
        _ORIG[k] = dense_ids(cur, qv)
    return _ORIG[k]


if DEFAULT_GOLDEN:
    get_dataset(DEFAULT_GOLDEN)   # precarga el default para calentar la caché
print('Listo.')


def subset_indices(golden, kind):
    if kind == 'hard':
        return [i for i, g in enumerate(golden) if g.get('difficulty') in ('hard', 'very_hard')]
    if kind == 'muestra':
        return list(range(min(6, len(golden))))   # primeras 6 (set-agnóstico)
    return list(range(len(golden)))


def metrics(ranks):
    n = len(ranks) or 1
    out = {f'recall@{k}': round(sum(1 for r in ranks if r and r <= k) / n, 3) for k in KS}
    out['MRR'] = round(sum(1.0 / r for r in ranks if r) / n, 3)
    return out


def eval_prompt(system_prompt, kind, golden_name):
    ds = get_dataset(golden_name)
    golden, gold_ids = ds['golden'], ds['gold_ids']
    idx = subset_indices(golden, kind)
    t0 = time.time()
    rewrites = [llm.chat(system_prompt, golden[i]['q']) for i in idx]   # llama-server secuencial
    rw_vecs = tei.embed([Q_INSTRUCT + r for r in rewrites], use_cache=False)
    rows, r_orig, r_rw, r_mq = [], [], [], []
    with connect() as conn, conn.cursor() as cur:   # UNA conexión para toda la corrida
        for k, i in enumerate(idx):
            o_ids = orig_ids_for(cur, golden_name, golden, i)   # cacheado tras la 1a vez
            rw_ids = dense_ids(cur, rw_vecs[k])
            mq_ids = rrf([o_ids, rw_ids])
            ro = rank_in(o_ids, gold_ids[i])
            rr, rm = rank_in(rw_ids, gold_ids[i]), rank_in(mq_ids, gold_ids[i])
            r_orig.append(ro); r_rw.append(rr); r_mq.append(rm)
            rows.append({'idx': i, 'difficulty': golden[i].get('difficulty', ''), 'type': golden[i].get('type', ''),
                         'question': golden[i]['q'], 'rewrite': rewrites[k],
                         'rank_orig': ro, 'rank_rewrite': rr, 'rank_mq': rm})
    return {'rows': rows, 'n': len(idx), 'golden': golden_name, 'seconds': round(time.time() - t0, 1),
            'agg': {'denso (orig)': metrics(r_orig), 'rewrite-solo': metrics(r_rw), 'multi-query': metrics(r_mq)}}


# ── Tab "Preguntar (RAG)" ────────────────────────────────────────────────────────
# Trae los k chunks más cercanos según el setting elegido, los inyecta como contexto
# y le pide la respuesta al LLM local (Llama). Para bm25/híbrido se necesita el texto
# de todos los chunks en memoria; se carga una vez al arrancar.
ASK_SYSTEM = (
    'Eres un asistente jurídico del sistema penal acusatorio mexicano. Responde la pregunta ÚNICAMENTE con base en los fragmentos de CONTEXTO proporcionados (extractos del Código Nacional de Procedimientos Penales, del Código Penal Federal, de la Constitución Política de los Estados Unidos Mexicanos y de doctrina). Si el contexto no contiene la respuesta, dilo con claridad y no inventes. Menciona en tu respuesta exactamente el articulo y ley de donde sacas la informacion, asimismo, cita al final de tu respuesta las fuentes doctrinales conforme a los lineamientos editoriales. Responde con suficiente vocabulario tus respuestas, hazlo de manera clara, veridica y oportuna.'
)
print(ASK_SYSTEM)
DOC_BY_ID: dict[int, dict] = {}   # id -> {source,title,hierarchy,text}
BM_IDS: list[int] = []            # índice del corpus -> id de la BD (para mapear BM25)
BM25_INDEX: BM25 | None = None


def load_corpus_index():
    """Carga todos los chunks (id, metadatos, texto) y construye el índice BM25."""
    global BM25_INDEX, BM_IDS, DOC_BY_ID
    with connect() as c, c.cursor() as cur:
        cur.execute(f'SELECT id, source, title, hierarchy, text FROM {TABLE} ORDER BY id')
        rows = cur.fetchall()
    BM_IDS = [r[0] for r in rows]
    DOC_BY_ID = {r[0]: {'source': r[1], 'title': r[2], 'hierarchy': r[3], 'text': r[4]} for r in rows}
    BM25_INDEX = BM25([tokenize(r[4]) for r in rows])
    print(f'Índice léxico BM25: {len(BM_IDS)} chunks en memoria.')


# ── Recuperación con score por chunk ─────────────────────────────────────────────
# Cada método devuelve una lista [(id, score)] y una etiqueta de qué significa el
# score, para poder mostrarlo en la UI:
#   dist  → distancia coseno de pgvector (menor = más cercano)
#   bm25  → score léxico BM25 (mayor = mejor)
#   rrf   → score de Reciprocal Rank Fusion (mayor = mejor)
def dense_ranked(cur, qvec):
    cur.execute(f"SELECT id, (embedding <=> %s) AS dist FROM {TABLE} ORDER BY 2 LIMIT %s",
                (qvec, N_DENSE))
    return [(r[0], float(r[1])) for r in cur.fetchall()]


def bm25_ranked(question):
    scores = BM25_INDEX.scores(tokenize(question))
    return [(BM_IDS[i], float(scores[i])) for i in rank_indices_by_score(scores)]


def rrf_scored(ranked_id_lists, k=60):
    """RRF sobre listas de ids ya ordenadas; devuelve [(id, score)] ordenado desc."""
    agg: dict[int, float] = {}
    for lst in ranked_id_lists:
        for rank, i in enumerate(lst, 1):
            agg[i] = agg.get(i, 0.0) + 1.0 / (k + rank)
    return sorted(agg.items(), key=lambda kv: -kv[1])


# Etiquetas del dropdown -> lógica de recuperación.
ASK_SETTINGS = ['orig', 'reescribir', 'multiquery', 'bm25', 'híbrido']


def retrieve_scored(cur, question, setting):
    """Devuelve (lista[(id, score)], etiqueta_de_score, reescritura_o_None)."""
    if setting == 'bm25':
        return bm25_ranked(question), 'bm25', None
    d_orig = dense_ranked(cur, tei.embed([Q_INSTRUCT + question], use_cache=False)[0])
    if setting == 'orig':
        return d_orig, 'dist', None
    if setting == 'híbrido':
        fused = rrf_scored([[i for i, _ in d_orig], [i for i, _ in bm25_ranked(question)]])
        return fused, 'rrf', None
    # reescribir / multiquery necesitan la reescritura del LLM
    rw = llm.rewrite_legal(question)
    d_rw = dense_ranked(cur, tei.embed([Q_INSTRUCT + rw], use_cache=False)[0])
    if setting == 'reescribir':
        return d_rw, 'dist', rw
    if setting == 'multiquery':
        fused = rrf_scored([[i for i, _ in d_orig], [i for i, _ in d_rw]])
        return fused, 'rrf', rw
    raise ValueError(f'setting desconocido: {setting!r} (usa {ASK_SETTINGS})')


def ask(question, setting, k=5, system=None):
    if not (question or '').strip():
        raise ValueError('pregunta vacía')
    if setting not in ASK_SETTINGS:
        raise ValueError(f'setting desconocido: {setting!r} (usa {ASK_SETTINGS})')
    t0 = time.time()
    with connect() as c, c.cursor() as cur:
        scored, score_kind, rw = retrieve_scored(cur, question, setting)
    top = [{'id': cid, 'rank': rank, 'score': round(score, 4), 'score_kind': score_kind,
            **DOC_BY_ID.get(cid, {})}
           for rank, (cid, score) in enumerate(scored[:k], 1)]
    context = '\n\n'.join(
        f"[{ch['rank']}] Fuente: {ch.get('source', '')} — {ch.get('hierarchy') or ch.get('title', '')}\n{ch.get('text', '')}"
        for ch in top)
    answer = llm.chat((system or ASK_SYSTEM).strip() or ASK_SYSTEM,
                      f'CONTEXTO:\n{context}\n\nPREGUNTA: {question}',
                      max_tokens=4096, timeout=180)
    return {'answer': answer, 'rewrite': rw, 'setting': setting, 'score_kind': score_kind,
            'question': question, 'chunks': top, 'seconds': round(time.time() - t0, 1)}


# ── Tab "Conversacional" ──────────────────────────────────────────────────────────
# Chat multi-turno: el historial completo se manda al LLM (para que entienda preguntas
# de seguimiento), pero el retrieval RAG se hace SOLO sobre el último mensaje del
# usuario; los chunks devueltos son los de esa última pregunta (no se acumulan). El
# historial de conversaciones vive en el browser (IndexedDB), no en el servidor.
def chat_answer(messages, setting, k=5, system=None):
    if setting not in ASK_SETTINGS:
        raise ValueError(f'setting desconocido: {setting!r} (usa {ASK_SETTINGS})')
    msgs = [m for m in (messages or []) if m.get('role') in ('user', 'assistant') and (m.get('content') or '').strip()]
    if not msgs or msgs[-1]['role'] != 'user':
        raise ValueError('el último mensaje debe ser del usuario')
    question = msgs[-1]['content'].strip()
    t0 = time.time()
    with connect() as c, c.cursor() as cur:   # retrieval SOLO de la última pregunta
        scored, score_kind, rw = retrieve_scored(cur, question, setting)
    top = [{'id': cid, 'rank': rank, 'score': round(score, 4), 'score_kind': score_kind,
            **DOC_BY_ID.get(cid, {})}
           for rank, (cid, score) in enumerate(scored[:k], 1)]
    context = '\n\n'.join(
        f"[{ch['rank']}] Fuente: {ch.get('source', '')} — {ch.get('hierarchy') or ch.get('title', '')}\n{ch.get('text', '')}"
        for ch in top)
    # El contexto RAG se inyecta en el ÚLTIMO turno del usuario; los turnos previos van
    # tal cual para dar memoria conversacional al LLM.
    llm_msgs = [{'role': 'system', 'content': (system or ASK_SYSTEM).strip() or ASK_SYSTEM}]
    llm_msgs += [{'role': m['role'], 'content': m['content']} for m in msgs[:-1]]
    llm_msgs.append({'role': 'user', 'content': f'CONTEXTO:\n{context}\n\nPREGUNTA: {question}'})
    answer = llm.chat_messages(llm_msgs, max_tokens=4096, timeout=180)
    return {'answer': answer, 'rewrite': rw, 'setting': setting, 'score_kind': score_kind,
            'question': question, 'chunks': top, 'seconds': round(time.time() - t0, 1)}


load_corpus_index()   # índice BM25 en memoria para la tab de RAG (bm25 / híbrido)

# Gestor de ingesta de PDFs (tab "Ingestar"). Comparte tabla, TEI y conexión con el
# resto del app; al terminar recarga el índice en memoria para que los chunks nuevos
# sean buscables de inmediato en la tab de RAG.
ingest_mgr = IngestManager(table=TABLE, tei=tei, connect_fn=connect,
                           clean_dir=CLEAN_DIR, upload_dir=UPLOAD_DIR,
                           on_complete=load_corpus_index)

app = FastAPI(title='Rewrite Lab')

# Puerta de autenticación con Google (primer paso de acceso). En local, si no hay
# credenciales configuradas, no se instala y el app queda abierto como antes.
from auth import install_auth  # noqa: E402  (import local del app, tras crear `app`)

install_auth(app)


@app.get('/healthz')
def healthz():
    return {'ok': True}


# Rutas "profundas" por tab: todas sirven el MISMO SPA (index.html); el front lee
# location.pathname y abre el tab correcto. Permite enlaces directos y compartibles:
#   /consulta → Preguntar (RAG) · /lab → Rewrite Lab · /ingesta → Ingestar
@app.get('/')
@app.get('/consulta')
@app.get('/lab')
@app.get('/ingesta')
@app.get('/conversacional')
def index():
    # no-store: el navegador no cachea el HTML, para que los cambios se vean sin hard-refresh.
    return FileResponse(STATIC / 'index.html', headers={'Cache-Control': 'no-store'})


@app.get('/api/config')
def config():
    return {'default_prompt': REWRITE_SYSTEM, 'table': TABLE,
            'goldens': list_goldens(), 'default_golden': DEFAULT_GOLDEN,
            'ask_settings': ASK_SETTINGS, 'ask_system': ASK_SYSTEM}


@app.get('/api/questions')
def api_questions(golden: str = ''):
    """Preguntas de un golden set, para el dropdown de la tab de RAG."""
    ds = get_dataset(golden or DEFAULT_GOLDEN)
    return [{'i': i, 'q': g['q'], 'difficulty': g.get('difficulty', '')}
            for i, g in enumerate(ds['golden'])]


# ── Tab "Ingestar documentos" ─────────────────────────────────────────────────────
# Sube uno o varios PDFs → genera Markdown → limpieza (se guarda el .md limpio para
# visualizar) → chunking por estructura (estrategia auto por documento) → embeddings
# (TEI en rtx5090) → upsert por documento en pgvector. Corre en segundo plano; la UI
# consulta el progreso por polling. Toda la lógica vive en `ingest_service`.
@app.post('/ingest/upload')
async def ingest_upload(files: list[UploadFile] = File(...)):
    pdfs = [f for f in files if (f.filename or '').lower().endswith('.pdf')]
    if not pdfs:
        return JSONResponse({'error': 'Sube al menos un archivo .pdf'}, status_code=400)
    # Guardar en un subdirectorio único por subida y con el nombre ORIGINAL: así el
    # `source` del documento sale del nombre real del PDF (no de un nombre temporal),
    # y a la vez se evita cualquier colisión entre subidas concurrentes.
    job_dir = UPLOAD_DIR / uuid.uuid4().hex
    job_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    for f in pdfs:
        dest = job_dir / Path(f.filename).name
        dest.write_bytes(await f.read())
        saved.append(dest)
    try:
        job_id = ingest_mgr.start(saved)
    except RuntimeError as e:   # ya hay una ingesta en curso
        for p in saved:
            p.unlink(missing_ok=True)
        return JSONResponse({'error': str(e)}, status_code=409)
    return {'job_id': job_id}


@app.get('/ingest/status/{job_id}')
def ingest_status(job_id: str):
    job = ingest_mgr.status(job_id)
    if job is None:
        return JSONResponse({'error': 'job desconocido'}, status_code=404)
    return job


@app.get('/ingest/documents')
def ingest_documents():
    """Documentos ya presentes en la tabla (source + nº de chunks)."""
    return ingest_mgr.documents()


@app.get('/ingest/clean')
def ingest_clean(source: str):
    """Markdown limpio de un documento ya procesado, para visualizarlo en la UI."""
    try:
        return {'source': source, 'text': ingest_mgr.read_clean(source)}
    except FileNotFoundError as e:
        return JSONResponse({'error': str(e)}, status_code=404)


@app.post('/ask')
async def ask_route(req: Request):
    body = await req.json()
    try:
        return ask(body.get('question', ''), body.get('setting', 'orig'),
                   int(body.get('k', 5)), body.get('system'))
    except Exception as e:
        return JSONResponse({'error': f'{type(e).__name__}: {e}'})


@app.post('/chat')
async def chat_route(req: Request):
    """Turno de la tab Conversacional: recibe el historial y responde con RAG sobre la
    última pregunta. El historial se guarda en el browser (IndexedDB), no aquí."""
    body = await req.json()
    try:
        return chat_answer(body.get('messages', []), body.get('setting', 'orig'),
                           int(body.get('k', 5)), body.get('system'))
    except Exception as e:
        return JSONResponse({'error': f'{type(e).__name__}: {e}'})


@app.post('/run')
async def run(req: Request):
    body = await req.json()
    try:
        return eval_prompt(body.get('prompt') or REWRITE_SYSTEM,
                           body.get('subset', 'hard'),
                           body.get('golden') or DEFAULT_GOLDEN)
    except Exception as e:
        return JSONResponse({'error': f'{type(e).__name__}: {e}'})


@app.post('/save')
async def save(req: Request):
    """Guarda una corrida (con su prompt) para poder compararla después."""
    b = await req.json()
    r = b.get('result') or {}
    with connect() as c, c.cursor() as cur:
        cur.execute(
            f"INSERT INTO {RUNS_TABLE} (label, prompt, subset, golden, n, metrics, rows) "
            f"VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb) RETURNING id",
            (b.get('label') or 'sin nombre', b.get('prompt', ''), b.get('subset', ''),
             b.get('golden') or r.get('golden', ''),
             r.get('n', 0), json.dumps(r.get('agg', {})), json.dumps(r.get('rows', []))))
        rid = cur.fetchone()[0]
        c.commit()
    return {'id': rid}


@app.get('/runs')
def runs():
    """Lista de corridas guardadas (sin el detalle pesado)."""
    with connect() as c, c.cursor() as cur:
        cur.execute(f"SELECT id, created_at::text, label, subset, golden, n, metrics "
                    f"FROM {RUNS_TABLE} ORDER BY id DESC")
        cols = ['id', 'created_at', 'label', 'subset', 'golden', 'n', 'metrics']
        return [dict(zip(cols, row)) for row in cur.fetchall()]


@app.get('/runs/{rid}')
def run_detail(rid: int):
    with connect() as c, c.cursor() as cur:
        cur.execute(f"SELECT id, created_at::text, label, prompt, subset, golden, n, metrics, rows "
                    f"FROM {RUNS_TABLE} WHERE id = %s", (rid,))
        row = cur.fetchone()
    if not row:
        return JSONResponse({'error': 'no existe'}, status_code=404)
    cols = ['id', 'created_at', 'label', 'prompt', 'subset', 'golden', 'n', 'metrics', 'rows']
    return dict(zip(cols, row))


@app.delete('/runs/{rid}')
def run_delete(rid: int):
    with connect() as c, c.cursor() as cur:
        cur.execute(f"DELETE FROM {RUNS_TABLE} WHERE id = %s", (rid,))
        c.commit()
    return {'deleted': rid}


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host=os.environ.get('HOST', '127.0.0.1'), port=int(os.environ.get('PORT', 8050)))
