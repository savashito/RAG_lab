# Future Work

Notas de trabajo pendiente, priorizadas. Contexto: RAG legal/psicología, app en prod
(`legis-app`, tabla `sistema_penal__qwen06__legal`, embedder `qwen06` 1024-dim,
DB `rag_lab`, TEI/LLM en rtx5090).

## Ingesta y OCR

### 1. Que el tab de ingesta OCRee escaneados (arreglo de fondo)
Hoy prod **no tiene backend de OCR**: el extra `parse` solo trae `pymupdf4llm`+`minio`.
Un PDF escaneado subido por el tab → texto vacío → `KeyError: 'document'` en
`merge_small_siblings` (DataFrame de unidades vacío). Actualmente se resuelve OCReando
en local (Docling+macOS Vision) e insertando por fuera con `ingest_md`.
- **Acción:** agregar `rapidocr` (u onnxruntime + rapidocr) al extra `parse`, redeploy
  (`git pull && uv sync --extra parse && sudo systemctl restart legis-app`).
- **Trade-off:** RapidOCR (fallback de pymupdf4llm) es más ruidoso que Docling+Vision.
  Para docs escaneados de alto valor, preferir el flujo local Docling+Vision.

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
