# Rewrite Lab

Laboratorio web con cuatro tabs:

1. **💬 Preguntar (RAG)** — recupera chunks y responde con el LLM local.
1. **🗨️ Conversacional** — chat **multi-turno** con el LLM. El historial de
   conversaciones se guarda **solo en el navegador** (IndexedDB, como la WebUI de
   llama.cpp), nunca en el servidor. El LLM recibe los turnos previos (memoria de la
   charla), pero el **retrieval RAG se hace únicamente sobre la última pregunta** del
   usuario y las fuentes mostradas son las de ese turno (no se acumulan). Barra lateral
   con lista de conversaciones (nueva / seleccionar / borrar) y selector de método +
   top-k. Endpoint: `POST /chat` (recibe `messages`, no persiste nada).
2. **Rewrite Lab** — **experimenta prompts de query rewriting**: pegas un
   system-prompt, eliges un golden set, y ves en vivo la reescritura, el rank del
   gold chunk (original / reescrita / multi-query, retrieval denso desde pgvector)
   y métricas agregadas (`recall@k`, `MRR`).
3. **📥 Ingestar documentos** — sube uno o varios **PDFs** legales y el app hace, en
   segundo plano, el pipeline completo: PDF → Markdown → **limpieza** (guarda el
   `.md` limpio para visualizarlo) → **chunking por estructura** (estrategia auto
   por documento) → **embeddings** (TEI, rtx5090) → **upsert por documento** en
   pgvector. Reporta, por documento, **qué estrategias se probaron y cuál ganó**
   (como el notebook de exploración) y refresca el índice en memoria para que los
   chunks nuevos sean buscables de inmediato en la tab de RAG. Aquí se elige el
   **tema** de la subida (o se crea uno nuevo); ver abajo.

## Segmentación por tema (tópicos)

El corpus se segmenta por **tema** para poder tener temas no relacionados en la misma
tabla (p. ej. *Derecho Penal*, *Derecho Mercantil*, *Root Apical Meristem*) y que la
búsqueda RAG se limite al tema que el usuario elija.

- Cada chunk lleva una columna **`topic`** en la tabla de vectores (Opción A: una tabla,
  filtro por `WHERE topic = %s`; BM25 se filtra en memoria por la misma metadata).
- El catálogo de temas vive en la tabla **`rewrite_lab_topics`** (`topic`, `label`,
  `instruct`). El **`instruct`** guarda **solo la TAREA** (la frase que describe qué se
  busca), por tema. El formato del modelo instruct-aware
  (`Instruct: <tarea>\nQuery: <pregunta>`) es una **plantilla fija en código**
  (`INSTRUCT_TEMPLATE` en `main.py`), igual para todos los temas — no se guarda ni se
  edita por tema. Así un tema en inglés usa la tarea *"Retrieve the passage…"* y uno legal
  *"Recupera el pasaje del código o la doctrina…"*, pero ambos se envuelven en el mismo
  `Instruct:/Query:`. Editar la tarea afecta solo consultas futuras; **no** re-embebe
  documentos (los documentos se embeben sin instrucción).
- Cada tema tiene además un **`system_prompt`** propio (columna en `rewrite_lab_topics`):
  la instrucción al **LLM** sobre cómo **redactar la respuesta** en ese tema (distinta del
  `instruct`, que es para la búsqueda). Al elegir un tema en Preguntar/Conversacional, su
  `system_prompt` se carga en el editor «⚙️ System prompt» (editable en vivo por sesión;
  el botón «Restaurar» vuelve al del tema). Si un tema no define uno, cae al `ASK_SYSTEM`
  global. Los tres conceptos son independientes: **instruct** (búsqueda) y **system
  prompt** (respuesta) viven por-tema en la tabla; **`Instruct:/Query:`** es plantilla fija
  en código; la **pregunta** la escribe el usuario en vivo.
- Los temas se **crean y editan desde el tab de Ingesta** («➕ Nuevo tema» / «✏️ Editar
  tema»: nombre + tarea de recuperación + system prompt). El id (slug) se deriva del nombre
  al crear y **no cambia** al editar.
- Los tabs **Preguntar** y **Conversacional** tienen un selector **Tema** y la búsqueda
  se restringe a él.
- **Migración automática al arrancar:** se añade la columna `topic` (idempotente), se
  crea el catálogo, y **todo lo ya insertado se etiqueta como `Derecho Penal Mexicano`**
  (`derecho_penal_mexicano`).

Endpoints: `GET /api/topics` (catálogo + nº de chunks), `POST /api/topics`
(`{label, instruct?}` — crea; el `instruct` es la tarea), `POST /api/topics/{topic}`
(`{label?, instruct?}` — edita; el slug no cambia). `POST /ask` y `POST /chat` aceptan
`topic`; `POST /ingest/upload` recibe el `topic` como campo de formulario.

> **Nota:** el tab **Rewrite Lab** (`/run`, evaluación con golden sets) **no** filtra por
> tema todavía — busca en toda la tabla. Es correcto mientras el único tema con datos
> sea el penal; si agregas otros temas y quieres que la evaluación se limite al penal,
> hay que pasarle el `topic` a `eval_prompt`/`dense_ids` (cambio chico).

## Estructura

```
apps/rewrite_lab/
  main.py            # backend FastAPI (lógica + endpoints)
  ingest_service.py  # gestor de jobs de ingesta en segundo plano (tab "Ingestar")
  static/index.html  # UI (se sirve estática; pide /api/config al cargar)
  README.md
```

Reusa la librería del repo: `shared/llm_client.py` (rewrite), `shared/tei_client.py`
(embeddings), `shared/lexical.py` (RRF), `shared/db.py` (pgvector) y el pipeline de
ingesta `ingestion/pipeline.py`. El prompt por defecto es
`shared.llm_client.REWRITE_SYSTEM`.

> **Dependencias del tab de ingesta:** la conversión PDF→Markdown usa el extra
> `parse` (pymupdf4llm). El app necesita, además del core (`pandas`,
> `python-multipart`), ese extra.
>
> - **En prod / para correr solo el app:** `uv sync --extra parse`. Instala core +
>   `parse` y **evita** el extra `embed` (torch/sentence-transformers, cientos de
>   MB) que el app no usa (embebe vía TEI remoto).
> - **En el laptop de dev, si trabajas otros labs a la vez:** `uv sync --all-extras`
>   (un `--extra parse` a secas reemplaza el set y desinstalaría `embed`, que esos
>   labs sí necesitan).
>
> **Deploy:** tras cada `git pull` que cambie dependencias, corre
> `uv sync --extra parse` **antes** de `systemctl restart legis-app`. Omitir el sync
> deja el venv desactualizado y el servicio no arranca (`ModuleNotFoundError`).

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
| `LLM_URL` | `http://localhost:1237` | llama-server (query rewriting) |
| `TEI_URL` | `http://localhost:8085` | embeddings (TEI) |
| `RAG_DB_*` | (ver `shared/db.py`) | Postgres/pgvector |
| `LEGAL_TABLE` | `sistema_penal__qwen06__legal` | tabla de vectores (destino del upsert del tab de ingesta) |
| `CLEAN_MD_DIR` | `ingestion/out_clean/Sistema Penal Acusatorio` | dónde persisten los `.md` limpios (visualizables) |
| `UPLOAD_DIR` | `ingestion/.uploads` | dónde caen los PDFs subidos (temporales) |
| `HOST` / `PORT` | `127.0.0.1` / `8050` | bind del servidor (usa `0.0.0.0` para exponerlo) |

En el server, en vez de `localhost`, `LLM_URL`/`TEI_URL` apuntan a como la rtx sea
alcanzable desde tlacua. Ponlo detrás de tu nginx/proxy y, si expones la UI,
agrégale la auth de tu app.

## Requisitos

- La tabla `LEGAL_TABLE` debe estar ingestada (`ingestion/legal_rag.py ingest`).

