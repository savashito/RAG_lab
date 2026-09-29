# OCR de PDFs escaneados (Mac mini) y hallazgos de calidad de ingesta

Registro de lo construido y lo encontrado entre el 2026-09-28 y el 2026-09-29 al
automatizar la ingesta de PDFs escaneados en `legis-app`. Lo pendiente vive en
[`../FUTURE_WORK.md`](../FUTURE_WORK.md).

## Resumen

- Cualquier admin sube un PDF por el tab de ingesta, desde cualquier dispositivo. El
  VPS decide solo si necesita OCR: los **digitales** se convierten en el VPS con
  `pymupdf4llm`, como antes; los **escaneados** se mandan a la **Mac mini**
  (Docling + macOS Vision) y vuelven como Markdown.
- El admin ve en cada archivo y en la lista del corpus **dónde se procesó**
  (🖥️ VPS o 🍎 Mac mini), el motivo, las páginas y el tiempo.
- Al probarlo aparecieron tres bugs de calidad que ya estaban en producción. El más
  grave: la limpieza **borraba párrafos enteros** que mencionaban "Secretaría
  General". Ya está corregido y los documentos afectados se reingirieron.

## Arquitectura

```
navegador ──subida──▶ VPS · legis-app ──triage (PyMuPDF, <1 s)──┬─ digital ─▶ pymupdf4llm (VPS)
                                                                 └─ escaneado ─▶ POST 127.0.0.1:8095/ocr
                                                                                   │ túnel inverso (lo abre la Mac)
                                                                                   ▼
                                                                  Mac mini · FastAPI 127.0.0.1:8095
                                                                  Docling + OcrMac (es-ES), CPU
```

- **El VPS nunca hace OCR:** comparte CPU con `dengue_forecast` y no tiene GPU. Si la
  Mac no responde, la ingesta falla con un mensaje claro y no hay OCR local de
  respaldo.
- **Servicio en la Mac:** `/Users/rodrigosavage/ai/ocr`, repo git local.
  - `app.py`: carga el converter una sola vez al arrancar, procesa **un PDF a la vez**
    (si llega otro responde `429` + `Retry-After`) y convierte en bloques de 50
    páginas para no llenar la RAM.
  - Límites: 800 páginas y 200 MB (`413`).
- **Seguridad:**
  - El servicio escucha solo en `127.0.0.1` y exige un token `Bearer`.
  - El token vive en `.token` en la Mac y en `~/.ocr_token` en el VPS, los dos con
    permisos 600; se copia a mano.
  - El túnel usa una llave dedicada (`~/.ssh/ocr_tunnel`). En el VPS esa llave está
    restringida a `restrict,port-forwarding,permitlisten="127.0.0.1:8095",command="/bin/false"`,
    así que solo puede abrir ese puerto.
- **Arranque:** dos LaunchAgents con `KeepAlive`, `com.ocr.service` y `com.ocr.tunnel`.
  Si el servicio muere, launchd lo levanta en unos 20 s.
  - ⚠️ **Tras un reinicio no arrancan** hasta que alguien inicie sesión en la Mac, porque
    no hay inicio de sesión automático. Lo mismo pasa con el bastión SSH
    (`com.tunnel.bastion`).
- **Cliente en el VPS:** `ingestion/ocr_client.py`.
  - Primero consulta `/health`, así que si la Mac no responde falla rápido y con un
    mensaje claro.
  - Si la Mac está ocupada (`429`), espera el `Retry-After` y reintenta, hasta
    `OCR_MAX_WAIT`.
  - El tiempo máximo de espera es proporcional al número de páginas.
  - Configuración: `OCR_URL`, `OCR_TOKEN_FILE` y `OCR_MAX_WAIT` (ver `.env.example`).

## Cómo decide si un PDF necesita OCR (`ingestion/pdf_triage.py`)

Se revisa cada página con PyMuPDF, sin hacer OCR:

| Clase | Regla |
|---|---|
| `scanned` | < 50 caracteres extraíbles **y** imágenes que cubren ≥ 15% de la página |
| `broken_text` | tiene texto, pero > 5% son caracteres inválidos (U+FFFD, uso privado, controles o letras que no son latinas ni griegas) |
| `blank` | sin texto ni imagen |
| `text` | todo lo demás |

- **Documento:** si más del 20% de las páginas con contenido son `scanned` o
  `broken_text`, el documento entero va a la Mac. Si son menos, se convierte en el VPS
  y el reporte lista las páginas omitidas.
- **Red de seguridad:** si el VPS produce menos de 5 palabras por página, o más del 5%
  de caracteres basura, se reintenta con OCR.
- **Validación con el corpus local (60 PDFs):** marcó exactamente los 8 que ya se
  habían OCReado a mano (3 del CAG y 5 de psicología) y ningún PDF digital.
- **Ajuste de la cobertura mínima:** empezó en 50%. Se bajó a 15% porque
  "La anorexia por actividad" es un escaneo chico sobre una hoja grande (27–48% de
  cobertura) y se clasificaba como página en blanco.

## Benchmark de calidad: Docling + Vision contra Tesseract

Los dos motores en la Mac mini (M4, 16 GB). En s/pág, Docling incluye la subida por HTTP.

| Prueba | Motor | s/pág | Palabras (en orden) | Palabras (sin orden) | Acentos |
|---|---|---|---|---|---|
| Sociología pp. 60–65, rasterizadas a 200 dpi en gris, JPEG q70 | Docling + Vision | 1.04 | 99.4% | 100% | 179/179 |
| | Tesseract `spa` | 0.66 | **99.9%** | 99.9% | 179/179 |
| **CAG real** (pp. 80–81, verdad transcrita a mano, 986 palabras) | Docling + Vision | 2.41 | **72.5%** | **94.6%** | **90.0%** |
| | Tesseract `spa` | 1.44 | 30.1% | 60.5% | 74.5% |

- En páginas limpias los dos motores empatan y Tesseract es más rápido.
- En escaneos reales Docling gana por mucho. Tesseract mezcla línea por línea las dos
  páginas del pliego y lee el texto que se transparenta de la otra cara.
- Docling también falla en escaneos: en ese pliego omitió ~34 palabras y cambió el
  orden de dos párrafos.
- La columna "en orden" usa `difflib.SequenceMatcher` sobre palabras en minúsculas,
  normalizadas a NFC y sin sintaxis Markdown.
- La "verdad" de sociología tuvo que corregirse primero; ver el hallazgo 3.
- Script: `~/ai/ocr/bench/bench.py` (en la Mac).

## Hallazgos

### 1. La limpieza borraba párrafos de cuerpo (grave, corregido)

**Síntoma.** Al subir un acuerdo del Consejo de la Judicatura (CJCDMX) de 15 páginas,
faltaban las páginas 11–14 en el md.

**Causa.** El OCR de la Mac las había leído completas (5,656 palabras); el texto se
perdía en `clean_document`. La regla `institutional_header` buscaba
`SECRETAR[IÍ]A GENERAL` en **cualquier parte** de la línea y descartaba la línea entera.
Docling (y a veces `pymupdf4llm`) entrega un párrafo completo como una sola línea: dos
párrafos de 481 y 631 palabras que mencionaban a "la Secretaria General" del Consejo
desaparecieron.

**Alcance en producción.** Medido comparando la limpieza vieja contra la nueva sobre
los mds crudos:

| Documento | Texto recuperado |
|---|---|
| CAG, Primera parte | ~40 cláusulas ("…se depositarán en la Secretaría General de la OEA") y la lista de tratados con su fecha del DOF: +14.5 mil palabras |
| La ejecución de sentencias | 5 párrafos ("Secretaría General de Gobierno") |
| Código Penal Federal | Arts. 352 y siguientes, pegados al encabezado de Diputados en la misma línea |
| CNPP, Desafíos, CAG Segunda parte, La policía de investigaciones | 1–2 párrafos o notas cada uno |

**Corrección** (`shared/legal_chunking.py`):

- El ruido de línea tiene tope de palabras: encabezado institucional ≤ 16 (el real tiene
  15) y marca de agua editorial ≤ 40 (la más larga medida tiene 35). Las
  distribuciones no se traslapan: el ruido real mide menos de 30 palabras y el cuerpo
  empieza en 19.
- Si el encabezado de Diputados viene pegado al inicio de un párrafo, se recorta solo
  el encabezado.
- Verificado sobre 44 mds: 159 líneas que antes se borraban ahora se conservan (todas
  son contenido). Lo único nuevo que se quita son los folios `N/15`. Siguen quedando 0
  encabezados de Diputados y 0 marcas de agua de la BJV.

**Reingesta (2026-09-29).**

- Documentos: los 2 del CAG desde `markdown/CAG_clean`, que es la versión que había en
  prod, y los demás desde el PDF, con el mismo pipeline de la UI.
- Tema y jurisdicción conservados.
- Comprobado oración por oración que **ninguna oración que estaba en prod se perdió**.
- El CPF baja de 646 a 636 chunks y el CNPP de 514 a 509, aunque tienen más texto: el
  chunker actual reparte los transitorios de otra manera. En prod había, por ejemplo,
  28 chunks titulados "Artículo 131" que eran transitorios.
- ⚠️ **Lección:** los mds locales de `ingestion/out` **no** eran la fuente exacta de prod.
  Antes de reingerir hay que comparar contra lo que hay en la DB, no suponer.

### 2. Folios `N/M` sin limpiar (corregido)

`PAGE_RE` solo reconocía `12`, `XII` y `12 de 15`. Ahora también reconoce `12/15`, pero
solo cuando es la línea completa: "3/4 partes del pleno" no se toca.

### 3. Sociología: fuente con `ToUnicode` roto (diagnosticado, reinserción pendiente)

- **En prod:** 264 de 311 chunks del libro de Olga Sánchez tienen `�`, unos 11 mil
  caracteres. Por ejemplo, `C������� 5` en lugar de "Capítulo 5", y subtítulos vacíos
  como `1.10.4.3. �� ��������` ("la encuesta"). Tampoco se encuentran "sociodrama" ni
  "mesa redonda".
- **Causa:** la fuente `ArialMT` (Type0, Identity-H) trae un CMap `ToUnicode` con solo
  85 entradas. Los CID de los encabezados valen `0x0D89…` y no se traducen.
  `page.get_text()` los devuelve como caracteres cingaleses (corrimiento fijo de
  `0xD28` para a–z; los acentos siguen el orden Mac Roman corrido −4: `83=á 8A=é 8E=í
  91=ñ 93=ó 96=ö 98=ú 9A=ü`). `pymupdf4llm` y `get_texttrace` los devuelven como
  U+FFFD. Desde el texto guardado en prod no se puede recuperar.
- **Arreglo probado:** agregar esas 35 entradas `bfchar` al CMap del PDF. Da 0 `�` y
  extracción exacta, sin OCR (`#### Capítulo 5 SOCIOLOGÍA DE LA FAMILIA`,
  `1.10.4.6. la mesa redonda`). Es mejor que mandarlo a OCR (99.4%). El triage lo manda
  al VPS: solo 26 de 510 páginas (5%) tienen texto roto.

### 4. FAP 1: ligaduras perdidas (menor, pendiente)

19 de 21 chunks tienen `identi�car`, `bene�cios` o `el �n`: la ligadura `fi` sale como
U+FFFD. BM25 no encuentra "identificar". Otros 3 documentos pierden solo símbolos
sueltos (`×`, `=`).

### 5. Borrar un documento parecía no funcionar (corregido)

- **Causa:** el `DELETE` esperaba a reconstruir el BM25 completo, unos 20 s con ~14.6 mil
  chunks, sin ninguna señal en la UI. En el log se ven 7 recargas de la lista en 3 s.
- **Corrección:** responde en cuanto borra y la recarga corre en segundo plano. El índice
  se publica de un solo golpe (`BM25_CORPUS = (índice, ids)`) y un lock evita que dos
  recargas se pisen.
- **UI:** la fila queda en "⏳ eliminando…" y luego aparece un aviso
  "✓ «X» eliminado (N chunks)".

### 6. Otros

- **Nombres en NFD.** macOS sube nombres de archivo con los acentos descompuestos (NFD),
  y 8 fuentes en la DB los tienen así. Si alguien vuelve a subir uno desde Windows,
  quedaría duplicado en vez de reemplazarse.
- **Mds huérfanos.** En `out_clean/` quedaron mds de 0 bytes de intentos fallidos
  anteriores (escaneados sin OCR).
- **Docling y las páginas firmadas.** Clasifica como `picture` las páginas con firmas,
  rúbricas y sellos ("ORIGINAL"), pero **el texto sí se exporta**. La pérdida del
  acuerdo no fue de Docling, fue el hallazgo 1.
- **OAuth.** Tras el login con Google siempre se regresaba a `/`, y se perdía el
  `?tema=` de un enlace compartido. Ahora se vuelve a la ruta pedida, solo si es
  interna.

## Operación

```bash
# Mac mini (desde la laptop: ssh -i ~/.ssh/id_ed25519_savashito macmini)
launchctl kickstart -k gui/$(id -u)/com.ocr.service   # reiniciar el servicio OCR
launchctl kickstart -k gui/$(id -u)/com.ocr.tunnel    # reiniciar el túnel
tail -f ~/ai/ocr/logs/service.log ~/ai/ocr/logs/tunnel.log

# VPS
curl -s http://127.0.0.1:8095/health                  # ¿llega a la Mac?
curl -s -H "Authorization: Bearer $(cat ~/.ocr_token)" -F file=@scan.pdf http://127.0.0.1:8095/ocr
```

- **Rotar el token:** `openssl rand -hex 32 > ~/ai/ocr/.token` en la Mac, reiniciar el
  servicio y copiar el token a mano a `~/.ocr_token` en el VPS.
- **Registro de conversión:** `<CLEAN_MD_DIR>/_conversion.json` (source → dónde, motor,
  motivo y fecha). Los documentos ingeridos antes del 2026-09-28 no tienen entrada.
