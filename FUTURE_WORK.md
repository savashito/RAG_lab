# Future Work

Notas de trabajo pendiente, priorizadas. Contexto: RAG legal/psicología, app en prod
(`legis-app`, tabla `sistema_penal__qwen06__legal`, embedder `qwen06` 1024-dim,
DB `rag_lab`, TEI/LLM en rtx5090).

## Ingesta y OCR

Detalle de lo hecho, benchmark y evidencia de cada hallazgo:
[`ingestion/OCR_ESCANEADOS.md`](ingestion/OCR_ESCANEADOS.md).

### ✅ 1. Automatizar la ingesta de PDFs escaneados (hecho 2026-09-28)
Cualquier admin, desde cualquier dispositivo, sube el PDF por el tab. `pdf_triage` decide
por página, sin OCR, si hace falta OCR:
- **Digital:** `pymupdf4llm` en el VPS.
- **Escaneado o con texto roto:** servicio **Docling + macOS Vision en la Mac mini**,
  vía túnel inverso a `127.0.0.1:8095` con token.

La UI muestra dónde se procesó cada documento. Se validó sobre 60 PDFs: detectó los 8
escaneados conocidos y ningún falso positivo.

Se eligió la **opción D** (Mac mini) en lugar de A (`rapidocr` en el VPS), que era la
recomendada antes:
- el VPS comparte CPU con `dengue_forecast` y no debe hacer OCR;
- en el CAG real, Docling + Vision recupera el 94.6% de las palabras contra el 60.5% de
  Tesseract.

Las opciones B (rtx5090) y C (nube) siguen abiertas si la Mac se vuelve cuello de botella.

### ✅ 2. Fix defensivo del `KeyError: 'document'` (hecho 2026-09-28)
`_ingest_markdown` falla con un mensaje claro si el texto limpio queda vacío ("¿PDF
escaneado sin OCR?"). Además, la red de seguridad de `convert_pdf` reintenta con OCR si
el VPS produce un Markdown casi vacío.

### ✅ Limpieza que borraba párrafos con "Secretaría General" (hecho 2026-09-29)
La regla `institutional_header` descartaba líneas completas, y en Docling una línea es
un párrafo entero. Se le puso tope de palabras; los folios `N/M` ahora sí se limpian.
Se reingirieron los 7 documentos afectados que tenían fuente local (el CAG recuperó
unas 14.5 mil palabras), comprobando oración por oración que no se perdiera nada.

### 3. Recarga del índice BM25 tras inserciones out-of-band (parcial)
- **Ya hecho:** el borrado desde la UI recarga el BM25 en segundo plano, y la recarga
  publica el índice de un solo golpe, con lock.
- **Falta:** un insert hecho por fuera de la app (script directo, como la reingesta del
  2026-09-29) sigue sin refrescar el BM25 en memoria, y hay que reiniciar el servicio.
  La búsqueda densa sí lo ve al instante.
- **Acción:** endpoint admin `POST /admin/reload-index` que llame `load_corpus_index()`
  en segundo plano.

### 8. Reinsertar Sociología con el CMap corregido (alta)
- 264 de 311 chunks del libro de sociología jurídica tienen `�`: se perdieron "Capítulo
  N" y subtítulos como "la encuesta", "la mesa redonda" o "el sociodrama".
- La causa es que la fuente `ArialMT` trae un `ToUnicode` incompleto.
- El arreglo exacto ya está probado: agregar 35 entradas `bfchar` al CMap del PDF, que
  da 0 `�` y no necesita OCR (ver `OCR_ESCANEADOS.md` §3).
- **Acción:** generar el PDF parchado, subirlo por la UI con el mismo nombre para que
  reemplace los 311 chunks, y verificar que se encuentran "sociodrama" y "mesa redonda".
- Opcional: detectarlo solo en `pdf_triage` (una fuente con CIDs sin mapear) y aplicar el
  parche antes de convertir.

### 9. Verificar la limpieza en los 36 documentos subidos solo por la UI (media)
- Sin su PDF ni su md crudo no se puede medir si el bug de "Secretaría General" les borró
  texto.
- Son sobre todo leyes de Diputados (Ley General de Víctimas, LFCDO, Secuestro, Trata),
  códigos de la CDMX y el Edomex, el CNPCyF, los cuadernos "Derecho y Familia" de la SCJN
  y libros de teoría del delito.
- **Acción:** conseguir los PDFs (las leyes son públicas, en diputados.gob.mx), reconvertir
  con el pipeline actual, comparar oración por oración contra la DB y reingerir solo los
  que ganen texto.

### 10. Ligaduras perdidas en FAP 1 (baja)
- 19 de 21 chunks tienen `identi�car`, `bene�cios` o `el �n`: la ligadura `fi` sale
  como U+FFFD, y BM25 no encuentra esas palabras.
- **Acción:** parchar el CMap como en el ítem 8, o mapear las ligaduras al convertir, y
  reingerir.

### 11. Nombres de fuente en NFD (baja)
- macOS sube nombres con los acentos descompuestos (NFD); hoy hay 8 fuentes así en la DB.
- Si alguien vuelve a subir el mismo documento desde Windows o Linux (NFC), queda
  duplicado en vez de reemplazarse.
- **Acción:** normalizar a NFC en `source_name()`, y en la misma migración pasar a NFC
  esas 8 fuentes en la tabla, en `out_clean/` y en `_conversion.json`.

### 12. Resiliencia de la Mac mini (media)
- **Reinicio:** tras un reinicio no arrancan ni el OCR, ni el túnel, ni el bastión hasta
  que alguien inicie sesión en la Mac. Hay dos salidas:
  - activar el inicio de sesión automático;
  - pasar el túnel y el bastión a `LaunchDaemons`. Falta comprobar si Vision funciona sin
    sesión gráfica.
- **Monitoreo:** avisar si `/health` falla desde el VPS, con un check periódico.
- **Versionado:** el código del servicio vive en un repo git local de la Mac
  (`~/ai/ocr`). Conviene versionarlo, por ejemplo en `deploy/ocr_macmini/` de este repo.

### 13. Calidad de Docling en escaneos (media)
- En el CAG, Docling a veces omite (unas 34 palabras) o reordena un párrafo.
- **Acción:** un control de calidad en el servicio que compare las palabras por página
  del resultado contra el OCR crudo de Vision (`ocrmac`) y avise si faltan más del ~10%.
  Esto se relaciona con el ítem 4.

### 14. PDFs mixtos: OCR solo de las páginas escaneadas (baja)
- Hoy, si menos del 20% de las páginas están escaneadas, esas páginas se omiten y el
  reporte las lista.
- **Acción:** mandar a la Mac solo esas páginas y reinsertar su Markdown en orden.
- Limpiar de paso los mds de 0 bytes que quedaron en `out_clean/` de intentos fallidos.

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
