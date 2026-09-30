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
- Cada tema tiene también un **`hyde_prompt`** propio (columna en `rewrite_lab_topics`):
  la instrucción para que el LLM redacte el **borrador hipotético** del pasaje buscado
  cuando **HyDE** está activo. `hyde_for(topic)` lo usa; si el tema no define uno, cae al
  `HYDE_SYSTEM` global, que es **jurídico penal** — por eso en temas no jurídicos (p. ej.
  psicología) **hay que cambiarlo** o los borradores salen con vocabulario legal. Editable
  en el editor de temas (campo «3 · Prompt de HyDE»). Migración: al arrancar se añade la
  columna y se rellena con el HyDE penal para no cambiar lo existente.
- Los temas se **crean y editan desde el tab de Ingesta** («➕ Nuevo tema» / «✏️ Editar
  tema»: nombre + tarea de recuperación + system prompt + prompt de HyDE). El id (slug) se
  deriva del nombre al crear y **no cambia** al editar.
- Los tabs **Preguntar** y **Conversacional** tienen un selector **Tema** y la búsqueda
  se restringe a él.
- **Migración automática al arrancar:** se añade la columna `topic` (idempotente), se
  crea el catálogo, y **todo lo ya insertado se etiqueta como `Derecho Penal Mexicano`**
  (`derecho_penal_mexicano`).

Endpoints: `GET /api/topics` (catálogo + nº de chunks + `system_prompt`/`hyde_prompt`),
`POST /api/topics` (`{label, instruct?, system_prompt?, hyde_prompt?}` — crea),
`POST /api/topics/{topic}` (`{label?, instruct?, system_prompt?, hyde_prompt?}` — edita;
el slug no cambia). `POST /ask` y `POST /chat` aceptan `topic`; `POST /ingest/upload`
recibe el `topic` como campo de formulario.

> **Nota:** el tab **Rewrite Lab** (`/run`, evaluación con golden sets) **no** filtra por
> tema todavía — busca en toda la tabla. Es correcto mientras el único tema con datos
> sea el penal; si agregas otros temas y quieres que la evaluación se limite al penal,
> hay que pasarle el `topic` a `eval_prompt`/`dense_ids` (cambio chico).

## Página simple para usuarios finales (`/preguntar`)

Además de la UI completa (`/consulta`, con todos los controles), hay una **página
minimalista** en `/preguntar` (`static/preguntar.html`): solo un campo de pregunta, la
respuesta en streaming, un bloque **Referencias** (APA, ver abajo) y los **Fragmentos
consultados** (colapsado). **Sin dropdowns ni checkboxes** — toda la configuración va en
la **URL**, para armar una liga por caso de uso y compartirla. Está detrás del mismo login.

| Parámetro | Qué hace | Default | Valores |
|---|---|---|---|
| `tema` | tópico (slug) | `psicologia_conductual` | cualquier slug de `rewrite_lab_topics` |
| `k` | nº de fragmentos base | `5` | entero 1–20 (se acota) |
| `metodo` | método de recuperación | `orig` | `orig`, `reescribir`, `multiquery`, `bm25`, `híbrido` (o `hibrido`); inválido → `orig` |
| `jurisdiccion` | filtro de lugar | (todas) | coma-separado, ej. `federal,cdmx` |
| `vecinos` | incluir chunks vecinos | `true` | `true`/`false` |
| `HyDE` | borrador hipotético | `true` | `true`/`false` |
| `rerank` | reordenar (cross-encoder) | `false` | `true`/`false` (sin efecto si `RERANK_URL` vacío) |

Ejemplos:
`/preguntar?tema=derecho_penal_mexicano&k=10&jurisdiccion=federal` ·
`/preguntar?tema=psicologia_conductual&k=8&metodo=híbrido`

Usa `POST /ask/stream` (SSE). Para cambiar los defaults, edita el objeto `CFG` en
`static/preguntar.html`.

## Citas por documento (`rewrite_lab_citations`)

Tabla curada `source` → cadena **APA**, para que la bibliografía no dependa del OCR
(que a menudo pierde año/revista del machote). La página `/preguntar` la muestra como
bloque **Referencias** (deduplicado por documento) y el contexto que va al LLM usa la
cita en vez del nombre de archivo, así la respuesta cita mejor. Si un documento no tiene
cita, cae a su nombre `.md`.

- Esquema: `source text PK, apa text, needs_review bool, note text, updated_at`.
- La app la **lee a memoria al arrancar** (`load_citations`, `CITATIONS`) y crea la tabla
  si falta (`CREATE TABLE IF NOT EXISTS`). Se **administra por SQL** (no hay UI aún);
  editar una cita es un `UPDATE` y **requiere reiniciar** el servicio para recargar
  `CITATIONS` (o exponer un endpoint de reload — pendiente).
- Agregar/editar una cita:
  ```sql
  INSERT INTO rewrite_lab_citations (source, apa) VALUES ('<archivo>.md', '<cita APA>')
  ON CONFLICT (source) DO UPDATE SET apa = EXCLUDED.apa, updated_at = now();
  ```
- `needs_review = true` marca citas incompletas (falta año/revista que el PDF no traía).

## OCR de PDFs escaneados

Automático desde el tab de ingesta: `ingestion/pdf_triage.py` detecta por página si un PDF
está escaneado (o trae la capa de texto rota). Si es así, `ingestion/ocr_client.py` lo
manda al servicio **Docling + macOS Vision de la Mac mini** (`127.0.0.1:8095`, túnel
inverso), y el Markdown sigue el camino de siempre. Los PDFs digitales se convierten en el
VPS con `pymupdf4llm`. El reporte de cada archivo, y la lista del corpus, dicen dónde se
procesó (🖥️ VPS / 🍎 Mac mini). El VPS nunca hace OCR: si la Mac no responde, la
ingesta falla con un mensaje claro.

Configuración: `OCR_URL`, `OCR_TOKEN_FILE` (`~/.ocr_token`) y `OCR_MAX_WAIT` en
`.env.example`. Arquitectura, benchmark, operación y hallazgos:
[`ingestion/OCR_ESCANEADOS.md`](../../ingestion/OCR_ESCANEADOS.md).

## 🧪 Benchmark de respuestas (`/benchmark`)

Evalúa la **respuesta** del LLM, no solo el retrieval (eso lo mide el Rewrite Lab). Solo
admins ven el tab; editar un set requiere permiso sobre su tema. Código: `bench.py`
(backend) + `static/bench.js` (UI); pruebas en `tests/test_bench.py`.

- **Sets por tema**: cada set pertenece a un tema y sus preguntas se responden buscando
  solo en ese tema. Import/export en JSON (`rag-lab-bench/v1`).
- **Pregunta** = texto + respuesta de referencia opcional + **componentes** esperados:
  `must` (obligatorio: si falta, no pasa), `should` (suma, no reprueba), `must_not` (no
  debe aparecer: artículo equivocado, jurisprudencia inventada…). Cada uno con peso.
  Sin componentes pero con referencia → se evalúa un único `must` «coincide con la referencia».
- **Juez**: el LLM (Gemma-4B hoy; otro servidor con `JUDGE_URL`) recibe pregunta,
  componentes numerados (sin decirle cuáles son `must_not`) y la respuesta, y marca cada
  uno presente / parcial / ausente con una cita de evidencia. El score se calcula en código:
  `(Σ peso·valor must/should − Σ peso·valor must_not) / Σ peso must/should`.
- **Métricas por corrida**: score medio, % de preguntas que pasan, cobertura de `must`,
  violaciones `must_not`, segundos por pregunta. Se comparan corridas lado a lado.

**Dónde vive cada cosa**: preguntas, componentes, métricas y veredictos en Postgres
(`bench_sets`, `bench_questions`, `bench_components`, `bench_runs`, `bench_results`); el
detalle pesado de cada corrida (respuesta completa, chunks, prompt, salida cruda del juez)
en el object store como `bench/runs/<id>.json` (bucket `rag-lab`), y los respaldos de sets en
`bench/exports/`. El object store (`shared/object_store.py`) es **MinIO** si hay
`MINIO_ENDPOINT` + llaves en el `.env` (en el servidor: `MINIO_ENDPOINT=127.0.0.1:9000`,
`MINIO_SECURE=false`, `MINIO_BUCKET=rag-lab`, con un usuario `rag-lab-app` cuya política
solo permite ese bucket); si no, cae a la carpeta local
`ingestion/.objects/` con las mismas llaves.

## Estructura

```
apps/rewrite_lab/
  main.py            # backend FastAPI (lógica + endpoints)
  ingest_service.py  # gestor de jobs de ingesta en segundo plano (tab "Ingestar")
  static/index.html  # UI completa (se sirve estática; pide /api/config al cargar)
  static/preguntar.html  # página simple para usuarios finales (config por URL)
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
| `CHAT_HISTORY_MESSAGES` | `6` | mensajes recientes del historial que van a la GENERACIÓN en Conversacional (acota el contexto; el retrieval se condensa aparte) |
| `HOST` / `PORT` | `127.0.0.1` / `8050` | bind del servidor (usa `0.0.0.0` para exponerlo) |

En el server, en vez de `localhost`, `LLM_URL`/`TEI_URL` apuntan a como la rtx sea
alcanzable desde tlacua. Ponlo detrás de tu nginx/proxy y, si expones la UI,
agrégale la auth de tu app.

## Requisitos

- La tabla `LEGAL_TABLE` debe estar ingestada (`ingestion/legal_rag.py ingest`).

