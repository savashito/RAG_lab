# Ronda 1 del estudio con usuarios: hallazgos, causas y plan para la ronda 2

> **Para quien lea esto (personas o un asistente de IA):** este documento es autocontenido. Resume un
> estudio con usuarios de un asistente jurídico con RAG (retrieval-augmented generation) sobre derecho penal
> mexicano, hecho para un paper en **ACM FAccT 2027** (abstract: 27-oct-2026; paper: 3-nov-2026).
> Todos los números vienen de la base de datos de producción al **13-oct-2026** (ronda 1 cerrada), salvo donde
> se indica. Las cifras son **preliminares**: los grupos son chicos (7–9 personas) y nada de esto tiene todavía
> pruebas estadísticas. Las citas de participantes son textuales (con sus faltas de ortografía) y anónimas.

---

## 0. Resumen en 12 líneas

1. 24 estudiantes (UNAM, casi todos **sin formación jurídica**) usaron el asistente en 3 situaciones ficticias.
2. **El asistente cita códigos penales de OTROS estados en la mayoría de las conversaciones** (≈ 50–70 % de las
   respuestas según la situación), **incluso cuando la persona ya dijo el estado** (43 % de esas respuestas).
3. **No es invención del modelo: en 65 de 67 casos esos otros estados venían en lo que recuperó el buscador.**
   Es sobre todo un problema de **búsqueda** (recuperación), no de generación.
4. **Casi nadie lo nota**: 0–13 % dijeron haber notado un problema; cuando el asistente mezcla estados, casi nadie
   lo registra como mezcla.
5. **La gente casi nunca dice dónde pasó** (26 % en las dos situaciones donde el lugar no es el centro de la
   historia). Cuando lo dice, el buscador encuentra el artículo correcto mucho más (p. ej. 100 % vs ≈ 40 %).
6. **Lenguaje cotidiano vs. jurídico**: con «me piden dinero por no publicar mis fotos», el buscador casi nunca trae
   el artículo que define la extorsión (9 %); confunde artículos contiguos casi homónimos (167 **Quáter** vs. 167
   **Quinquies** de Querétaro).
7. **Prompt sencillo vs. jurídico** (sorteado, 8 vs. 7 personas): el sencillo **gusta más** (SUS 84 vs. 78),
   da **más seguridad** y **más disposición a actuar** (75 % vs. 56 %), **tarda menos** (6.3 vs. 8.7 min por
   situación)… pero **no mejora la comprensión** (67 % vs. 61 %, diferencia dentro del ruido).
8. Hipótesis emergente (a confirmar): **el lenguaje sencillo sube la confianza sin subir la comprensión.**
9. El prompt sencillo **pregunta el estado** más (35 % vs. 8 % de las respuestas)… pero **contesta igual citando
   otros estados**, así que preguntar no evita el error.
10. Benchmark experto (sin personas): el prompt sencillo **sin** la regla «usa solo el CONTEXTO» cae de 76 % a 38 %
    en preguntas generales; **con** esa regla iguala al jurídico (76 %), pero pierde en preguntas comparativas (63 %
    vs. 79 %).
11. Propuesta: cerrar la ronda 1 como **auditoría** y hacer una **ronda 2 con un sistema corregido**
    (filtro de jurisdicción en la búsqueda + prompt que no cite otros estados + mejor recuperación de artículos),
    sorteando de nuevo original vs. corregido, con personas nuevas y las mismas situaciones.
12. Mensaje del paper: **la falla es de diseño, no del usuario, y se puede corregir** (incluso con un modelo
    pequeño y abierto), pero el lenguaje sencillo trae su propio riesgo: más confianza.

---

## 1. El sistema que se evaluó

- **Corpus**: tema «derecho_penal_mexicano», 49 documentos (≈ 8,718 fragmentos o *chunks*): Código Penal Federal,
  Código Nacional de Procedimientos Penales (CNPP), códigos penales de la Ciudad de México (CDMX), Estado de
  México (Edomex), Morelos y Querétaro, leyes generales (secuestro, **extorsión — nueva, 2025**, víctimas,
  delincuencia organizada), ~30 libros de doctrina y, desde el 9-oct, una ficha técnica de **«Ley Olimpia»** (tabla
  con el artículo de cada uno de los 32 estados), un documento de «Violencia Digital» y una tesis. Los códigos
  están partidos **un artículo por chunk**, con el nombre de la ley y la jerarquía (libro › título › capítulo ›
  artículo) al inicio del texto. **La Constitución no está en el corpus.**
- **Búsqueda**: híbrida (BM25 + embeddings densos Qwen3-Embedding-0.6B, fusionados con RRF), **HyDE** (el LLM
  redacta un pasaje hipotético y se busca con él), **descomposición** (el LLM parte preguntas comparativas en
  sub-preguntas), **routing por código** (si la pregunta nombra un estado o código, se hace además una búsqueda
  restringida a ese código y se intercala — *agrega*, no *filtra*), **vecinos** (se agregan el artículo y sus
  ±2 artículos contiguos). Top-k = 10 + vecinos. Conversación multi-turno: la pregunta se reescribe con el
  historial antes de buscar; el modelo ve toda la conversación (hasta 10 mensajes previos).
- **Modelo**: Gemma 4 (26B-A4B MoE, 4-bit, llama.cpp), alojado en servidor propio (sin APIs comerciales).
  Respuesta en *streaming*; ~11–12 s por respuesta.
- **Dos system prompts** (la condición experimental):
  - **«original»** (jurídico): exige responder **solo con el CONTEXTO**, citar artículo + ordenamiento, y redactar
    «en español jurídico… para estudiantes y profesionales del Derecho», en párrafos argumentativos con secciones
    Respuesta / Fundamento jurídico / Conclusión / Fuentes doctrinales.
  - **«sencillo»** (escrito por la experta, Karen): lenguaje cotidiano, empático, estructura «¿qué significa?,
    ¿cuáles son mis derechos?, ¿qué puedo hacer?, ¿qué podría pasar?», **pide la entidad federativa**, + un bloque
    añadido «USO DEL CONTEXTO (OBLIGATORIO)» (responder solo con los fragmentos y citar artículo y ley). Archivos:
    `06_evaluation/prompts_2026-10-12/`.

## 2. Diseño del estudio (ronda 1)

- **Participantes**: estudiantes de la UNAM reclutados en persona (kioscos en computadoras de la universidad) y por
  un enlace público. Sin nombre: código anónimo por persona. Consentimiento informado, retiro con borrado de datos.
- **Flujo por persona (~20–30 min)**: consentimiento → perfil (área, carrera, semestre, formación jurídica, uso de
  IA, confianza basal para buscar información legal, edad) → **práctica** (pregunta de ejemplo en lenguaje
  cotidiano sobre un tema que no aparece en las situaciones) → **3 situaciones en orden aleatorio** → cuestionario
  final (SUS de usabilidad + 2 preguntas abiertas).
- **En cada situación**: lee una historia ficticia, conversa con el asistente con sus propias palabras (1–6
  preguntas), luego pasa a preguntas (ya no puede preguntar más, pero ve la conversación en modo lectura al
  lado): **2 preguntas de opción múltiple** (una sola respuesta; opciones en orden aleatorio; desde el 12-oct con
  la opción «No está en las opciones la respuesta que busco» + texto libre), **confianza 1–5**, **«¿notaste algún
  problema?»** (+ cuál), **«¿actuarías con base en esta respuesta?»**, comentario opcional. En la **última**
  situación de cada persona: **«¿de qué estado era la ley que te citó el asistente?»** (solo ahí, para no
  influir en las demás).
- **Aviso bajo cada situación** (texto final, neutral): *«El asistente jurídico no puede ver esta situación: solo
  sabe lo que tú le escribas. Pregúntale con tus propias palabras, como lo harías si te pasara a ti.»*
- **Las 3 situaciones** (nombres unisex, sin marcar género):
  1. **Mensajes en el trabajo** — la persona que supervisa a Alex le manda mensajes sexuales y le ofrece un
     ascenso a cambio de una cita; nunca hubo contacto. **Versión sorteada: Querétaro o CDMX** (mismos hechos,
     distinto delito: Querétaro art. 167 Ter *hostigamiento sexual*, 4–8 años; CDMX art. 179 *acoso sexual*, 1–3
     años + 1/3 por jerarquía). Mide **jurisdicción**.
  2. **Las fotos** — Cris (Querétaro) mandó fotos íntimas; ahora le exigen 5,000 pesos para no publicarlas.
     Esperado: **Ley General en materia de Extorsión, art. 15** (y agravante art. 17 fr. IV por usar imágenes
     privadas); relacionado: Querétaro **art. 167 Quinquies** (amenazar con difundir imágenes íntimas «obtenidas con
     o sin consentimiento»). Mide **lenguaje cotidiano vs. jurídico** y una ley nueva.
  3. **El citatorio** — Ariel vive en CDMX, se pelea en un bar de Querétaro y recibe un citatorio de la Fiscalía de
     Querétaro; cree que le aplican las leyes de la CDMX. Esperado: **Código Penal de Querétaro, art. 1**
     (territorialidad) y **CNPP art. 20** (competencia). Mide **domicilio vs. lugar de los hechos**.
- **Fases**: «piloto» (9-oct a 11-oct; todos con el prompt original, sin sorteo; con explicación verbal de la
  investigadora de que el asistente no conoce la situación) y «principal» (desde 12-oct; **prompt sorteado,
  balanceado** mitad y mitad).

## 3. Muestra

| Grupo | Personas | Terminaron | Situaciones contestadas |
|---|---|---|---|
| Original (piloto, sin sorteo) | 9 | 7 | 21 |
| Original (sorteado) | 7 | 6 | 18 |
| Sencillo (sorteado) | 8 | 8 | 24 |
| **Total** | **24** | **21** | **63** |

(Se excluyeron 3 pruebas técnicas del 8-oct.) Áreas: Biológicas y de la Salud 10, Humanidades y Artes 7,
Sociales 3, Físico-Matemáticas e Ingenierías 3, **Derecho 1**. Formación jurídica: ninguna 17, una o dos
materias 6, trabaja en algo jurídico 1. Uso de IA: diario 11, semanal 10, mensual 3. Origen: kioscos 21, enlace 3.
→ **La muestra es casi totalmente «lega»**: no se puede todavía comparar con estudiantes de Derecho.

## 4. Resultados por prompt

| | Original (piloto) | Original (sorteado) | **Sencillo (sorteado)** |
|---|---|---|---|
| Comprensión (aciertos en opción múltiple) | 69 % | 61 % | 67 % |
| Comprensión cuando confianza alta (4–5) | 73 % (n=13) | 68 % (n=14) | 67 % (n=12) |
| Comprensión cuando confianza baja (1–3) | 63 % (n=8) | 38 % (n=4) | 67 % (n=12) |
| Confianza media (1–5) | 3.8 | 3.9 | 3.8 |
| «Sí actuaría con esta respuesta» | 57 % | 56 % | **75 %** |
| Notó algún problema | 5 % | 0 % | 13 % |
| Eligió «no está mi respuesta» | — (no existía) | 17 % | 13 % |
| SUS (usabilidad 0–100) | 70 | 78 | **84** |
| SUS «innecesariamente complicado» (1–5) | 2.7 | 2.2 | 1.9 |
| SUS «necesitaría ayuda de un experto» (1–5) | 2.1 | 2.0 | 1.4 |
| SUS «me sentí con confianza al usarlo» (1–5) | 3.1 | 4.0 | **4.6** |
| Minutos por situación (mediana) | 6.0 | **8.7** | 6.3 |
| Preguntas al asistente por situación | 1.6 | **2.1** | 1.5 |
| Palabras por respuesta del asistente | 501 | 510 | 544 |
| Respuestas en que el asistente pregunta el lugar | 12 % | 8 % | **35 %** |
| 1.ª respuesta cita el código correcto | 70 % | 63 % | 67 % |
| 1.ª respuesta cita el artículo correcto | 48 % | 42 % | 58 % |
| 1.ª respuesta **empieza** citando otro estado | 57 % | 68 % | 54 % |
| Respuestas que citan códigos de otro estado | 74 % | 50 % | 62 % |
| Recall@10 del artículo esperado (1.ª pregunta) | 33 % | 34 % | 40 % |

**Lectura (con cautela, n chico):**
- El sencillo **no mejora la comprensión**. Con 4 personas por grupo parecía que sí (79 % vs. 61 %); con 7–8 la
  diferencia casi desapareció. Fue ruido.
- El sencillo **sí cambia la experiencia**: más usable, menos «necesito un experto», más seguridad al usarlo,
  **más disposición a actuar**. Combinado con comprensión igual → **más confianza sin más comprensión** (riesgo de
  sobre-confianza). Además, con el sencillo la comprensión es la misma con confianza alta o baja (67 % y 67 %): la
  confianza **no distingue** cuándo la persona entendió bien (mala calibración).
- El original **cuesta más tiempo y más preguntas** (8.7 min, 2.1 preguntas): la gente repregunta porque no
  entiende a la primera (las quejas de jerga vienen de este grupo).
- **El sencillo no es más corto** (544 palabras): usa palabras más simples, pero escribe lo mismo. A la gente le
  gusta así («te da la información completa»).

## 5. Resultados por situación

| Situación | Comprensión | 1.ª pregunta dice el lugar | Recall@10 1.ª pregunta (con lugar / sin lugar) | Respuestas con otros estados | Notó problema | Min |
|---|---|---|---|---|---|---|
| Mensajes — Querétaro | 77 % | 36 % | **100 %** (4) / 43 % (7) | 48 % | 9 % | 7.6 |
| Mensajes — CDMX | 65 % | 33 % | **100 %** (4) / 38 % (8) | 48 % | 0 % | 6.0 |
| Las fotos | **52 %** | 23 % | 0 % (5) / 12 % (17) | 68 % | 10 % | 6.6 |
| El citatorio | 74 % | **76 %** | 41 % (16) / 20 % (5) | 73 %* | 5 % | 5.6 |

\* En el citatorio, mencionar la CDMX es correcto («no aplica el de la CDMX»): esa cifra está inflada.

**Respuestas a la opción múltiple (todas las fases):**
- *Mensajes Qro, «¿qué delito y ley?»*: 167 Ter (correcta) 8 · Morelos 158 1 · CPF 259 Bis 1 · no sé 1.
- *Mensajes CDMX*: CDMX 179 (correcta) 5 · CPF 259 Bis 2 · Morelos 158 1 · «no está» 2 (escribieron: *«el 269
  del código penal del edomex»*; *«hostigamiento sexual artículo 269 del código penal de la ciudad de México»* — el
  269 es del **Edomex**, lo atribuyó a la CDMX).
- *Fotos, «¿qué delito y ley?»*: Ley General de Extorsión art. 15 (la marcada como correcta) 5 · **CPF art. 390
  (derogado) 5** · Querétaro 167 Quinquies 4 · «no está» 4 (escribieron: *«código penal federal artículo 199»*,
  *«Artículo 150 bis y Artículo 194»*, *«el artículo 209 y el artículo 181, ley olimpia»*, *«Artículo 167 QUÁTER
  del Código Penal del Estado de Querétaro»*) · ningún delito 2 · no sé 1.
  - Ojo: **el asistente nunca citó el art. 390** (0 de 37 respuestas). Quienes lo eligieron siguieron su
    intuición («extorsión → Código Penal Federal»), no al asistente.
  - Está pendiente que la experta decida si el 167 Quinquies también cuenta como correcto (ver §9).
- *Fotos, «¿es delito aunque Cris mandó las fotos?»*: sí 17 · no 2 · «solo si ya se publicaron» 2.
- *Citatorio, «¿qué código aplica?»*: Querétaro 15 · **Federal 5** · no sé 1.

## 6. Hallazgos principales (con evidencia)

### H1. El asistente cita códigos de otros estados, aun cuando la persona dijo el estado
- 67 de 109 respuestas mencionan códigos penales de un estado distinto al de la situación (incluye el citatorio,
  donde mencionar CDMX puede ser correcto). Sin el citatorio: 68 % en «Las fotos» y 48 % en «Mensajes».
- En las respuestas dadas **después de que la persona ya dijo el estado** (63), **27 (43 %)** igual citaron otros
  estados.
- Ejemplo (prueba con el modelo real, pregunta sin estado): el prompt original citó **Estado de México 269 Bis y
  Querétaro 167 Bis**; el sencillo preguntó el estado… y en la misma respuesta citó **Edomex 269 y Morelos 158**.

### H2. La causa es la búsqueda, no la «imaginación» del modelo
- De las respuestas que citaron otros estados, **en 65 de 67 (97 %) esos estados estaban en los fragmentos que
  recuperó el buscador**; solo 2 los citó sin tenerlos en el contexto.
- El routing por código actual **agrega** una búsqueda restringida al estado mencionado, pero **no quita** los
  códigos de los demás estados → el modelo recibe una mezcla y la reproduce.
- Implicación: un **filtro de jurisdicción** (si se sabe el estado, solo ese código + leyes federales/generales)
  atacaría la causa principal.

### H3. La gente casi no dice el lugar, y cuando no lo dice el buscador falla más
- 1.ª pregunta dice el lugar: 36 % y 33 % (Mensajes), 23 % (Fotos); 76 % en el citatorio (la historia gira en
  torno al lugar).
- Mensajes: Recall@10 del artículo correcto **100 % con lugar vs. ≈ 40 % sin lugar**.
- Pero decir el lugar **no basta** (H1): ayuda al buscador, no impide que la respuesta mezcle estados.
- Cita: *«Considero que al quererte responder falta que te ayude a especificar en donde estas para ver las leyes
  en el que se adscriben»* (original). *«olvidé poner el estado por lo que la respuesta está sesgada»* (original).

### H4. Casi nadie detecta el error de jurisdicción
- «¿Notaste algún problema?»: 0–13 % según grupo, aunque más de la mitad de las respuestas citaban otros estados.
- «¿De qué estado era la ley que te citó?» (última situación, n=14): Querétaro 7, CDMX 2, federal/general 2,
  varios 1, otro 1, no me fijé 1. En la fase principal, de 10 conversaciones donde el asistente citó varios estados,
  solo **1** persona respondió «varios»; 7 dijeron **un solo** estado. Cuando el asistente cita **un** estado, la
  gente lo identifica bien (2/2). (Limitación: la pregunta no distingue «mencionó» de «dijo que aplica».)
- Los pocos que lo notan lo dicen al final: *«En la última situación la verdad no sé porqué citó leyes del Estado
  de Morelos, si el contexto estaba dado desde Querétaro»*; *«considero que en ocasiones mezcla los artículos»*.

### H5. Con «Las fotos», el lenguaje cotidiano no llega a la ley correcta
- Recall@10 del art. 15/17 de la Ley General de Extorsión: **9 %** en la 1.ª pregunta.
- La ley **sí aparece** (en 11 de 22 primeras preguntas algún fragmento suyo quedó en el top-3), pero ganan sus
  artículos **generales** (objeto de la ley, competencias, investigación), que repiten «extorsión», y no el art. 15,
  que define el delito en abstracto («obligue a otro a dar, hacer, dejar de hacer o tolerar algo…»).
- Además compiten **9 documentos sobre imágenes íntimas** por el top-10: códigos de CDMX (31 apariciones en top-10),
  Querétaro (27), Morelos (26), Federal (20), Edomex (12), «Violencia Digital» (15), ficha «Ley Olimpia» (12),
  libros de doctrina. La pregunta de la gente es sobre «fotos íntimas»; «me piden dinero» pesa menos.
- La ficha «Ley Olimpia» es una **tabla de los 32 estados**: si llega al contexto, invita a citar otros estados.
- Comentario de participante: *«Agreguen la palabra "chantaje" o términos más coloquiales»*.

### H6. Artículos contiguos casi homónimos se confunden: Querétaro 167 Quáter vs. 167 Quinquies
- 167 **Quáter**: *obtener* imágenes íntimas **sin consentimiento** (no aplica: Cris las mandó).
  167 **Quinquies**: *divulgar o amenazar con difundir* imágenes íntimas «obtenidas con o sin consentimiento»
  (sí aplica).
- El buscador favorece el Quáter (aparece en 22 rankings vs. 16; varias veces es el resultado #1 y el Quinquies
  ni aparece). Probable causa: el Quáter usa las palabras de la gente («imágenes íntimas», «se compartan…
  públicamente»); el Quinquies dice «imágenes eróticas sexuales», «amenace con difundir».
- Aun con ambos en el contexto, el modelo citó el Quáter. Total en «Las fotos»: **Quáter 6 citas, Quinquies 2,
  Ley de Extorsión art. 15: 2**.
- Detectado por la experta al revisar respuestas. Análogo a problemas previos con «Bis/Ter/Quáter» en el
  benchmark.

### H7. Lenguaje sencillo: más agrado y confianza, no más comprensión (hipótesis)
- Ver §4. Citas del grupo sencillo: *«Me gustó que es entendible el lenguaje que usa»*; *«No solo responde a mi
  pregunta, sino que también valida y reconoce las emociones de ese momento»*; *«te da la información completa…»*.
- Citas del grupo original: *«usa lenguaje muy técnico»*; *«me revolvía un poco con toda la terminología legal»*;
  *«la parte de Querétaro y Ciudad de México me quedé con dudas»*.
- Riesgo FAccT: si el estilo sencillo sube la disposición a actuar (75 % vs. 56 %) sin subir la comprensión, la
  claridad sin precisión puede aumentar el daño.

### H8. Señales de cautela espontánea
- Varias personas escribieron que corroborarían: *«buscaría en las fuentes para confirmar y buscar la info
  oficial»*, *«Es necesario que verifiquen las respuestas que da y el fundamento legal»*, *«Sí, con asistencia
  jurídica para corroborar lo dicho por el asistente»*, *«no, confío más en una persona preparada»*.
- Pero **75 %** (sencillo) y **56 %** (original) dijeron que sí actuarían con la respuesta.

### H9. Otros problemas que reportaron
- *«Le redacté la situación en tercera persona y respondió como si la víctima fuera yo»* (el sistema asume
  primera persona).
- *«como tal no me explicó del todo lo que pedí, en lugar de eso me entregó muchas cosas relacionadas»*;
  *«no te entrega la información de la situación solicitada y te envía generalidades»*.
- *«no me dijo qué protocolo se debe activar en mi trabajo, y tengo miedo que… me corran»* (falta orientación
  práctica/laboral, fuera del corpus penal).
- *«La legislación a que hace referencia la pregunta, no aparece en la respuesta»* (Fotos).

## 7. Benchmark experto de prompts (sin personas; 12-oct)

Mismas preguntas del benchmark de la experta (con estado explícito), misma configuración del estudio, juez = el
mismo Gemma con criterios must/should/error. Corridas 37–42, etiqueta `prompts-2026-10-12`.

| Prompt | Set 3: generales (50) | Set 11: comparativas CDMX vs. Querétaro (57) |
|---|---|---|
| A. Original (jurídico) | 76 % | 79 % |
| B. Sencillo de Karen tal cual (sin «usa solo el CONTEXTO») | **38 %** | 68 % |
| C. Sencillo + «usa solo el CONTEXTO» (el del estudio) | 76 % | 63 % |

- La regla «responde solo con el CONTEXTO y cita artículo y código» es **indispensable** (B → C: 38 % → 76 %).
- En comparativas, el sencillo pierde ~9 preguntas de 57 (más que el ruido típico de ±3).
- Advertencia: el juez exige el artículo exacto (favorece el estilo jurídico) y es el mismo modelo.

## 8. Benchmark automático de jurisdicción (13-oct)

*(Sección completada al terminar la corrida; ver al final del documento.)*

## 9. Decisiones y cambios durante la ronda 1 (para el método)

| Fecha | Cambio |
|---|---|
| 8–9 oct | Situaciones redactadas sin género; top-k 10 con vecinos visibles; streaming; sin «volver al chat» al pasar a las preguntas; opciones con artículo exacto y orden aleatorio |
| 9 oct | Karen validó respuestas de referencia y artículos esperados |
| 9 oct | Aviso bajo la situación cambiado a la versión neutral (la explicación verbal del piloto lo motivó) |
| 9 oct | Karen agregó al corpus «Ley Olimpia», «Violencia Digital» y una tesis |
| 12 oct | Fase principal: 2 prompts sorteados; opción «no está mi respuesta»; pregunta del estado en la última situación; métricas automáticas |
| — | Sin cambios al corpus penal ni al sistema desde el 12-oct |

## 10. Limitaciones y amenazas a la validez

- **n pequeño** (7–9 por grupo); ninguna diferencia está probada estadísticamente.
- **Muestra casi sin Derecho** (1 persona): no se puede comparar formación jurídica vs. lega.
- **El piloto no fue sorteado** y tuvo explicación verbal; usarlo solo como análisis complementario.
- **Juez automático = el mismo modelo**; no hay todavía calificación humana de las respuestas (104 pendientes en
  `/calificar`).
- **Respuesta «correcta» discutible** en «Las fotos» (¿solo Ley de Extorsión, o también 167 Quinquies?).
- La pregunta del estado citado es ambigua (mencionar ≠ aplicar).
- El prompt sencillo cambia varias cosas a la vez (estilo, estructura, pedir el estado): no se puede atribuir el
  efecto a una sola.
- Detección automática de «otros estados» por nombres de códigos: cuenta menciones, incluso «no aplica el de…».

## 11. Propuesta para la ronda 2

**Objetivo:** mostrar que las fallas son **corregibles por diseño** y medir el efecto en personas.

1. **Filtro de jurisdicción en la búsqueda** (ataca H1–H2): si el estado se sabe (lo dijo la persona o se
   preguntó), restringir los códigos estatales a ese estado + leyes federales/generales. Si no se sabe: buscar
   igual, pero **no** citar artículos estatales hasta saberlo.
2. **Prompt con disciplina de jurisdicción** (ataca H1, H4): «si ya sabes el estado, cita solo su código y leyes
   federales/generales; nunca presentes artículos de otros estados como aplicables; si no sabes el estado,
   pregúntalo primero». Validarlo con el benchmark de §8 hasta que la tasa de «otros estados» baje.
3. **Mejor recuperación de artículos definitorios y contiguos** (H5–H6): reordenamiento (*reranker*), o agregar
   a cada artículo una descripción en lenguaje cotidiano («amenazar con publicar fotos íntimas»), o un HyDE que
   genere vocabulario de la gente. Medir con el benchmark experto + preguntas reales de la ronda 1.
4. **Mantener el estilo sencillo** (gusta, ahorra tiempo) pero vigilar la sobre-confianza: medir de nuevo
   comprensión vs. confianza vs. disposición a actuar.
5. **Diseño**: mismas 3 situaciones, **personas nuevas**, sorteo **original vs. corregido**; reclutar estudiantes
   de Derecho; arrancar la calificación humana ciega (2 estudiantes de Derecho + la experta para desempates).
6. **Antes de abrir**: validar el sistema corregido con (a) benchmark experto, (b) benchmark de jurisdicción,
   (c) repetición de las preguntas reales de la ronda 1.

**Calendario tentativo:** 13–14 oct cierre y documento · 14–16 oct correcciones + benchmarks · 16–22 oct
sesiones ronda 2 · 23–27 oct análisis + abstract · hasta 3 nov paper.

## 12. Preguntas abiertas (para la experta / para discutir)

1. «Las fotos»: ¿cuenta como correcta solo la Ley de Extorsión art. 15, o también Querétaro 167 Quinquies (y la
   «Ley Olimpia»)? (Se puede re-puntuar hacia atrás sin perder datos.)
2. ¿El filtro de jurisdicción debe permitir siempre leyes federales/generales? ¿Y el CNPP?
3. ¿Qué cuenta como «error de jurisdicción dañino» para la escala de daño de la calificación humana?
4. ¿Cuántos estudiantes de Derecho pueden calificar, y cuándo?
5. ¿Vale la pena separar en la ronda 2 «estilo sencillo» de «pedir el estado» (2×2), o comparar solo original vs.
   corregido (más simple, menos inferencia causal)?

## 13. Dónde están los datos y el código

- App en producción: estudio `/estudio` (participantes), `/calificar` (calificación ciega), `/estudios` (admin,
  con resumen por condición, por situación, por fase y vista por participante).
- Código: `labs/apps/rewrite_lab/study/` (store, API, análisis), páginas en `labs/apps/rewrite_lab/static/`.
- Definición del estudio: en la base de datos (editable en `/estudios`); copia en
  `labs/apps/rewrite_lab/study/estudios/piloto_penal.yaml`.
- Prompts y lanzador del benchmark de prompts: `labs/06_evaluation/prompts_2026-10-12/`.
- Scripts de este análisis: `labs/06_evaluation/estudio_ronda1_2026-10-13/` (`ronda1.py`, `bench_jurisdiccion.py`).
- Datos crudos por participante: **no** están en git (seudónimos, pero con texto libre); se exportan desde
  `/estudios` → «Exportar JSON».
