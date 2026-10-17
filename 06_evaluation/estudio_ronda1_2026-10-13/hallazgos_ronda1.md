# Ronda 1 del estudio con usuarios: hallazgos, causas y plan para la ronda 2

> **Para quien lea esto (personas o un asistente de IA):** este documento es autocontenido. Resume un
> estudio con usuarios de un asistente jurídico con RAG (retrieval-augmented generation) sobre derecho penal
> mexicano, hecho para un paper en **ACM FAccT 2027** (abstract: 27-oct-2026; paper: 3-nov-2026).
> Los números de §0–§9 vienen de la base de datos de producción al **13-oct-2026**; la **§5b** agrega a las
> personas de **Derecho** que contestaron el 14–15 oct (datos al 15-oct). **La ronda 1 sigue abierta** (se
> está completando el grupo de Derecho); el sistema no se ha modificado desde el inicio de la fase principal. Las cifras son **preliminares**: los grupos son chicos (7–9 personas) y nada de esto tiene todavía
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
   Según la experta, el error de fondo es de **subsunción**: el caso parece acoso por difusión de imágenes
   (167 Quinquies), pero el **lucro** lo convierte en **extorsión**; el sistema no detecta ese elemento decisivo.
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

**Actualización 15-oct — participantes de Derecho (§5b, n = 11, preliminar):**

13. **Derecho entiende más pero actuaría menos**: comprensión 81 % (original) / 70 % (sencillo) vs. 62–67 % sin
    formación jurídica; seguridad en su respuesta 4.7 vs. 3.8; pero solo 40–44 % actuaría con la respuesta (vs.
    62–75 %). Su desconfianza es explícita: «lo usaría de guía», «hay que corroborar la ley y su vigencia».
14. **Tampoco detectan los errores**: 46–76 % de las respuestas citan códigos de otro estado; solo 11–27 % de las
    personas de Derecho dijo notar un problema. En Mensajes-Querétaro, 2 de 4 eligieron el art. 179 **de la CDMX**.
15. **El grupo más expuesto es el no-jurídico con prompt sencillo**: más disposición a actuar (75 %) y mejor
    calificación (SUS 84) con comprensión de solo 67 %.
16. Lo que piden las personas de Derecho coincide con la ronda 2: *«debería interrogar previamente respecto a la
    situación en particular… es bastante genérico»*.

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
**(Actualización 15-oct: ya hay 11 personas con formación jurídica que terminaron; ver §5b.)**

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
  - **Regla de calificación (decidida 14-oct):** cuenta como correcta si menciona **extorsión (Ley General) o el
    167 Quinquies**. El **Quáter** es incorrecto (castiga *obtener* imágenes sin consentimiento; Cris las mandó).
    Con esta regla, esta pregunta pasa de 5 a **9 correctas** (5 Ley de Extorsión + 4 Quinquies). La experta
    señala que el lucro hace que sea extorsión (H6b); el Quinquies se acepta porque la amenaza de difundir sí
    está en los hechos.
- *Fotos, «¿es delito aunque Cris mandó las fotos?»*: sí 17 · no 2 · «solo si ya se publicaron» 2.
- *Citatorio, «¿qué código aplica?»*: Querétaro 15 · **Federal 5** · no sé 1.

## 5b. Participantes con formación jurídica (14–15 oct; datos al 15-oct)

Se abrió un enlace propio para personas de Derecho (enlace #12, grupo «estudiante», cupo 20) el 14-oct; el sorteo
de prompt y variantes se balancea dentro de ese grupo. **Mismo sistema, mismas situaciones, mismos prompts** que
la fase principal. Clasificación «Derecho» = área Derecho en el perfil **o** formación jurídica «carrera» o
«trabajo» (igual que `analisis.grupo_de`); con esa regla entra 1 persona de Ciencias de la Comunicación que
declaró formación jurídica.

**Muestra (Derecho):** 16 consintieron, **11 terminaron** (6 original, 5 sencillo; 33 situaciones). Semestre: 9.º 8,
7.º–8.º 4, posgrado 3, 5.º–6.º 1. Formación jurídica: trabaja en algo jurídico 9, carrera 7. Uso de IA: mensual 7,
semanal 3, diario 3, nunca 3. Confianza previa en IA (1–5): mayoría 4–5.

**Totales del estudio al 15-oct:** 40 personas aceptaron el consentimiento y **33 terminaron** (22 sin formación
jurídica + 11 de Derecho); «terminó» = completó las 3 situaciones y el cuestionario final (`terminado_at`). Nadie
quedó con las 3 situaciones hechas pero sin cuestionario final.

### Derecho vs. sin formación jurídica

| | Derecho, original | Derecho, sencillo | No-Derecho, original | No-Derecho, sencillo | Piloto (no-Derecho, original) |
|---|---|---|---|---|---|
| Terminaron | 6 | 5 | 7 | 8 | 7 |
| Comprensión (opción múltiple) | **81 %** | 70 % | 62 % | 67 % | 69 % |
| Comprensión con confianza alta (4–5) | 78 % (n=16) | 71 % (n=12) | 68 % (n=14) | 67 % (n=12) | 73 % (n=13) |
| Seguridad en su respuesta (1–5) | **4.7** | 4.3 | 3.8 | 3.8 | 3.8 |
| «Sí actuaría con esta respuesta» | 44 % | 40 % | 62 % | **75 %** | 57 % |
| Notó algún problema | 11 % | 27 % | 5 % | 12 % | 5 % |
| SUS (0–100) | 75 | 70 | 75 | **84** | 70 |
| Preguntas al asistente por situación | 1.7 | 1.3 | 2.0 | 1.5 | 1.6 |
| El asistente pregunta el lugar | 10 % | **42 %** | 7 % | 35 % | 12 % |
| Respuestas que citan otro estado | 63 % | 58 % | 46 % | 62 % | 76 % |
| 1.ª respuesta cita el código correcto | 56 % | 80 % | 59 % | 67 % | 68 % |
| Recall@10 del artículo esperado (1.ª pregunta) | 33 % | 50 % | 30 % | 40 % | 30 % |

(Las cifras «no-Derecho» difieren un poco de §4 porque aquí la clasificación es por perfil y no por grupo de
enlace, y se incluye a quienes terminaron hasta el 15-oct.)

### Por situación (Derecho, n de situaciones entre paréntesis)

- **El citatorio (11)**: comprensión 91 % (no-Derecho 73 %). «¿Qué código aplica?»: Querétaro 10, federal 1 (en
  no-Derecho, **federal 6 de 22**). «¿Puede pedir que lo lleven en la CDMX?»: no 10, sí 1.
- **Mensajes – CDMX (7)**: CDMX 179 (correcta) 5, CPF 259 Bis 2. Jerarquía «más grave»: 7 de 7.
- **Mensajes – Querétaro (4)**: Querétaro 167 Ter (correcta) 2, **CDMX 179 2** → error de jurisdicción también en
  Derecho (n muy chico). Jerarquía «más grave»: 4 de 4.
- **Las fotos (11)**: Querétaro 167 Quinquies 5, Ley General de Extorsión art. 15 3, **CPF art. 390 (derogado) 2**,
  otra 1. Con la regla «extorsión o Quinquies = correcta»: **8 de 11 (73 %)** vs. 10 de 22 (45 %) en no-Derecho;
  con «solo extorsión»: 3 de 11 vs. 6 de 22. «¿Es delito aunque Cris mandó las fotos?»: sí 9, no 1, «solo si ya
  se publicaron» 1. El art. 390 (7 personas en total) **nunca** lo citó el asistente: viene del conocimiento previo.
  Texto en «otra»: *«La inteligencia no aportó nada sobre el estado de Querétaro, se centró en la CDMX y el código
  FEDERAL»*.
- En las 15 respuestas del asistente a Derecho en «Las fotos»: Quáter 3, Quinquies 3, extorsión art. 15 2, «Ley
  Olimpia» 4.
- Última pregunta («¿de qué estado era la ley que citó?»): Querétaro 8, CDMX 1, varios 1, nacional 1.

### Cómo preguntan las personas de Derecho

- **Con lenguaje técnico y pocas preguntas** (1.3–1.7 por situación): *«¿Qué legislación penal y qué autoridad
  ministerial son competentes para investigar una agresión física ocurrida en el estado de Querétaro…?»*,
  *«Características de la extorsión»*, *«Que elementos se necesitan para acreditar el acoso laboral en la CDMX»*.
- **Dicen el lugar mucho más**: 82 % en el citatorio, 88 % en Mensajes-CDMX (no-Derecho: 25–36 % en Mensajes).
- **Varias personas pegaron el texto completo de la situación** («Ariel vive y trabaja en la Ciudad de México…»,
  «Cris tiene 24 años y vive en Querétaro…»), aunque la instrucción pide «con tus propias palabras». Esto infla
  «dice el lugar» y el recall.
- **Algunas cambiaron los hechos** a lugares fuera del corpus (Puebla, Estado de México, «Zihuatanejo, Guerrero»):
  prueba involuntaria de cobertura; conviene revisar qué respondió el asistente ahí (¿avisa que no tiene ese
  código o cita otro estado como si aplicara?).

### Lo que dijeron (textual)

- Confianza: *«Lo utilizaría de guía, pero no confiaría del todo en él.»* · *«No, siempre es mejor consultar a un
  profesional.»* · *«No, porque… hay que verificar la información porque en ocasiones puede inventar o confundir
  información.»* · *«Sí confiaría, resolvió mis dudas de inmediato y con fundamento legal. Después buscaría a un
  abogado.»* · *«Podría ser usado como referencia, mas mi actuar no podría estar únicamente basado en un modelo de
  IA.»* · *«Debería corroborarlo en la ley y su vigencia.»*
- Calidad: *«Debería interrogar previamente respecto a la situación en particular, ya que desarrolla temas que
  pueden llegar a confundir, es decir, es bastante genérico.»* · *«Es genérico y no vincula del todo las respuestas
  que va dando.»* · *«No es concreto y sus respuestas no siguen un hilo con las dadas anteriormente.»* · *«Dio
  información general, mas no respondió como tal la pregunta planteada.»* · *«Le falta… responder de manera más
  objetiva y precisa a lo que se le pregunta.»*
- Positivo: *«Me gusta que el asistente manifieste empatía por mi situación»* (sencillo) · *«Las respuestas fueron
  muy claras y precisas»* (sencillo).
- Sobre el instrumento: *«No le pregunté si debía hacer algo, por eso no sé la respuesta a esta pregunta»* →
  la pregunta «¿actuarías?» se interpreta distinto según lo que preguntó cada quien.

### Lectura

1. **Más conocimiento → más escepticismo, no más detección.** La gente de Derecho acierta más y desconfía más
   (actuaría menos, SUS más bajo), pero **igual casi no detecta** que el asistente cita otros estados. La
   desconfianza es *general* («hay que verificar»), no *calibrada* a los errores concretos.
2. **La protección del experto viene de su conocimiento, no del asistente**: en Mensajes y Fotos aciertan más que no-Derecho
   con respuestas igual de mezcladas (46–63 % citan otro estado; en el citatorio la cifra no sirve porque mencionar la
   CDMX ahí es legítimo). Quien no tiene formación jurídica no tiene esa defensa → refuerza el
   argumento de equidad del paper (el daño se concentra en quien menos puede detectarlo).
3. **Derecho prefiere el original** (comprensión 81 % vs. 70 %; SUS 75 vs. 70), al revés que no-Derecho (sencillo
   SUS 84 vs. 75). Pero depende de las respuestas rápidas (ver abajo): **no concluir todavía**.
4. Sus críticas («interrogar previamente», «genérico», «no sigue un hilo») apoyan la propuesta de la ronda 2:
   identificar los **hechos decisivos** y preguntarlos antes de responder.

### Calidad de datos (decidir la regla antes de ver más resultados)

- **3 personas de Derecho con prompt sencillo** completaron casi todas sus situaciones en **< 2 minutos con una sola
  pregunta** (situaciones de 0.8–2.0 min); dos de ellas dieron SUS 40–42.5. Propuesta: regla de exclusión
  pre-registrada (p. ej. < 2 min por situación o 0 preguntas propias) y reportar resultados **con y sin** ellas.
- La diferencia «Derecho original 81 % vs. sencillo 70 %» depende en buena parte de esas 3 personas.
- n = 5–6 por celda: todo esto es descriptivo.

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

### H6a. Diagnóstico: por qué la búsqueda trae el Quáter (14-oct, solo lectura)
Scripts `diag_quater.py`, `diag_desc.py`, `diag_hechos.py`, `diag_ext.py` (1.ª pregunta real de «Las fotos», 23
preguntas; posición del artículo en el ranking; 999 = no aparece).

| Buscador | Quáter (mediana / top-3) | Quinquies | LG art. 15 | LG art. 17 |
|---|---|---|---|---|
| Denso, solo la pregunta | 22 / 3 de 35 | 68 / 1 | 385 / 0 | 252 / 1 |
| Denso + HyDE (como en el estudio) | 8 / 6 de 23 | 11 / 5 | 65 / 0 | 23 / 0 |
| BM25 | ≈2 300 | ≈3 800 | ≈3 600 | ≈2 500 |

- **El buscador semántico prefiere el Quáter**: su texto usa las palabras de la gente («imágenes o videos de las
  partes íntimas», «se compartan a un tercero o públicamente»); el Quinquies dice «imágenes eróticas sexuales»,
  «divulgue o amenace con difundir» y es corto (77 palabras). **BM25 no encuentra ninguno**: las palabras de la
  gente («fotos», «nudes», «pack», «publicar») no están en los artículos.
- **El modelo** elige el Quáter aunque el Quinquies esté en el contexto: el 2.º párrafo del Quáter habla de
  compartir/publicar, y el modelo no verifica el elemento «sin consentimiento». Misma falla de subsunción que H6b.

**Arreglos probados (simulación, sin tocar la base):**
1. *Descripción en lenguaje cotidiano por artículo* (generada por el LLM con un prompt neutro, sin conocer el
   caso, y embebida junto al texto): Quinquies **11 → 4** de mediana, top-3 **5 → 11** de 23; pasa al Quáter.
   LG art. 15: 65 → 36. *Ojo:* solo se re-embebieron 6 artículos; la prueba real exige hacerlo en todo el corpus.
2. *«Hechos decisivos → delitos candidatos»* (el LLM enumera los hechos que cambian el delito y nombra los delitos
   posibles; se busca eso como sub-consulta): el LLM **sí identifica «extorsión»** en todos los ejemplos
   («exigencia de dinero para evitar la difusión»). LG art. 17 (agravante por usar imágenes privadas) entra al
   top-10 en **15 de 23** (antes 4). El art. 15 sigue fuera (mediana 33): es un artículo abstracto.
3. *Qué estorba*: en esa sub-consulta el top-10 lo ocupan «Violencia Digital» (53), Morelos (39), ficha «Ley
   Olimpia» (35), CDMX (20), Edomex (11): los equivalentes de **otros estados** (CDMX 181 Quintus, Morelos 150 Bis).
   Quitar los otros estados mejora poco el art. 15 (33 → 24).
4. **El filtro de jurisdicción hoy no funciona** para Querétaro: en la base, 45 documentos (Querétaro, Morelos, Ley
   de Extorsión, doctrina…) tienen `jurisdiction='general'`; solo CDMX, CPF, CNPP y Edomex tienen etiqueta propia.
   Hay que re-etiquetar antes de filtrar.
5. Propuesta para el art. 15: **seguir referencias cruzadas**. El art. 17 dice «además de las penas señaladas en el
   **artículo 15** de la presente Ley»: si llega el 17, traer también el 15 (lo mismo para «Bis/Ter…» de un tipo base).

### H6b. El elemento que decide el delito (el lucro) se pierde: Quinquies «parece» correcto, pero es extorsión
Criterio de la experta (Karen, 14-oct), en sus palabras resumidas:
- El asistente se confunde porque la conducta **sí tiene los elementos** del acoso sexual en su modalidad de
  divulgación o **amenaza de difusión** de material erótico (Querétaro, art. 167 Quinquies).
- Pero en el caso de Cris hay un **elemento imperante**: la **intención de obtener un lucro o beneficio
  económico** («si no le deposita 5,000 pesos…»). **Con ese elemento la conducta se convierte en extorsión**
  (Ley General en materia de Extorsión, art. 15; agravantes del art. 17 fr. IV —usar imágenes privadas— y fr. V
  —medios electrónicos—).

Por qué importa (para el paper):
- No es solo un problema de «encontrar el artículo»: es de **subsunción**. El sistema empareja por **parecido
  superficial** (fotos íntimas + amenaza de publicarlas → artículos sobre imágenes íntimas) y pierde el
  **elemento típico que distingue** un delito de otro (pedir dinero).
- Las tres capas fallan en la misma dirección:
  1. *Pregunta de la gente*: describe sobre todo las fotos; el dinero aparece de pasada («me piden dinero»).
  2. *Búsqueda*: los artículos sobre imágenes íntimas comparten vocabulario con la pregunta; el art. 15 de
     extorsión está redactado en abstracto («obligue a otro a dar… obteniendo un lucro») y no menciona fotos.
  3. *Modelo*: aun cuando el art. 15 está en el contexto, rara vez razona «hay lucro → extorsión».
- Daño potencial: con el 167 Quinquies la pena es de 3 a 6 años; con extorsión agravada, 15 a 25 años más
  5 a 12. Encuadrar mal **subestima la gravedad** y puede orientar mal la denuncia.
- Es un hallazgo general, no de este caso: en derecho penal, **un solo elemento** (lucro, jerarquía laboral,
  consentimiento, lugar) cambia el delito aplicable. H1–H3 (lugar) y H6b (lucro) son la misma falla: el sistema
  no identifica qué **hechos jurídicamente decisivos** necesita y no los usa para elegir la norma.

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

Sin personas y sin juez. Preguntas: la **1.ª pregunta real** de cada participante en cada situación (ronda 1).
Cada una se corre tal cual y, si no decía el lugar, también con «Esto pasó en <estado>.» al final. Misma
configuración del estudio (híbrido, k=10, vecinos, HyDE, descomponer, routing). Conteo automático de códigos
citados (script `bench_jurisdiccion.py`; resultados en prod `/tmp/bench_jurisdiccion_AC.json`). 214 corridas,
2 errores (el LLM remoto falló de forma intermitente; se repitieron solo las fallidas).

| Prompt | Pregunta | n | Cita otro estado | …y venía en el contexto | Pide el lugar | Cita el estado correcto | Palabras |
|---|---|---|---|---|---|---|---|
| Original | dice el lugar | 30 | 27 % | 88 % | 7 % | 93 % | 478 |
| Original | **no** dice el lugar | 39 | **85 %** | 97 % | 10 % | 28 % | 545 |
| Original | lugar agregado | 39 | 33 % | 100 % | 3 % | 97 % | 472 |
| Sencillo | dice el lugar | 30 | 17 % | 60 % | 40 % | 97 % | 545 |
| Sencillo | **no** dice el lugar | 38 | 74 % | 100 % | **82 %** | 29 % | 556 |
| Sencillo | lugar agregado | 38 | 21 % | 100 % | 8 % | **100 %** | 516 |

Lectura:
- **Decir el lugar es lo que más cambia**: citar otros estados baja de 74–85 % a 17–33 %, y citar el estado
  correcto sube de ≈ 28 % a 93–100 %. Agregar una sola frase con el lugar a la misma pregunta produce casi el
  mismo efecto que haberlo dicho: el lugar es **el** dato decisivo.
- **La causa es la búsqueda**: cuando cita otro estado, ese código venía en el contexto en 88–100 % de los casos
  (salvo «sencillo + dice el lugar», 60 %, con pocos casos).
- **El prompt sencillo pregunta el lugar** cuando falta (82 % vs 10 %), pero **igual cita otros estados** (74 %):
  pregunta *y además* responde con lo que trajo la búsqueda.
- Aun con el lugar, 1 de cada 4–5 respuestas sigue citando otro estado: ahí el filtro de jurisdicción es el
  arreglo natural (ver H6a: hoy las etiquetas de estado de la base no lo permiten para Querétaro).
- Limitación: «cita» = el código aparece en la respuesta (puede ser para decir que no aplica); en el citatorio se
  permite mencionar la CDMX.

## 8b. Benchmark «Jurisdicción · un solo estado» (set 13, 17-oct)

**Cierre de la ronda 1: 17-oct-2026** (se desactivaron todos los kioscos, enlaces y códigos sin terminar; la
calificación ciega sigue disponible). **Muestra final: 40 consintieron, 33 terminaron (22 sin formación jurídica,
11 de Derecho).**

Set nuevo en la pestaña 🧪 Benchmark de prod: **31 preguntas en lenguaje cotidiano que dicen UN solo estado** (CDMX 8,
Querétaro 8, Estado de México 7, Morelos 8) sobre 8 delitos (robo, fraude, amenazas, violencia familiar, acoso con
jerarquía/acoso, imágenes íntimas, allanamiento, despojo). Cada pregunta: *must* = el artículo del código de ese
estado (verificado en el corpus), *should* = explicar que aplica la ley del lugar de los hechos, *must_not* =
«presenta como aplicable un artículo del código penal de otra entidad». Configuración del estudio (híbrido, k=10,
vecinos, HyDE, descomponer, routing). Además del juez, un conteo **sin juez** de los artículos de otra entidad
que cita cada respuesta (`06_evaluation/jurisdiccion_2026-10-17/analizar_set.py`).

| | Original (run 43) | Sencillo (run 44) |
|---|---|---|
| **Cita artículos de otra entidad** (conteo sin juez) | **19 %** (6/31) | **10 %** (3/31) |
| Juez: presenta otra entidad como aplicable | 16 % (5/31) | 10 % (3/31) |
| Acuerdo juez vs. conteo sin juez | 30/31 | 31/31 |
| Pasa (artículo correcto y sin violación) | 68 % | 81 % |
| El artículo correcto llegó al contexto | 84 % | 90 % |

- **Aun diciendo el estado de forma explícita, 1 de cada 5–10 respuestas cita artículos de otro estado** (p. ej.
  robo en la CDMX respondido con los arts. 287, 290 y 293 del Edomex; amenazas en la CDMX con el art. 148 de Morelos;
  violencia familiar en Querétaro con el 202 Bis de Morelos).
- Coincide con el benchmark de jurisdicción con preguntas reales (§8: 17–33 % con el lugar dicho).
- El juez y el conteo sin juez coinciden casi siempre: el conteo automático sirve como métrica barata.
- Cautela: una corrida por prompt; el HyDE no es determinista (el «llegó al contexto» varía 84 % vs. 90 % con la
  misma configuración), así que diferencias de pocos puntos son ruido.

## 8c. Verificación de citas: ¿el modelo inventa artículos? (17-oct, sin juez)

Script `06_evaluation/citas_2026-10-17/verificar_citas.py`. Para cada artículo citado en una respuesta: se identifica
la ley (la nombrada junto al artículo en la misma oración, o el encabezado de la columna en tablas; si no se puede
saber, «sin ley identificable» y no se clasifica) y se verifica contra el corpus y contra el contexto recuperado.

| Fuente | Respuestas | Citas clasificadas | En el contexto | Fuera del contexto (memoria) | Atribución cruzada | **No existe** |
|---|---|---|---|---|---|---|
| Estudio de usuarios (ronda 1) | 161 | 436 | 95.6 % | 3.7 % | 0.7 % | **0** |
| Benchmark set 3, prompts A/B/C (runs 40–42) | 150 | 264 | 88–100 % | 0–3.7 % | 0–2.2 % | **0** |
| Benchmark set 11, prompts A/B/C (runs 37–39) | 171 | 414 | 100 % | 0 % | 0 % | **0** |
| Jurisdicción, original / sencillo (runs 43–44) | 62 | 109 | 93–96 % | 3–7 % | 0–1.5 % | **0** |

- **Ya está en la página (18-oct):** cada corrida del 🧪 Benchmark calcula esto solo (columnas «📎 sin fuente»,
  «🔴 inexist.», «🗺️ otro edo.», tarjeta «🧾 citas verificadas», etiquetas por pregunta y filas en la comparación;
  código en `apps/rewrite_lab/citations.py`). Las 41 corridas anteriores se recalcularon desde su artefacto: **4 542
  citas clasificadas, 1 inexistente** (corrida #13 del 1-oct). La versión de la página compara el contexto también
  por (ley, artículo), porque los ids de los chunks cambian al reingestar; por eso sus cifras difieren un poco de la
  tabla de arriba (p. ej. run 43: 98 % en contexto, 0 % de memoria, 1.6 % cruzada; run 44: 98 %, 2.4 %, 0 %).
- **Ninguna cita a un artículo inexistente** en ~1 200 citas verificadas: con este RAG el modelo **no inventa
  números de artículo**.
- **≈ 4 % de las citas no venían en el contexto** (el modelo las tomó de su memoria, aunque el prompt pide usar solo
  el contexto). Revisadas a mano en el estudio (15 de 16): casi todas del **CNPP** (arts. 311, 312, 316, 335, 337,
  153, 137, 138…) y parte general del CPF; **parecen correctas**, pero no están fundamentadas en lo recuperado.
- **Atribución cruzada** (raro, < 1 % en el estudio, pero dañino): el número existe en el contexto, pero con OTRA ley.
  Ejemplos reales: *«Artículo 269 del Código Penal de la Ciudad de México»* (el 269 es del **Edomex**) y *«Artículo
  150 BIS del Código Penal de la CDMX»* (es de **Morelos**). Es la versión «a nivel artículo» de la mezcla de estados.
- **Lectura para el paper:** el riesgo principal no es la alucinación clásica (inventar), sino **citar artículos
  reales del estado equivocado** (§8, §8b) y, en menor medida, mal atribuirlos.
- **Limitaciones:** 20–50 % de las citas quedan «sin ley identificable» (artículo suelto en prosa comparativa) y no se
  clasifican; el emparejamiento se depuró revisando a mano todos los casos dudosos del estudio (≈ 1 error residual en
  21); no verifica que el **contenido** atribuido al artículo sea correcto (eso requiere juez o revisión humana).
  «Derogado»: el texto del corpus empieza con «se deroga»; 0–3 por corrida, casi siempre citado precisamente para
  decir que está derogado.

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
- **Respuesta «correcta» en «Las fotos»**: se acepta extorsión o 167 Quinquies (decidido 14-oct, después de ver
  los datos). Reportarlo y dar los resultados con ambas reglas (solo extorsión / extorsión o Quinquies).
- La pregunta del estado citado es ambigua (mencionar ≠ aplicar).
- **Copiar y pegar la situación** (sobre todo en Derecho) en vez de preguntar con sus palabras; y **respuestas muy
  rápidas** (< 2 min por situación). Definir y reportar una regla de exclusión.
- **La composición por enlace difiere**: Derecho entró casi todo por un enlace propio (en casa); los no-Derecho
  por kioscos (en persona, con alguien presente). Lugar y supervisión pueden explicar parte de las diferencias.
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
3. **Identificar los hechos decisivos antes de buscar** (H3, H6b): un paso que extraiga de la pregunta los
   elementos que cambian el delito (lugar, ¿piden dinero o algo a cambio?, relación jerárquica, consentimiento,
   edad) y que los use para (a) reformular la búsqueda en términos jurídicos («obtener un lucro → extorsión») y
   (b) preguntar a la persona lo que falte. Medirlo con el benchmark de jurisdicción y con «Las fotos».
4. **Mejor recuperación de artículos definitorios y contiguos** (H5–H6): reordenamiento (*reranker*), o agregar
   a cada artículo una descripción en lenguaje cotidiano («amenazar con publicar fotos íntimas»), o un HyDE que
   genere vocabulario de la gente. Medir con el benchmark experto + preguntas reales de la ronda 1.
5. **Mantener el estilo sencillo** (gusta, ahorra tiempo) pero vigilar la sobre-confianza: medir de nuevo
   comprensión vs. confianza vs. disposición a actuar.
6. **Diseño**: mismas 3 situaciones, **personas nuevas**, sorteo **original vs. corregido**; reclutar estudiantes
   de Derecho; arrancar la calificación humana ciega (2 estudiantes de Derecho + la experta para desempates).
7. **Antes de abrir**: validar el sistema corregido con (a) benchmark experto, (b) benchmark de jurisdicción,
   (c) repetición de las preguntas reales de la ronda 1.

**Calendario tentativo:** 13–14 oct cierre y documento · 14–16 oct correcciones + benchmarks · 16–22 oct
sesiones ronda 2 · 23–27 oct análisis + abstract · hasta 3 nov paper.

## 12. Preguntas abiertas (para la experta / para discutir)

1. ~~«Las fotos»: ¿cuenta como correcta también el 167 Quinquies?~~ **Resuelto (14-oct): extorsión o Quinquies
   cuentan como correctas; Quáter no.**
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
