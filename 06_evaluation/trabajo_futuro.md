# Trabajo futuro y experimentos pendientes (después del envío a FAccT, noviembre de 2026)

Reúne lo que quedó pendiente o se propuso en el paper, en los análisis y en la revisión de los revisores. Cada punto
dice qué hacer, por qué (el dato que lo motiva) y de dónde sale. Ordenado por prioridad.

---

## A. Validaciones que no dio tiempo de hacer (lo primero: el paper las declara como limitación)

Las hojas ya están listas en iCloud `tlacua/research/AAAI/faact/`, con su clave aparte (la clave no se le manda a
quien califica).

| # | Qué | Quién | Hoja | Por qué |
|---|---|---|---|---|
| A1 | Validar mis reglas automáticas en 100 primeras respuestas (¿nombra el código de otro estado?, ¿cita la ley o el artículo aceptado?, ¿pregunta el lugar?) | Karen, a ciegas | `revision_metricas_100_respuestas_Karen.xlsx` | La métrica de otro estado sostiene el resultado principal (53 % → 4 %) y nunca se comparó con una persona |
| A2 | Revisar las 7 respuestas correctas del cuestionario | Un abogado que no escribió el cuestionario | `revision_claves_independiente.xlsx` | Las claves las escribió una sola persona del equipo |
| A3 | Calificar a ciegas las 180 primeras respuestas de la ronda 2 (o una muestra de 60) | Segundo abogado | Por preparar: sin códigos de participante, sin prompt, sin la evaluación de IA ni el dictamen de Karen, en orden aleatorio | La auditoría de Karen la hizo una sola coautora, sin ocultar el prompt y partiendo de una evaluación preliminar de IA; el revisor pide acuerdo entre evaluadores |
| A4 | Resolver los 6 casos donde el dictamen no coincide con las casillas, y calificar las 16 respuestas que faltan | Karen | Su hoja «INCIDENCIAS» | Pendientes de su propia auditoría |
| A5 | Nombrar la herramienta de IA de la evaluación preliminar y las versiones de ChatGPT y Codex | Karen, Francisco | — | Declaración de uso de IA |

## B. Ronda 3: experimentos con usuarios

**B1. Separar qué rasgo del prompt sube la confianza (diseño factorial).**
- **Qué:** variar por separado el registro (jurídico o cotidiano), la estructura (párrafos o encabezados y listas) y el contenido de acción (con o sin pasos concretos y sin o con decir si los hechos pueden ser delito).
- **Por qué:** el prompt intermedio subió la disposición a actuar de 39 % a 82 % y la confianza +0.76, sin mejorar el cuestionario. Los prompts cambian muchos rasgos a la vez; solo el contenido de acción redujo algo el efecto al ajustar (de +43 a +33 puntos).
- **Fuente:** `paper_2026-11-03/que_hace_cada_prompt.md`.

**B2. Dónde y cómo pedir el lugar de los hechos.**
- **Qué:** asignar al azar: (A) como ahora, la pregunta dentro de la respuesta; (B) la misma respuesta con la pregunta al final, en negritas y diciendo por qué importa; (C) un primer turno corto que solo pide el lugar y luego responde. Medir cuántos dan el lugar, el recall@10 y el cuestionario que siguen.
- **Por qué:** cuando el primer mensaje no nombra el estado, el recall@10 es 16 % (contra 61 %). El asistente pidió el lugar en 81 % de esos casos, pero solo 40 % lo dio, y la mitad ni siquiera volvió a escribir. Una pregunta al final y aparte se contestó cerca del doble de veces que una enterrada a media respuesta, sin diferencia clara.
- **Fuente:** `paper_2026-11-03/pregunta_enterrada.json`, `como_preguntan.json`; borrador v3, sección 8.

**B3. Preguntar por qué no actuarían.**
- **Qué:** después de «¿actuarías?», preguntar el motivo, con opciones que incluyan «citó la ley de otro estado».
- **Por qué:** las personas con formación jurídica actuarían menos cuando hubo error de estado (23 % contra 61 %), pero ninguna mencionó el estado en sus comentarios. No sabemos si notaron el error o solo dudaron.
- **Fuente:** `paper_2026-11-03/resultados_ronda1.md`.

**B4. Un cuestionario que sí mida lo que dijo el asistente.**
- **Qué:** más preguntas que dependan de la respuesta (no del texto de la situación), una medición antes de usar el asistente, y la clave fijada en la definición del estudio antes de empezar.
- **Por qué:** solo 3 de las 6 preguntas dependen de la ley; las otras se contestan con sentido común. La clave de «Las fotos» se amplió a mitad del estudio y no quedó en la definición de la ronda 2.

**B5. Medir la confianza calibrada, no solo la confianza.**
- **Qué:** comparar la confianza y la disposición a actuar en respuestas correctas contra incorrectas (según una calificación jurídica independiente), y probar intervenciones que hagan visibles los límites (por ejemplo, decir qué hecho falta y por qué cambia la respuesta).
- **Por qué:** en las 24 respuestas que Karen calificó como incorrectas, las personas actuarían en 15 y no reportaron problema en 17.

**B6. Tamaño de muestra y diseño.**
- Para detectar 15 puntos en el cuestionario: unas 49 personas por prompt; para 10 puntos, 111; para mostrar equivalencia de ±10, 121 (`paper_2026-11-03/resultados_ronda2.json`, `tamano_de_muestra`).
- Asignación aleatoria estratificada por formación jurídica desde el inicio, con todas las condiciones disponibles desde el primer día, y prerregistro.

## C. Sistema

**C1. El filtro por estado.**
- **Heredar el lugar en mensajes de seguimiento:** 2 continuaciones no heredaron el estado dicho antes.
- **«Estoy en / vivo en Querétaro» en extorsión en línea:** en 5 mensajes de «Las fotos», Karen los marcó como lugar de los hechos y el filtro no; con el 167 Quinquies como respuesta aceptada, eso deja fuera una respuesta correcta.
- **Delitos federales:** el filtro detectó solo 6 de 10.
- **Guardar la decisión del filtro en cada mensaje:** hoy se reconstruye a partir de lo que recuperó el buscador.
- **Fuente:** `paper_2026-11-03/evaluacion_filtro_estado.md` (tabla G4, codificación de Karen).

**C2. Un conjunto de prueba independiente para el filtro.**
- **Qué:** casos escritos por un abogado que no vio el prompt del filtro, con hechos en varios estados, delitos a distancia, competencia federal concurrente y delitos federales.
- **Por qué:** los 263 casos actuales los escribimos nosotros y los usamos para desarrollar el filtro.

**C3. Aplicabilidad más allá del lugar.**
- **Qué:** que el sistema pregunte o identifique hechos de los que depende la ley: sexo, edad y relación entre las partes. Primer paso ya hecho: la página para que los expertos etiqueten a quién aplica cada ley.
- **Por qué:** 22 de las 24 respuestas incorrectas en la auditoría de Karen son «aplicación normativa sin verificar su aplicabilidad», casi ninguna por el estado. Además, apagar la Ley General de Acceso de las Mujeres arregló «Las fotos» pero esconde esa ley a las mujeres a quienes protege.

**C4. Recuperación.**
- **Qué:** mejorar el recall del artículo esperado con lenguaje cotidiano (por ejemplo, el buscador prefiere el 167 Quáter al 167 Quinquies porque usa las palabras de la gente).
- **Por qué:** aun con el reranker, el artículo esperado entra a los 10 primeros en cerca de un tercio de los primeros mensajes.

**C5. Corpus nacional.**
- **Qué:** agregar más de los 32 códigos estatales y medir si cambia el error de estado.
- **Por qué:** con 4 estados no sabemos cómo se comporta el error ni el filtro a escala nacional.

**C6. Máquina de estados con expediente de la consulta (diseño decidido el 9 de noviembre).**

Términos:
- **Estado:** uno de una lista finita y fija de situaciones de la conversación; siempre hay exactamente uno, y el siguiente depende solo del estado actual y del evento.
- **Evento:** cada mensaje de la persona o botón que presiona.
- **Expediente de la consulta:** los datos del caso que el programa del asistente (en Python) va anotando. No es un estado; los tres estados lo leen y lo escriben, y las transiciones lo consultan.
- **Dato del expediente:** cada dato que el programa anota en el expediente de la consulta, porque de él depende qué ley aplica (por ejemplo, el lugar de los hechos, la edad de la víctima, si hubo dinero de por medio, si quien manda los mensajes es su superior). Karen los define por tipo de caso en un catálogo, igual que los formularios de trámites.

Estados:

| Estado | Objetivo | Qué hace el asistente |
|---|---|---|
| **LLENAR_EXPEDIENTE** (inicial) | Tener todos los datos del expediente | Pregunta los datos del expediente que faltan, con el texto del catálogo de Karen. **No da leyes ni orientación legal** |
| **ORIENTACIÓN** | Dar la orientación legal que aplica | El buscador recupera solo artículos de las leyes que permite el expediente; el LLM escribe la respuesta; otra llamada al LLM revisa que cada ley citada aplique a los datos del expediente; contesta preguntas de seguimiento |
| **REDACTAR_DOCUMENTO** | Redactar un escrito (denuncia, querella) | Corre la máquina de trámites como submáquina, sin TRIAJE; el expediente llena por adelantado los campos; el documento sale de la plantilla de Karen, sin LLM |

Transiciones:

| De | Evento | A |
|---|---|---|
| LLENAR_EXPEDIENTE | Falta un dato del expediente | LLENAR_EXPEDIENTE |
| LLENAR_EXPEDIENTE | Ya están todos los datos del expediente | ORIENTACIÓN |
| ORIENTACIÓN | Pregunta de seguimiento | ORIENTACIÓN |
| ORIENTACIÓN | Un mensaje cambia o agrega un dato del expediente | LLENAR_EXPEDIENTE |
| ORIENTACIÓN | La persona acepta redactar (botón) | REDACTAR_DOCUMENTO |
| REDACTAR_DOCUMENTO | Se genera el documento o la persona cancela | ORIENTACIÓN |

Decisiones:
- **Si la persona no da un dato del expediente, sigue en LLENAR_EXPEDIENTE.** Es mejor no orientar que orientar con la ley equivocada.
- **El programa en Python decide las transiciones; el LLM no.** El LLM solo extrae datos de los mensajes, escribe la orientación y revisa la aplicabilidad.
- **Las preguntas a la persona salen del catálogo de Karen,** no las redacta el LLM.

Qué resuelve, según los datos: las 7 fallas del filtro en la ronda 2 (2 continuaciones sin el lugar heredado y 5 «estoy en Querétaro»); el 40 % que dio el lugar cuando se le pidió después de la respuesta; los 22 de 24 errores de aplicabilidad de la auditoría de Karen; la ley de mujeres apagada (se filtra por a quién protege); y el filtro que no guardaba su decisión (el expediente se registra en cada mensaje).

Lo que falta: el catálogo de datos del expediente por tipo de caso y las plantillas de los escritos por estado (hoy solo existe la del divorcio unilateral en la CDMX). Se reutilizan `extraer_lugares` de `jurisdiction_gate.py`, el filtro de la búsqueda por jurisdicción y el patrón de `forms/asistente.py`.

**Experimento (ronda 3):** comparar, con asignación aleatoria, el sistema actual contra LLENAR_EXPEDIENTE + ORIENTACIÓN. **Sin REDACTAR_DOCUMENTO**, que agrega otra variable; probarlo después, por separado. Medidas: corrección jurídica calificada a ciegas por un abogado; cuántas personas abandonan antes de recibir orientación (el costo de no orientar sin los datos); recall del artículo esperado; comprensión; y si la confianza corresponde a respuestas correctas.

## D. Lecciones de proceso (para no repetir)

- Fijar la clave de respuesta en la definición del estudio **antes** de recolectar, y comparar contra la versión de prod antes de copiar una definición.
- Respaldar fuera de `/tmp` todo resultado de prod que use el paper, en cuanto termina la corrida.
- Codificación humana a ciegas, con la hoja guardada, para cualquier cifra que el paper atribuya a una persona.
- Validar cada métrica automática contra una persona antes de que sostenga un resultado.
