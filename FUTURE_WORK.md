# Future Work

Notas de trabajo pendiente, priorizadas. Contexto: RAG legal/psicología, app en prod
(`legis-app`, tabla `sistema_penal__qwen06__legal`, embedder `qwen06` 1024-dim,
DB `rag_lab`, TEI/LLM en rtx5090).

## Ingesta y OCR

### 1. Automatizar la ingesta de PDFs escaneados

**Estado actual (manual, solo Mac):** prod convierte con `pymupdf4llm`, que **no OCRea**.
Un PDF escaneado → texto vacío → `KeyError: 'document'` en `merge_small_siblings`. Hoy se
resuelve OCReando **en local** con Docling + macOS Vision (`ingestion/ocr_*.py`) e
insertando el `.md` con `ingestion.pipeline.ingest_md`. Requiere una Mac + los scripts →
no lo puede hacer cualquier admin.

**Requisito:** que **cualquier admin, desde cualquier OS (Win/Mac/Linux) y desde el
teléfono**, suba un escaneado por el tab y se ingiera solo.

**Consecuencia de diseño:** el teléfono y el "cualquier OS" implican que **el OCR NO puede
correr en el dispositivo del usuario**. El cliente solo sube; el OCR es **server-side o en
la nube**. Esto descarta la opción de "preprocesar con una app local" (no aplica a móvil;
instalación por-OS; calidad dispareja).

**Opciones (todas: subir el PDF por el tab; el OCR ocurre server-side):**

| # | Solución | Esfuerzo | Pros | Contras |
|---|---|---|---|---|
| **A** | **OCR en el server de la app** (agregar `rapidocr`; pymupdf4llm lo usa solo) | **Mínimo** | Sin infra nueva; funciona desde cualquier device y móvil; uniforme | Carga de CPU en el VPS con libros grandes (minutos, RAM); calidad RapidOCR (más ruidosa que Vision) |
| **B** | **Offload a rtx5090** (microservicio OCR HTTP, como TEI/LLM/reranker) | Medio | Encaja con la arquitectura (cómputo pesado ya vive en rtx5090 vía túneles); GPU-rápido; alta calidad; VPS ligero; móvil ok | Un servicio nuevo que mantener en rtx5090 |
| **C** | **API de OCR en la nube** (Mistral OCR / Google Document AI / Azure DI) | Bajo | Cero infra; mejor calidad; funciona en todo incl. móvil; barato (~$1/1000 págs) | Los datos salen a un tercero (privacidad); API key; costo por página |
| **D** | **Offload a una Mac mini vía SSH** (macOS Vision) | Medio-alto | Calidad de Vision; VPS ligero; móvil ok | Un box nuevo, **menos integrado que rtx5090** (que ya está en el stack); orquestación SSH; peor que B salvo que se necesite Vision específicamente |
| ~~E~~ | ~~Preprocesar con app local~~ (la opción 1 planteada) | — | — | **Rechazada:** no corre en teléfono; instalación por-OS; calidad dispareja |

**Recomendación (por fases):**
- **Fase 1 (MVP, ya):** **Opción A** — agregar `rapidocr` al extra `parse` + redeploy
  (`uv sync --extra parse && sudo systemctl restart legis-app`). Satisface el requisito
  completo (cualquier admin/OS/móvil) con cambio mínimo y reusa el job async ya probado.
  Guardarraíles: límite de páginas/tamaño por subida, y mantenerlo de a uno (ya lo es).
  Los libros de alto valor pueden seguir usando el flujo local Docling+Vision cuando la
  precisión importe.
- **Fase 2 (si la carga o la calidad lo exigen):** **Opción B** (rtx5090, consistente con
  la arquitectura y privado) o **C** (nube, menos esfuerzo y mejor calidad). La **D**
  (Mac mini) solo si se requiere específicamente la calidad de macOS Vision y el OCR de
  rtx5090 no basta — pero B usa un box ya integrado, así que domina a D.

**En todos los casos** shipear también el fix defensivo del `KeyError` (ítem 2): un OCR
que salga vacío debe dar un error claro, no un crash.

### 2. Fix defensivo del `KeyError: 'document'`
`shared/legal_chunking.py` → `merge_small_siblings`: si `units` viene vacío, lanzar un
error claro ("documento sin texto extraíble — ¿PDF escaneado sin OCR?") en vez del
`KeyError` críptico. Igual en el reporte de la UI.

### 3. Recarga del índice BM25 tras inserciones out-of-band
Un insert hecho por fuera de la app (script directo) NO refresca el BM25 en memoria
(solo se recarga al arrancar o vía `on_complete` de un ingest por la app). La densa sí
lo ve al instante. Hoy se soluciona reiniciando el servicio.
- **Acción:** endpoint admin `POST /admin/reload-index` que llame `load_corpus_index()`,
  para evitar reiniciar todo el servicio.

### 4. Limpieza post-OCR de los escaneados legales (CAG)
El OCR de CAG (Docling+Vision) dejó errores por clase: acentos perdidos
(`articulo→artículo`), garbles de caracteres (`Priendo→Privado`), numerales romanos
(`Il→II`), ordinales (`1ª`), abreviaturas (`pdg.→pág.`). Un diccionario general es
peligroso (marca vocabulario legal legítimo como error).
- **Acción propuesta:** pase de corrección con LLM (chunk a chunk, prompt estricto
  "solo corrige OCR, no reescribas"), idealmente con la imagen de página para recuperar
  los garbles de caracteres. Verificar por diff. Alternativa: re-OCR con OCR
  language-aware (Mistral OCR / vision-LLM).

### 5. Recorte de bibliografía en papers académicos
`clean_document` conserva la bibliografía; en los papers de psicología esos chunks de
puras referencias meten ruido en retrieval. Evaluar recortar secciones
"Referencias/Bibliografía" al final para temas académicos.

## Evaluación / calidad de recuperación

### 6. Benchmark de retrieval por tópico
Reusar `06_evaluation/` (recall@k, MRR, nDCG a nivel doc) para medir cada tópico, no
solo el penal.
- Construir golden sets por tópico (`golden_<topic>.json`: pregunta → doc gold).
  Empezando por `psicologia_conductual` (28 docs).
- Comparar métodos: denso vs BM25 vs híbrido (RRF) vs +reranker.
- Registrar resultados versionados (tabla `rewrite_lab_runs` o `results.json`).

### 7. Métricas de generación (RAGAS-style)
Pendiente en lab 06 (faithfulness, answer relevance). Separar calidad de retrieval de
calidad de generación.
