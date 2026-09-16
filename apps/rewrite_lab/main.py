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
import re
import sys
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
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
from shared.legal_chunking import find_article_ref
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
# Modelos de embeddings instruction-aware: la consulta se embebe como
# "Instruct: <tarea>\nQuery: <pregunta>". La PLANTILLA es fija (convención del modelo,
# igual para todos los temas); lo único que cambia por tópico es la TAREA (la frase).
# Por eso la tabla de tópicos guarda solo la tarea, no el prefijo completo.
INSTRUCT_TEMPLATE = 'Instruct: {task}\nQuery: '
DEFAULT_TASK = 'Recupera el pasaje del código o la doctrina que responde la pregunta.'
Q_INSTRUCT = INSTRUCT_TEMPLATE.format(task=DEFAULT_TASK)   # prefijo completo (lo usa el eval)


def query_prefix(task: str) -> str:
    """Prefijo completo de consulta a partir de la tarea del tópico."""
    return INSTRUCT_TEMPLATE.format(task=(task or DEFAULT_TASK).strip())


def _task_only(instruct: str) -> str:
    """Normaliza valores legacy: si guardaban el prefijo completo
    'Instruct: <tarea>\\nQuery:', devuelve solo <tarea>. Si ya es la tarea, no toca nada."""
    s = (instruct or '').strip()
    if s.startswith('Instruct:'):
        s = s[len('Instruct:'):]
        i = s.rfind('Query:')
        if i != -1:
            s = s[:i]
    return s.strip()
KS = (5, 10, 20)
N_DENSE = 1500   # profundidad del ranking denso traído de pgvector para calcular el rank

# ── Tópicos ────────────────────────────────────────────────────────────────────────
# Segmentación por tema: cada chunk lleva una columna `topic`, y la búsqueda RAG filtra
# por el tema elegido. El `instruct` (prefijo de la consulta antes de embeber) se guarda
# POR TÓPICO en un catálogo (tabla `rewrite_lab_topics`), no por chunk. Los documentos ya
# insertados se asignan al tópico por defecto (Derecho Penal Mexicano).
DEFAULT_INSTRUCT = DEFAULT_TASK   # la tabla guarda la TAREA; este es su valor por defecto
TOPICS_TABLE = 'rewrite_lab_topics'
DEFAULT_TOPIC = 'derecho_penal_mexicano'
DEFAULT_TOPIC_LABEL = 'Derecho Penal Mexicano'

# ── Jurisdicción ("lugar") ───────────────────────────────────────────────────────
# Dimensión ORTOGONAL al tópico: el tópico es la materia (penal, familiar…), la
# jurisdicción es el lugar/ámbito del documento. El mismo nº de artículo existe en
# varios códigos; sin este filtro el retrieval compite entre todos. Cada chunk lleva la
# columna `jurisdiction`. 'general' = doctrina sin jurisdicción (se incluye siempre).
JURISDICTIONS = {
    'federal': 'Federal',
    'queretaro': 'Querétaro',
    'cdmx': 'Ciudad de México',
    'edomex': 'Estado de México',
    'nacional': 'Nacional (procedimientos)',
    'general': 'General / Doctrina',
}
DEFAULT_JURISDICTION = 'general'
# Backfill de los documentos ya ingeridos: se deriva el lugar del nombre del archivo.
# El orden importa (lo más específico primero). Lo no reconocido queda 'general'.
JURISDICTION_BY_SOURCE = [
    ('Quer', 'queretaro'), ('Ciudad de M', 'cdmx'), ('Estado de M', 'edomex'),
    ('Nacional de Proced', 'nacional'), ('Federal', 'federal'),
]


def jurisdiction_for_source(source: str) -> str:
    for needle, code in JURISDICTION_BY_SOURCE:
        if needle.lower() in (source or '').lower():
            return code
    return 'general'


def _jur_set(jurisdictions):
    """Normaliza la selección de lugares (lista de ids, o un str suelto) a un `set`, o None
    (= sin filtro, todo el corpus). La búsqueda filtra EXACTAMENTE por lo seleccionado; la
    'inteligencia' de qué acompaña a qué (estado → +federal +CNPP +doctrina) vive en la
    pre-selección de la UI, para que el usuario pueda ajustarla. 'todos' o vacío = None."""
    if isinstance(jurisdictions, str):
        jurisdictions = [jurisdictions]
    if not jurisdictions or 'todos' in jurisdictions:
        return None
    vals = {j for j in jurisdictions if j in JURISDICTIONS}
    return vals or None


def _jur_sql(jset):
    """Fragmento WHERE + params para el `set` de lugares (incluye NULL = sin etiquetar)."""
    if not jset:
        return '', []
    inc = sorted(jset)
    return f"(jurisdiction IN ({','.join(['%s'] * len(inc))}) OR jurisdiction IS NULL)", inc


def _jur_match(jset, chunk_jur) -> bool:
    """Versión en memoria de `_jur_sql`, para filtrar BM25 por metadata."""
    return not jset or chunk_jur is None or chunk_jur in jset


# ── Usuarios y roles ─────────────────────────────────────────────────────────────
# La lista blanca vive en la tabla `rewrite_lab_users` (antes en ALLOWED_EMAILS del
# .env). Cada usuario tiene un rol:
#   reader     — solo lee/pregunta (no ve el tab de ingesta).
#   admin      — además sube documentos: a los tópicos que él creó (owner) y a los que
#                el superadmin le asigne (tabla de grants).
#   superadmin — todo, incluida la gestión de usuarios (tab exclusivo). Se re-siembra
#                al arrancar para no quedar nunca fuera aunque borren su fila.
USERS_TABLE = 'rewrite_lab_users'
TOPIC_GRANTS_TABLE = 'rewrite_lab_topic_grants'
SUPERADMIN_EMAIL = os.environ.get('SUPERADMIN_EMAIL', 'rodrigosavagerower@gmail.com').strip().lower()
# Correos del .env: solo para SEMBRAR la tabla la 1a vez (como lectores). Después manda la DB.
ALLOWED_EMAILS_SEED = {e.strip().lower() for e in os.environ.get('ALLOWED_EMAILS', '').split(',') if e.strip()}
ROLES = ('reader', 'admin', 'superadmin')


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


def dense_ids(cur, qvec, topic=None) -> list[int]:
    """Ranking denso desde pgvector, reusando el cursor que le pasen (una conexión
    por corrida, no una por query). Si `topic`, restringe la búsqueda a ese tópico."""
    if topic:
        cur.execute(f"SELECT id FROM {TABLE} WHERE topic = %s ORDER BY embedding <=> %s LIMIT %s",
                    (topic, qvec, N_DENSE))
    else:
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
    # Segmentación por tópico: columna en la tabla de vectores + catálogo de tópicos.
    _cur.execute(f"ALTER TABLE {TABLE} ADD COLUMN IF NOT EXISTS topic text")
    _cur.execute(f"CREATE INDEX IF NOT EXISTS {TABLE}_topic ON {TABLE} (topic)")
    # Jurisdicción ("lugar"): columna + índice + backfill por nombre de archivo (una vez;
    # no pisa lo ya asignado). Los documentos sin regla reconocida quedan 'general'.
    _cur.execute(f"ALTER TABLE {TABLE} ADD COLUMN IF NOT EXISTS jurisdiction text")
    _cur.execute(f"CREATE INDEX IF NOT EXISTS {TABLE}_jurisdiction ON {TABLE} (jurisdiction)")
    _cur.execute(f"SELECT DISTINCT source FROM {TABLE} WHERE jurisdiction IS NULL")
    for (_src,) in _cur.fetchall():
        _cur.execute(f"UPDATE {TABLE} SET jurisdiction = %s WHERE source = %s AND jurisdiction IS NULL",
                     (jurisdiction_for_source(_src), _src))
    _cur.execute(f"""CREATE TABLE IF NOT EXISTS {TOPICS_TABLE} (
        topic text PRIMARY KEY, label text NOT NULL, instruct text NOT NULL,
        created_at timestamptz DEFAULT now())""")
    # system_prompt por tópico (instrucción del LLM al RESPONDER; distinta del instruct
    # de búsqueda). Se rellena con el default global más abajo, cuando ASK_SYSTEM existe.
    _cur.execute(f"ALTER TABLE {TOPICS_TABLE} ADD COLUMN IF NOT EXISTS system_prompt text")
    # Semilla del tópico por defecto y backfill de lo ya insertado (que tenía topic NULL).
    _cur.execute(f"INSERT INTO {TOPICS_TABLE} (topic, label, instruct) VALUES (%s, %s, %s) "
                 f"ON CONFLICT (topic) DO NOTHING",
                 (DEFAULT_TOPIC, DEFAULT_TOPIC_LABEL, DEFAULT_INSTRUCT))
    _cur.execute(f"UPDATE {TABLE} SET topic = %s WHERE topic IS NULL", (DEFAULT_TOPIC,))
    # Normaliza a "solo tarea" cualquier `instruct` legacy que guardara el prefijo completo.
    _cur.execute(f"SELECT topic, instruct FROM {TOPICS_TABLE}")
    for _t, _ins in _cur.fetchall():
        _clean = _task_only(_ins)
        if _clean != _ins:
            _cur.execute(f"UPDATE {TOPICS_TABLE} SET instruct = %s WHERE topic = %s", (_clean, _t))

    # ── Usuarios / roles / permisos de subida por tópico ────────────────────────────
    _cur.execute(f"""CREATE TABLE IF NOT EXISTS {USERS_TABLE} (
        email text PRIMARY KEY, role text NOT NULL DEFAULT 'reader',
        name text, created_at timestamptz DEFAULT now())""")
    # Dueño del tópico: un admin puede subir a los tópicos que él creó.
    _cur.execute(f"ALTER TABLE {TOPICS_TABLE} ADD COLUMN IF NOT EXISTS owner_email text")
    # Permisos extra: el superadmin asigna a un admin tópicos que NO creó pero puede subir.
    _cur.execute(f"""CREATE TABLE IF NOT EXISTS {TOPIC_GRANTS_TABLE} (
        email text NOT NULL, topic text NOT NULL,
        created_at timestamptz DEFAULT now(), PRIMARY KEY (email, topic))""")
    # Superadmin siempre existe (aunque borren su fila) y el tópico por defecto es suyo.
    _cur.execute(f"INSERT INTO {USERS_TABLE} (email, role, name) VALUES (%s, 'superadmin', %s) "
                 f"ON CONFLICT (email) DO UPDATE SET role = 'superadmin'",
                 (SUPERADMIN_EMAIL, 'Super Admin'))
    _cur.execute(f"UPDATE {TOPICS_TABLE} SET owner_email = %s WHERE owner_email IS NULL",
                 (SUPERADMIN_EMAIL,))
    # Siembra 1a-vez: los correos que estaban en ALLOWED_EMAILS entran como lectores.
    for _e in ALLOWED_EMAILS_SEED:
        if _e != SUPERADMIN_EMAIL:
            _cur.execute(f"INSERT INTO {USERS_TABLE} (email, role) VALUES (%s, 'reader') "
                         f"ON CONFLICT (email) DO NOTHING", (_e,))
    _c.commit()

# Catálogo de tópicos en memoria: topic -> {'label':..., 'instruct':...}. Se recarga al
# arrancar, al crear un tópico y al terminar una ingesta.
TOPICS: dict[str, dict] = {}


def load_topics():
    global TOPICS
    with connect() as c, c.cursor() as cur:
        cur.execute(f"SELECT topic, label, instruct, system_prompt FROM {TOPICS_TABLE} ORDER BY created_at")
        TOPICS = {t: {'label': lb, 'instruct': ins, 'system_prompt': sp}
                  for t, lb, ins, sp in cur.fetchall()}
    return TOPICS


# ── Usuarios en memoria + permisos ──────────────────────────────────────────────────
# Caché email -> {'role','name'}. Se recarga al arrancar y tras cualquier cambio de
# usuarios/roles, para que la puerta de auth y los permisos reflejen los cambios sin
# reiniciar. El superadmin se fuerza aunque falte la fila.
USERS: dict[str, dict] = {}


def load_users():
    global USERS
    with connect() as c, c.cursor() as cur:
        cur.execute(f"SELECT email, role, name FROM {USERS_TABLE}")
        USERS = {e.lower(): {'role': r, 'name': n} for e, r, n in cur.fetchall()}
    USERS.setdefault(SUPERADMIN_EMAIL, {'role': 'superadmin', 'name': 'Super Admin'})
    USERS[SUPERADMIN_EMAIL]['role'] = 'superadmin'   # nunca se degrada
    return USERS


def is_allowed(email) -> bool:
    """¿El correo está en la lista blanca (o es el superadmin)? Lo usa la puerta de auth."""
    e = (email or '').lower()
    return e == SUPERADMIN_EMAIL or e in USERS


def role_of(email) -> str:
    e = (email or '').lower()
    if e == SUPERADMIN_EMAIL:
        return 'superadmin'
    return (USERS.get(e) or {}).get('role', 'reader')


def can_ingest(email) -> bool:
    return role_of(email) in ('admin', 'superadmin')


def is_superadmin(email) -> bool:
    return role_of(email) == 'superadmin'


def allowed_topics_for(email) -> list[str]:
    """Tópicos a los que este usuario puede SUBIR: superadmin=todos; admin=los que creó
    (owner) + los que el superadmin le asignó; reader=ninguno."""
    e = (email or '').lower()
    if is_superadmin(e):
        return list(TOPICS.keys())
    if role_of(e) != 'admin':
        return []
    with connect() as c, c.cursor() as cur:
        cur.execute(f"SELECT topic FROM {TOPICS_TABLE} WHERE lower(owner_email) = %s", (e,))
        owned = {t for (t,) in cur.fetchall()}
        cur.execute(f"SELECT topic FROM {TOPIC_GRANTS_TABLE} WHERE lower(email) = %s", (e,))
        granted = {t for (t,) in cur.fetchall()}
    return [t for t in TOPICS if t in (owned | granted)]


def can_upload_topic(email, topic) -> bool:
    return is_superadmin(email) or topic in allowed_topics_for(email)


def current_email(request) -> str | None:
    """Correo del usuario logueado. Si el auth está desactivado (dev local sin
    credenciales), se actúa como superadmin para no bloquear el desarrollo."""
    if not AUTH_ON:
        return SUPERADMIN_EMAIL
    return ((request.session.get('user') or {}).get('email') or '').lower() or None


def instruct_for(topic) -> str:
    """Tarea de recuperación del tópico (frase para el 'Instruct:'), o el default si no
    existe. El prefijo completo se arma con `query_prefix`."""
    return (TOPICS.get(topic) or {}).get('instruct') or DEFAULT_INSTRUCT


def system_for(topic) -> str:
    """System prompt del tópico (instrucción al LLM al responder), o el default global
    ASK_SYSTEM si el tópico no tiene uno."""
    return (TOPICS.get(topic) or {}).get('system_prompt') or ASK_SYSTEM


def slugify(text) -> str:
    """Etiqueta legible → slug ascii para usar como id de tópico."""
    import re
    import unicodedata
    s = unicodedata.normalize('NFKD', text or '').encode('ascii', 'ignore').decode()
    s = re.sub(r'[^a-zA-Z0-9]+', '_', s).strip('_').lower()
    return s or 'tema'


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
load_topics()
print(f'Tópicos: {list(TOPICS)}')
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
# Rellena el system_prompt de los tópicos que no tengan uno (incl. el default penal, que
# se creó antes de que ASK_SYSTEM estuviera disponible en el arranque) y recarga la caché.
with connect() as _c, _c.cursor() as _cur:
    _cur.execute(f"UPDATE {TOPICS_TABLE} SET system_prompt = %s WHERE system_prompt IS NULL",
                 (ASK_SYSTEM,))
    _c.commit()
load_topics()
DOC_BY_ID: dict[int, dict] = {}   # id -> {source,title,hierarchy,text}
BM_IDS: list[int] = []            # índice del corpus -> id de la BD (para mapear BM25)
BM25_INDEX: BM25 | None = None


def load_corpus_index():
    """Carga todos los chunks (id, metadatos, texto) y construye el índice BM25."""
    global BM25_INDEX, BM_IDS, DOC_BY_ID
    with connect() as c, c.cursor() as cur:
        cur.execute(f'SELECT id, source, title, hierarchy, text, topic, jurisdiction FROM {TABLE} ORDER BY id')
        rows = cur.fetchall()
    BM_IDS = [r[0] for r in rows]
    DOC_BY_ID = {r[0]: {'source': r[1], 'title': r[2], 'hierarchy': r[3], 'text': r[4],
                        'topic': r[5], 'jurisdiction': r[6]} for r in rows}
    BM25_INDEX = BM25([tokenize(r[4]) for r in rows])
    print(f'Índice léxico BM25: {len(BM_IDS)} chunks en memoria.')


# ── Recuperación con score por chunk ─────────────────────────────────────────────
# Cada método devuelve una lista [(id, score)] y una etiqueta de qué significa el
# score, para poder mostrarlo en la UI:
#   dist  → distancia coseno de pgvector (menor = más cercano)
#   bm25  → score léxico BM25 (mayor = mejor)
#   rrf   → score de Reciprocal Rank Fusion (mayor = mejor)
def _scope_sql(topic, jset):
    """WHERE + params combinando tópico y el set de lugares (ambos opcionales)."""
    clauses, params = [], []
    if topic:
        clauses.append("topic = %s"); params.append(topic)
    frag, p = _jur_sql(jset)
    if frag:
        clauses.append(frag); params += p
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


def dense_ranked(cur, qvec, topic=None, jset=None):
    where, params = _scope_sql(topic, jset)
    cur.execute(f"SELECT id, (embedding <=> %s) AS dist FROM {TABLE}{where} ORDER BY 2 LIMIT %s",
                [qvec, *params, N_DENSE])
    return [(r[0], float(r[1])) for r in cur.fetchall()]


def bm25_ranked(question, topic=None, jset=None):
    scores = BM25_INDEX.scores(tokenize(question))
    out = []
    for i in rank_indices_by_score(scores):
        cid = BM_IDS[i]
        meta = DOC_BY_ID.get(cid) or {}
        if topic and meta.get('topic') != topic:
            continue   # BM25 es un índice global; filtramos por tópico/lugar con la metadata
        if not _jur_match(jset, meta.get('jurisdiction')):
            continue
        out.append((cid, float(scores[i])))
    return out


def rrf_scored(ranked_id_lists, k=60):
    """RRF sobre listas de ids ya ordenadas; devuelve [(id, score)] ordenado desc."""
    agg: dict[int, float] = {}
    for lst in ranked_id_lists:
        for rank, i in enumerate(lst, 1):
            agg[i] = agg.get(i, 0.0) + 1.0 / (k + rank)
    return sorted(agg.items(), key=lambda kv: -kv[1])


# Etiquetas del dropdown -> lógica de recuperación.
ASK_SETTINGS = ['orig', 'reescribir', 'multiquery', 'bm25', 'híbrido']


# Pistas de código en la pregunta → patrón ILIKE del `source`, para desambiguar cuando el
# mismo número de artículo existe en varios códigos del tópico ("artículo 167 de Querétaro").
CODE_HINTS = [
    ('quer', '%Quer%'), ('cdmx', '%Ciudad de M%'), ('ciudad de m', '%Ciudad de M%'),
    ('estado de m', '%Estado de M%'), ('edomex', '%Estado de M%'),
    ('nacional de proced', '%Nacional de Proced%'), ('procedimientos', '%Nacional de Proced%'),
    ('cnpp', '%Nacional de Proced%'), ('federal', '%Federal%'),
]


def article_lookup(cur, question, topic, jset=None):
    """IDs de los chunks cuyo `title` coincide EXACTO con el artículo citado en la pregunta
    ('artículo 167' → title='Artículo 167'). Se acota por los lugares SELECCIONADOS si los
    hay; si no, por el código MENCIONADO en el texto (Querétaro, Federal…). Vacío si la
    pregunta no cita un artículo. Resuelve las consultas de referencia exacta que el denso falla."""
    label = find_article_ref(question)
    if not label:
        return []
    clauses, params = ["title = %s"], [label]
    if topic:
        clauses.append("topic = %s"); params.append(topic)
    if jset:
        frag, p = _jur_sql(jset)
        clauses.append(frag); params += p
    else:   # sin lugar seleccionado: intenta deducir el código del texto de la pregunta
        ql = (question or '').lower()
        src_like = next((v for k, v in CODE_HINTS if k in ql), None)
        if src_like:
            clauses.append("source ILIKE %s"); params.append(src_like)
    cur.execute(f"SELECT id FROM {TABLE} WHERE " + " AND ".join(clauses) + " ORDER BY source, position", params)
    return [r[0] for r in cur.fetchall()]


_ARTICLE_BASE_RE = re.compile(r'Art[íi]culo\s+(\d+)')


def _article_base(title):
    m = _ARTICLE_BASE_RE.search(title or '')
    return m.group(1) if m else None


def _source_families(cur, source, topic, jset):
    """Familias del documento en ORDEN DE LECTURA. Una familia = corrida contigua de
    unidades con el mismo número base (167, 167 BIS, 167 BIS 1, … SEPTIMUS = UNA familia;
    luego 168 = la siguiente). Agrupar por corrida —no solo por número— evita mezclar el
    artículo del cuerpo con un transitorio del mismo número (que aparece mucho después).
    Cada familia: {'base', 'pmin', 'pmax', 'ids': [...]}. Respeta el alcance topic/lugar."""
    clauses, params = ["source = %s"], [source]
    if topic:
        clauses.append("topic = %s"); params.append(topic)
    frag, p = _jur_sql(jset)
    if frag:
        clauses.append(frag); params += p
    cur.execute(f"SELECT id, position, title FROM {TABLE} WHERE " + " AND ".join(clauses)
                + " ORDER BY position, part", params)
    fams: list[dict] = []
    for cid, pos, title in cur.fetchall():
        base = _article_base(title)
        if fams and fams[-1]['base'] == base:
            fams[-1]['ids'].append(cid); fams[-1]['pmax'] = pos
        else:
            fams.append({'base': base, 'pmin': pos, 'pmax': pos, 'ids': [cid]})
    return fams


def _neighbor_groups(cur, anchor_ids, topic, jset, around=2):
    """Por cada ancla (en el ORDEN dado = ranking), devuelve su lista de ids vecinos ordenada
    por CERCANíA: primero su propia familia (bis/adendums), luego la familia de arriba y la de
    abajo (dist 1), después dist 2… Así, si hay que recortar, se conserva lo más cercano/relevante
    (para el 168, la familia 167 va antes que la 166). Alineada con `anchor_ids`."""
    if not anchor_ids:
        return []
    cur.execute(f"SELECT id, source, position FROM {TABLE} WHERE id = ANY(%s)", (list(anchor_ids),))
    info = {r[0]: (r[1], r[2]) for r in cur.fetchall()}   # el ANY() no respeta orden: reindexamos
    fams_cache: dict[str, list] = {}
    groups = []
    for aid in anchor_ids:                                 # preserva el orden del ranking
        if aid not in info:
            groups.append([]); continue
        source, position = info[aid]
        if source not in fams_cache:
            fams_cache[source] = _source_families(cur, source, topic, jset)
        fams = fams_cache[source]
        idx = next((i for i, f in enumerate(fams) if f['pmin'] <= position <= f['pmax']), None)
        if idx is None:
            groups.append([]); continue
        order = [idx]                                      # familia propia primero (sus bis)
        for d in range(1, around + 1):                     # luego, de cerca a lejos: arriba y abajo
            if idx - d >= 0:
                order.append(idx - d)
            if idx + d < len(fams):
                order.append(idx + d)
        groups.append([cid for fi in order for cid in fams[fi]['ids']])
    return groups


def expand_article_context(cur, exact_ids, topic, jset, around=2):
    """Familia + ±`around` familias de cada ancla, aplanado y sin duplicar (para la búsqueda
    directa por 'artículo N', donde queremos todo el contexto de la referencia)."""
    out, seen = [], set()
    for grp in _neighbor_groups(cur, exact_ids, topic, jset, around):
        for cid in grp:
            if cid not in seen:
                seen.add(cid); out.append(cid)
    return out


def _prepend_exact(scored, exact_ids):
    """Coloca los chunks de match EXACTO por número de artículo al principio (sin duplicar),
    conservando su score si ya venían en la lista. El resto queda igual, como contexto."""
    if not exact_ids:
        return scored
    score_map = dict(scored)
    exact = set(exact_ids)
    head = [(i, score_map.get(i, 0.0)) for i in exact_ids]
    return head + [(i, s) for i, s in scored if i not in exact]


NEIGHBOR_EXTRA_CAP = 8   # máx. chunks vecinos añadidos como contexto en preguntas temáticas


def select_context_ids(cur, scored, k, question, topic, jurisdictions, neighbors=True):
    """Ids finales para el contexto: el top-k + (en preguntas TEMáTICAS, sin cita de artículo)
    la familia + ±2 familias vecinas de los artículos del top como contexto ADICIONAL, sin
    desplazar la cobertura. El tope se REPARTE entre las anclas (para no perder amplitud entre
    entidades) y se prioriza lo más cercano de cada una. Con `neighbors=False` devuelve solo
    el top-k. Devuelve (ids_ordenados, set_extra)."""
    base = [cid for cid, _ in scored[:k]]
    if not neighbors or find_article_ref(question):
        return base, set()   # sin vecinos, o ya se expandió dentro de retrieve_scored
    art_ids = [cid for cid in base if (DOC_BY_ID.get(cid) or {}).get('title', '').startswith('Artículo ')]
    if not art_ids:
        return base, set()
    groups = _neighbor_groups(cur, art_ids, topic, _jur_set(jurisdictions))
    queues = [[cid for cid in grp if cid not in set(base)] for grp in groups]
    seen: set = set(base)
    chosen: list[int] = []
    share = max(2, NEIGHBOR_EXTRA_CAP // max(1, len([q for q in queues if q])))
    # Pasada 1: hasta `share` cercanos por ancla, en orden de ranking (reparte amplitud).
    for q in queues:
        taken = 0
        for cid in q:
            if len(chosen) >= NEIGHBOR_EXTRA_CAP or taken >= share:
                break
            if cid not in seen:
                seen.add(cid); chosen.append(cid); taken += 1
    # Pasada 2: rellena el tope con lo que quede (siempre por cercanía).
    for q in queues:
        for cid in q:
            if len(chosen) >= NEIGHBOR_EXTRA_CAP:
                break
            if cid not in seen:
                seen.add(cid); chosen.append(cid)
    # Ordena los vecinos elegidos por lectura (source, position) para un contexto legible.
    if chosen:
        cur.execute(f"SELECT id, source, position FROM {TABLE} WHERE id = ANY(%s)", (chosen,))
        pos = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
        chosen.sort(key=lambda cid: pos.get(cid, ('', 0)))
    return base + chosen, set(chosen)


def retrieve_scored(cur, question, setting, topic=None, jurisdictions=None,
                    neighbors=True, hyde=False):
    """Devuelve (lista[(id, score)], etiqueta_de_score, reescritura_o_None). Filtra por
    `topic` y por el conjunto de lugares `jurisdictions` (lista; vacío/'todos' = todo). Usa
    el `instruct` del tópico para embeber. Si la pregunta cita un artículo por número, ese
    chunk se ancla al principio (búsqueda directa por metadata).
    `neighbors`: consolidar familia + ±2 vecinos (togglea el padding, no el match exacto).
    `hyde`: enriquece el vector denso con un borrador hipotético del pasaje (arregla el
    desajuste de vocabulario: la pregunta nombra el delito, el artículo lo define)."""
    prefix = query_prefix(instruct_for(topic))   # "Instruct: <tarea del tópico>\nQuery: "
    jset = _jur_set(jurisdictions)               # set de lugares (o None = todos)
    exact = article_lookup(cur, question, topic, jset)   # match exacto por número
    # Consolida la familia (bis/adendums) y —si `neighbors`— trae ±2 artículos vecinos.
    exact = expand_article_context(cur, exact, topic, jset, around=2 if neighbors else 0)
    if setting == 'bm25':
        return _prepend_exact(bm25_ranked(question, topic, jset), exact), 'bm25', None
    # HyDE: embebe pregunta + borrador del pasaje. El léxico (BM25) sigue con la pregunta
    # real; el borrador solo mueve el vector denso hacia la conducta descrita.
    dense_text = question
    if hyde:
        try:
            passage = llm.hyde_passage(question)
            if passage:
                dense_text = f'{question}\n\n{passage}'
        except Exception:   # noqa: BLE001 — si el LLM falla, degradamos a denso normal
            pass
    d_orig = dense_ranked(cur, tei.embed([prefix + dense_text], use_cache=False)[0], topic, jset)
    if setting == 'orig':
        return _prepend_exact(d_orig, exact), 'dist', None
    if setting == 'híbrido':
        fused = rrf_scored([[i for i, _ in d_orig], [i for i, _ in bm25_ranked(question, topic, jset)]])
        return _prepend_exact(fused, exact), 'rrf', None
    # reescribir / multiquery necesitan la reescritura del LLM
    rw = llm.rewrite_legal(question)
    d_rw = dense_ranked(cur, tei.embed([prefix + rw], use_cache=False)[0], topic, jset)
    if setting == 'reescribir':
        return _prepend_exact(d_rw, exact), 'dist', rw
    if setting == 'multiquery':
        fused = rrf_scored([[i for i, _ in d_orig], [i for i, _ in d_rw]])
        return _prepend_exact(fused, exact), 'rrf', rw
    raise ValueError(f'setting desconocido: {setting!r} (usa {ASK_SETTINGS})')


def ask(question, setting, k=5, system=None, topic=None, jurisdictions=None,
        neighbors=True, hyde=False):
    if not (question or '').strip():
        raise ValueError('pregunta vacía')
    if setting not in ASK_SETTINGS:
        raise ValueError(f'setting desconocido: {setting!r} (usa {ASK_SETTINGS})')
    if find_article_ref(question):
        k = max(k, 8)   # deja espacio para la familia (bis) + los ±2 vecinos
    t0 = time.time()
    with connect() as c, c.cursor() as cur:
        scored, score_kind, rw = retrieve_scored(cur, question, setting, topic, jurisdictions, neighbors, hyde)
        ids, extra = select_context_ids(cur, scored, k, question, topic, jurisdictions, neighbors)
    score_map = dict(scored)
    top = [{'id': cid, 'rank': rank, 'score': (round(score_map[cid], 4) if cid in score_map else None),
            'score_kind': score_kind, 'neighbor': cid in extra, **DOC_BY_ID.get(cid, {})}
           for rank, cid in enumerate(ids, 1)]
    context = '\n\n'.join(
        f"[{ch['rank']}] Fuente: {ch.get('source', '')} — {ch.get('hierarchy') or ch.get('title', '')}\n{ch.get('text', '')}"
        for ch in top)
    answer = llm.chat((system or '').strip() or system_for(topic),
                      f'CONTEXTO:\n{context}\n\nPREGUNTA: {question}',
                      max_tokens=4096, timeout=180)
    return {'answer': answer, 'rewrite': rw, 'setting': setting, 'score_kind': score_kind,
            'question': question, 'chunks': top, 'seconds': round(time.time() - t0, 1)}


# ── Tab "Conversacional" ──────────────────────────────────────────────────────────
# Chat multi-turno: el historial completo se manda al LLM (para que entienda preguntas
# de seguimiento), pero el retrieval RAG se hace SOLO sobre el último mensaje del
# usuario; los chunks devueltos son los de esa última pregunta (no se acumulan). El
# historial de conversaciones vive en el browser (IndexedDB), no en el servidor.
def chat_answer(messages, setting, k=5, system=None, topic=None, jurisdictions=None,
                neighbors=True, hyde=False):
    if setting not in ASK_SETTINGS:
        raise ValueError(f'setting desconocido: {setting!r} (usa {ASK_SETTINGS})')
    msgs = [m for m in (messages or []) if m.get('role') in ('user', 'assistant') and (m.get('content') or '').strip()]
    if not msgs or msgs[-1]['role'] != 'user':
        raise ValueError('el último mensaje debe ser del usuario')
    question = msgs[-1]['content'].strip()
    if find_article_ref(question):
        k = max(k, 8)   # deja espacio para la familia (bis) + los ±2 vecinos
    t0 = time.time()
    with connect() as c, c.cursor() as cur:   # retrieval SOLO de la última pregunta
        scored, score_kind, rw = retrieve_scored(cur, question, setting, topic, jurisdictions, neighbors, hyde)
        ids, extra = select_context_ids(cur, scored, k, question, topic, jurisdictions, neighbors)
    score_map = dict(scored)
    top = [{'id': cid, 'rank': rank, 'score': (round(score_map[cid], 4) if cid in score_map else None),
            'score_kind': score_kind, 'neighbor': cid in extra, **DOC_BY_ID.get(cid, {})}
           for rank, cid in enumerate(ids, 1)]
    context = '\n\n'.join(
        f"[{ch['rank']}] Fuente: {ch.get('source', '')} — {ch.get('hierarchy') or ch.get('title', '')}\n{ch.get('text', '')}"
        for ch in top)
    # El contexto RAG se inyecta en el ÚLTIMO turno del usuario; los turnos previos van
    # tal cual para dar memoria conversacional al LLM.
    llm_msgs = [{'role': 'system', 'content': (system or '').strip() or system_for(topic)}]
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

load_users()   # lista blanca + roles en memoria (la usa la puerta de auth y los permisos)

# Puerta de autenticación con Google (primer paso de acceso). La lista blanca es la
# tabla de usuarios (`is_allowed`). En local, si no hay credenciales, no se instala y
# el app queda abierto (`AUTH_ON=False` → todo mundo actúa como superadmin).
from auth import install_auth  # noqa: E402  (import local del app, tras crear `app`)

AUTH_ON = install_auth(app, is_allowed=is_allowed)


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
@app.get('/admin')
def index():
    # no-store: el navegador no cachea el HTML, para que los cambios se vean sin hard-refresh.
    return FileResponse(STATIC / 'index.html', headers={'Cache-Control': 'no-store'})


@app.get('/api/me')
def api_me(request: Request):
    """Identidad y permisos del usuario logueado. El front lo usa para decidir qué tabs
    mostrar (ingesta solo admins, gestión de usuarios solo superadmin) y a qué tópicos
    permitir subir."""
    email = current_email(request)
    return {'email': email, 'role': role_of(email), 'name': (USERS.get(email) or {}).get('name', ''),
            'can_ingest': can_ingest(email), 'is_superadmin': is_superadmin(email),
            'allowed_topics': allowed_topics_for(email)}


@app.get('/api/config')
def config():
    return {'default_prompt': REWRITE_SYSTEM, 'table': TABLE,
            'goldens': list_goldens(), 'default_golden': DEFAULT_GOLDEN,
            'ask_settings': ASK_SETTINGS, 'ask_system': ASK_SYSTEM,
            'default_instruct': DEFAULT_INSTRUCT, 'default_topic': DEFAULT_TOPIC,
            'jurisdictions': [{'id': k, 'label': v} for k, v in JURISDICTIONS.items()],
            'default_jurisdiction': DEFAULT_JURISDICTION}


@app.get('/api/topics')
def api_topics():
    """Catálogo de tópicos (para los selectores de tema) con el nº de chunks de cada uno."""
    with connect() as c, c.cursor() as cur:
        cur.execute(f"SELECT topic, count(*) FROM {TABLE} GROUP BY topic")
        counts = {t: n for t, n in cur.fetchall()}
    return [{'topic': t, 'label': v['label'], 'instruct': v['instruct'],
             'system_prompt': v.get('system_prompt') or ASK_SYSTEM,
             'chunks': counts.get(t, 0)} for t, v in TOPICS.items()]


@app.post('/api/topics')
async def api_topic_create(req: Request):
    """Crea un tópico nuevo: {label, instruct?}. El id (slug) se deriva de la etiqueta.
    El `instruct` es el prefijo de consulta de ese tema (usa el default si viene vacío).
    Solo admins/superadmin; el creador queda como `owner_email` (podrá subir a su tópico)."""
    email = current_email(req)
    if not can_ingest(email):
        return JSONResponse({'error': 'Solo los administradores pueden crear tópicos.'}, status_code=403)
    b = await req.json()
    label = (b.get('label') or '').strip()
    if not label:
        return JSONResponse({'error': 'La etiqueta del tópico no puede estar vacía'}, status_code=400)
    topic = slugify(label)
    instruct = (b.get('instruct') or '').strip() or DEFAULT_INSTRUCT
    system_prompt = (b.get('system_prompt') or '').strip() or ASK_SYSTEM
    with connect() as c, c.cursor() as cur:
        cur.execute(f"SELECT 1 FROM {TOPICS_TABLE} WHERE topic = %s", (topic,))
        if cur.fetchone():
            return JSONResponse({'error': f'Ya existe un tópico con id {topic!r}'}, status_code=409)
        cur.execute(f"INSERT INTO {TOPICS_TABLE} (topic, label, instruct, system_prompt, owner_email) "
                    f"VALUES (%s, %s, %s, %s, %s)", (topic, label, instruct, system_prompt, email))
        c.commit()
    load_topics()
    return {'topic': topic, 'label': label, 'instruct': instruct, 'system_prompt': system_prompt}


@app.post('/api/topics/{topic}')
async def api_topic_update(topic: str, req: Request):
    """Edita un tópico existente: {label?, instruct?}. El id (slug) NO cambia. Editar la
    tarea (`instruct`) afecta solo a consultas futuras; no re-embebe documentos (los
    documentos se embeben sin instrucción)."""
    b = await req.json()
    sets, vals = [], []
    label = (b.get('label') or '').strip()
    if label:
        sets.append('label = %s'); vals.append(label)
    if 'instruct' in b:
        sets.append('instruct = %s'); vals.append((b.get('instruct') or '').strip() or DEFAULT_INSTRUCT)
    if 'system_prompt' in b:
        sets.append('system_prompt = %s'); vals.append((b.get('system_prompt') or '').strip() or ASK_SYSTEM)
    if not sets:
        return JSONResponse({'error': 'nada que actualizar'}, status_code=400)
    vals.append(topic)
    with connect() as c, c.cursor() as cur:
        cur.execute(f"SELECT 1 FROM {TOPICS_TABLE} WHERE topic = %s", (topic,))
        if not cur.fetchone():
            return JSONResponse({'error': f'tópico desconocido: {topic!r}'}, status_code=404)
        cur.execute(f"UPDATE {TOPICS_TABLE} SET {', '.join(sets)} WHERE topic = %s", vals)
        c.commit()
    load_topics()
    return {'topic': topic, **TOPICS.get(topic, {})}


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
async def ingest_upload(request: Request, files: list[UploadFile] = File(...),
                        topic: str = Form(DEFAULT_TOPIC),
                        jurisdiction: str = Form(DEFAULT_JURISDICTION)):
    email = current_email(request)
    if not can_ingest(email):
        return JSONResponse({'error': 'No tienes permiso para subir documentos.'}, status_code=403)
    pdfs = [f for f in files if (f.filename or '').lower().endswith('.pdf')]
    if not pdfs:
        return JSONResponse({'error': 'Sube al menos un archivo .pdf'}, status_code=400)
    if topic not in TOPICS:
        return JSONResponse({'error': f'Tópico desconocido: {topic!r}'}, status_code=400)
    if jurisdiction not in JURISDICTIONS:
        return JSONResponse({'error': f'Lugar desconocido: {jurisdiction!r}'}, status_code=400)
    if not can_upload_topic(email, topic):
        return JSONResponse({'error': f'No tienes permiso para subir al tópico {topic!r}. '
                             f'Pídele acceso al superadmin o sube a un tópico que hayas creado.'},
                            status_code=403)
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
        job_id = ingest_mgr.start(saved, topic, jurisdiction)
    except RuntimeError as e:   # ya hay una ingesta en curso
        for p in saved:
            p.unlink(missing_ok=True)
        return JSONResponse({'error': str(e)}, status_code=409)
    return {'job_id': job_id}


@app.post('/ingest/url')
async def ingest_url_route(request: Request):
    """Ingesta uno o varios LINKS: {urls: [...], topic}. Descarga y convierte a Markdown
    (HTML o PDF en línea) con el mismo pipeline que los PDFs. Mismas guardas de permiso."""
    email = current_email(request)
    if not can_ingest(email):
        return JSONResponse({'error': 'No tienes permiso para ingerir documentos.'}, status_code=403)
    b = await request.json()
    raw = b.get('urls') or b.get('url') or []
    if isinstance(raw, str):
        raw = raw.split()   # acepta URLs separadas por espacios/saltos de línea
    urls = [u.strip() for u in raw if u and u.strip()]
    bad = [u for u in urls if not (u.startswith('http://') or u.startswith('https://'))]
    if not urls:
        return JSONResponse({'error': 'Pega al menos un link (http/https).'}, status_code=400)
    if bad:
        return JSONResponse({'error': f'Links inválidos (deben empezar con http/https): {bad}'},
                            status_code=400)
    topic = (b.get('topic') or DEFAULT_TOPIC)
    if topic not in TOPICS:
        return JSONResponse({'error': f'Tópico desconocido: {topic!r}'}, status_code=400)
    jurisdiction = (b.get('jurisdiction') or DEFAULT_JURISDICTION)
    if jurisdiction not in JURISDICTIONS:
        return JSONResponse({'error': f'Lugar desconocido: {jurisdiction!r}'}, status_code=400)
    if not can_upload_topic(email, topic):
        return JSONResponse({'error': f'No tienes permiso para subir al tópico {topic!r}. '
                             f'Pídele acceso al superadmin o sube a un tópico que hayas creado.'},
                            status_code=403)
    try:
        job_id = ingest_mgr.start_urls(urls, topic, jurisdiction)
    except RuntimeError as e:   # ya hay una ingesta en curso
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
                   int(body.get('k', 5)), body.get('system'), body.get('topic'),
                   body.get('jurisdictions') or body.get('jurisdiction'),
                   bool(body.get('neighbors', True)), bool(body.get('hyde', False)))
    except Exception as e:
        return JSONResponse({'error': f'{type(e).__name__}: {e}'})


@app.post('/chat')
async def chat_route(req: Request):
    """Turno de la tab Conversacional: recibe el historial y responde con RAG sobre la
    última pregunta. El historial se guarda en el browser (IndexedDB), no aquí."""
    body = await req.json()
    try:
        return chat_answer(body.get('messages', []), body.get('setting', 'orig'),
                           int(body.get('k', 5)), body.get('system'), body.get('topic'),
                           body.get('jurisdictions') or body.get('jurisdiction'),
                           bool(body.get('neighbors', True)), bool(body.get('hyde', False)))
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


# ── Tab "Usuarios" (solo superadmin) ──────────────────────────────────────────────────
# Gestión de la lista blanca: alta/baja de usuarios, cambio de rol y asignación de
# tópicos a los que un admin puede subir (además de los que él mismo crea).
def _require_superadmin(request):
    """Devuelve None si es superadmin, o un JSONResponse 403 si no. (Guardia común.)"""
    if not is_superadmin(current_email(request)):
        return JSONResponse({'error': 'Solo el superadmin puede gestionar usuarios.'}, status_code=403)
    return None


@app.get('/api/admin/users')
def api_admin_users(request: Request):
    """Lista de usuarios con su rol, tópicos que crearon (owner) y tópicos asignados."""
    if (deny := _require_superadmin(request)) is not None:
        return deny
    with connect() as c, c.cursor() as cur:
        cur.execute(f"SELECT email, role, name, created_at::text FROM {USERS_TABLE} ORDER BY role, email")
        users = cur.fetchall()
        cur.execute(f"SELECT lower(owner_email), topic FROM {TOPICS_TABLE} WHERE owner_email IS NOT NULL")
        owned: dict[str, list] = {}
        for oe, t in cur.fetchall():
            owned.setdefault(oe, []).append(t)
        cur.execute(f"SELECT lower(email), topic FROM {TOPIC_GRANTS_TABLE}")
        granted: dict[str, list] = {}
        for ge, t in cur.fetchall():
            granted.setdefault(ge, []).append(t)
    return [{'email': e, 'role': r, 'name': n or '', 'created_at': ca,
             'owned': owned.get(e.lower(), []), 'granted': granted.get(e.lower(), []),
             'is_superadmin': e.lower() == SUPERADMIN_EMAIL}
            for e, r, n, ca in users]


@app.post('/api/admin/users')
async def api_admin_user_upsert(request: Request):
    """Alta o cambio de rol de un usuario: {email, role, name?}. El superadmin no se degrada."""
    if (deny := _require_superadmin(request)) is not None:
        return deny
    b = await request.json()
    email = (b.get('email') or '').strip().lower()
    role = (b.get('role') or 'reader').strip()
    name = (b.get('name') or '').strip()
    if '@' not in email:
        return JSONResponse({'error': 'Correo inválido.'}, status_code=400)
    if role not in ROLES:
        return JSONResponse({'error': f'Rol inválido: {role!r} (usa {ROLES}).'}, status_code=400)
    if email == SUPERADMIN_EMAIL and role != 'superadmin':
        return JSONResponse({'error': 'No puedes cambiar el rol del superadmin.'}, status_code=400)
    with connect() as c, c.cursor() as cur:
        cur.execute(f"INSERT INTO {USERS_TABLE} (email, role, name) VALUES (%s, %s, %s) "
                    f"ON CONFLICT (email) DO UPDATE SET role = EXCLUDED.role, "
                    f"name = COALESCE(NULLIF(EXCLUDED.name, ''), {USERS_TABLE}.name)",
                    (email, role, name))
        c.commit()
    load_users()
    return {'email': email, 'role': role, 'name': name}


@app.delete('/api/admin/users/{email}')
def api_admin_user_delete(email: str, request: Request):
    """Quita a un usuario de la lista blanca (pierde el acceso). El superadmin no se borra."""
    if (deny := _require_superadmin(request)) is not None:
        return deny
    email = email.strip().lower()
    if email == SUPERADMIN_EMAIL:
        return JSONResponse({'error': 'No puedes borrar al superadmin.'}, status_code=400)
    with connect() as c, c.cursor() as cur:
        cur.execute(f"DELETE FROM {USERS_TABLE} WHERE lower(email) = %s", (email,))
        cur.execute(f"DELETE FROM {TOPIC_GRANTS_TABLE} WHERE lower(email) = %s", (email,))
        c.commit()
    load_users()
    return {'deleted': email}


@app.post('/api/admin/users/{email}/grants')
async def api_admin_user_grants(email: str, request: Request):
    """Reemplaza los tópicos asignados a un admin: {topics: [...]}. Son tópicos a los que
    podrá subir además de los que él mismo cree (owner)."""
    if (deny := _require_superadmin(request)) is not None:
        return deny
    email = email.strip().lower()
    b = await request.json()
    topics = [t for t in (b.get('topics') or []) if t in TOPICS]
    with connect() as c, c.cursor() as cur:
        cur.execute(f"DELETE FROM {TOPIC_GRANTS_TABLE} WHERE lower(email) = %s", (email,))
        for t in topics:
            cur.execute(f"INSERT INTO {TOPIC_GRANTS_TABLE} (email, topic) VALUES (%s, %s) "
                        f"ON CONFLICT DO NOTHING", (email, t))
        c.commit()
    return {'email': email, 'granted': topics}


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host=os.environ.get('HOST', '127.0.0.1'), port=int(os.environ.get('PORT', 8050)))
