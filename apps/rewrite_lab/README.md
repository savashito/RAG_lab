# Rewrite Lab

Laboratorio web para **experimentar prompts de query rewriting** contra los modelos
locales (LLM en la rtx5090 + embedder TEI) y la base pgvector. Pegas un system-prompt,
eliges un set de preguntas del golden, y ves en vivo:

- la **reescritura** de cada pregunta,
- el **rank del gold chunk** con la consulta original, con la reescrita sola, y con
  multi-query (RRF), calculado con retrieval denso desde **pgvector**,
- métricas agregadas (`recall@k`, `MRR`) por método.

## Estructura

```
apps/rewrite_lab/
  main.py            # backend FastAPI (lógica + endpoints)
  static/index.html  # UI (se sirve estática; pide /api/config al cargar)
  README.md
```

Reusa la librería del repo: `shared/llm_client.py` (rewrite), `shared/tei_client.py`
(embeddings), `shared/lexical.py` (RRF), `shared/db.py` (pgvector). El prompt por
defecto es `shared.llm_client.REWRITE_SYSTEM`.

## Correr local (dev)

Con los túneles arriba (`./tunnel.sh`: Postgres + TEI + llama-server):

```bash
uv run uvicorn apps.rewrite_lab.main:app --reload --port 8050
# o:  uv run python apps/rewrite_lab/main.py
```

Abre http://localhost:8050

## Desplegar en tlacua.cloud

tlacua alcanza la rtx, así que no necesita túnel: apunta las URLs por env.

```bash
uv run uvicorn apps.rewrite_lab.main:app --host 0.0.0.0 --port 8050
```

### Variables de entorno

| var | default | qué es |
|---|---|---|
| `LLM_URL` | `http://localhost:41499` | llama-server (query rewriting) |
| `TEI_URL` | `http://localhost:8085` | embeddings (TEI) |
| `RAG_DB_*` | (ver `shared/db.py`) | Postgres/pgvector |
| `LEGAL_TABLE` | `sistema_penal__qwen06__legal` | tabla de vectores ya ingestada |
| `HOST` / `PORT` | `127.0.0.1` / `8050` | bind del servidor (usa `0.0.0.0` para exponerlo) |

En el server, en vez de `localhost`, `LLM_URL`/`TEI_URL` apuntan a como la rtx sea
alcanzable desde tlacua. Ponlo detrás de tu nginx/proxy y, si expones la UI,
agrégale la auth de tu app.

## Requisitos

- La tabla `LEGAL_TABLE` debe estar ingestada (`ingestion/legal_rag.py ingest`).
- El golden set en `exploracion_datos/golden_penal.json`.
