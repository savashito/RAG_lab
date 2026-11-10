# Borrador: tipos de caso del derecho penal (para que Karen lo revise)

## De dónde sale

Revisé el corpus penal en prod (`sistema_penal__qwen06__legal`, tema `derecho_penal_mexicano`) el 10 de noviembre de 2026:

- El Libro Segundo (los delitos) del Código Penal de la CDMX tiene 27 títulos y unos 120 capítulos; casi cada capítulo es un delito.
- Los códigos de Querétaro, Estado de México, Morelos y el Código Penal Federal tienen los mismos grupos de delitos, con otros nombres y otros números de artículo.
- Leyes especiales: Ley General en materia de Extorsión, Ley General en materia de Secuestro y Ley Federal contra la Delincuencia Organizada.
- Las 9 fuentes apagadas: se revisan en la sección «Fuentes apagadas».

## Problema y propuesta

Si cada delito fuera un tipo de caso, el LLM tendría que elegir entre unos 120. Además, la persona no sabe qué delito es. Por ejemplo, «Las fotos» puede ser extorsión, un delito contra la intimidad sexual (Ley Olimpia), amenazas o pornografía infantil: depende de datos que la persona tal vez no dijo.

Propuesta, en dos niveles:

1. **Tipo de caso:** lo que le pasó a la persona, con palabras de todos los días. Son unos 20. **El LLM clasifica** el mensaje en uno o más tipos de caso de esta lista cerrada.
2. **Delitos posibles:** cada tipo de caso tiene su lista de delitos posibles y los datos decisivos que los distinguen. **El programa en Python** pregunta esos datos (con el texto de Karen) y, con las respuestas, decide qué delitos aplican. El LLM no elige el delito.

Así el LLM elige entre unos 20 tipos de caso, no entre 120 delitos. Y la distinción difícil (extorsión o Ley Olimpia) queda en una regla que Karen escribe y que se puede revisar.

## Datos decisivos

Lista única; cada tipo de caso dice cuáles usa. `lugar_hechos` aplica a todos.

| id | Pregunta (borrador) | Para qué distingue |
|---|---|---|
| `lugar_hechos` | ¿En qué estado pasó? | Qué código penal aplica |
| `papel` | ¿Te pasó a ti, te acusan a ti, o le pasó a otra persona? | Derechos de víctima o de imputado |
| `edad_victima` | ¿Qué edad tiene la víctima? | Menor de 12, de 12 a 17, adulta: cambia el delito y la pena |
| `victima_mujer` | ¿La víctima es mujer? | Feminicidio; Ley General de Acceso de las Mujeres; medidas de protección |
| `relacion_partes` | ¿Qué relación tienen? (pareja o expareja, familiar, trabajo, escuela, ninguna) | Violencia familiar, hostigamiento, agravantes |
| `superior_o_docente` | ¿Esa persona es tu jefe, maestro o supervisa tu trabajo? | Hostigamiento sexual frente a acoso sexual |
| `servidor_publico` | ¿Quien lo hizo es policía o trabaja en el gobierno? | Abuso de autoridad, tortura, cohecho |
| `pide_dinero` | ¿Te pidieron dinero o algo a cambio? | Extorsión frente a amenazas o difusión |
| `ya_difundido` | ¿Ya publicaron o mandaron las imágenes a alguien? | Intimidad sexual consumada o amenaza |
| `violencia_o_arma` | ¿Hubo golpes, amenazas con arma o fuerza? | Robo con violencia, agravantes |
| `medio_digital` | ¿Pasó por internet, redes o teléfono? | Violencia digital; delitos a distancia |
| `intencional` | ¿Fue a propósito o fue un accidente? | Doloso frente a culposo (tránsito, médico) |
| `gravedad_lesion` | ¿La lesión tarda más de 15 días en sanar o pone en riesgo la vida? | Grado de lesiones |
| `monto` | ¿Cuánto dinero o de qué valor? | Pena del robo y del fraude |
| `consentimiento` | ¿La persona estuvo de acuerdo? (tomar las imágenes, el procedimiento médico) | Intimidad sexual, responsabilidad médica |

## Tipos de caso

| # | Tipo de caso (palabras de la persona) | Delitos posibles (nombre en el Código Penal CDMX) | Datos decisivos además del lugar |
|---|---|---|---|
| 1 | Golpes, peleas o lesiones | Lesiones; lesiones con ácido; reglas de riña; disparo de arma | `papel`, `gravedad_lesion`, `violencia_o_arma`, `relacion_partes` |
| 2 | Murió una persona | Homicidio; feminicidio; transfeminicidio; ayuda o inducción al suicidio | `intencional`, `victima_mujer`, `relacion_partes` |
| 3 | Violencia en la familia o la pareja | Violencia familiar; violencia vicaria; incumplimiento de la obligación alimentaria | `relacion_partes`, `edad_victima`, `victima_mujer` |
| 4 | Agresión sexual | Violación; abuso sexual; estupro; incesto; delitos contra menores de 12 años | `edad_victima`, `relacion_partes`, `consentimiento` |
| 5 | Acoso u hostigamiento sexual | Acoso sexual; hostigamiento sexual | `superior_o_docente`, `medio_digital`, `victima_mujer` |
| 6 | Fotos, videos o mensajes íntimos | Contra la intimidad sexual (Ley Olimpia); extorsión; amenazas; pornografía de personas menores de edad; corrupción de menores | `pide_dinero`, `ya_difundido`, `edad_victima`, `consentimiento`, `victima_mujer` |
| 7 | Amenazas, extorsión o cobros | Amenazas; extorsión (código y Ley General en materia de Extorsión); cobranza ilegítima | `pide_dinero`, `medio_digital`, `violencia_o_arma` |
| 8 | Se llevaron a una persona | Privación de la libertad; secuestro (Ley General en materia de Secuestro); sustracción o retención de menores; tráfico de menores | `pide_dinero`, `relacion_partes`, `edad_victima` |
| 9 | Me robaron | Robo (y sus agravantes); abuso de confianza; encubrimiento por receptación | `violencia_o_arma`, `monto`, `relacion_partes` |
| 10 | Me estafaron o usaron mis datos | Fraude; administración fraudulenta; insolvencia fraudulenta; usurpación de identidad; falsificación de documentos | `monto`, `medio_digital` |
| 11 | Mi casa, terreno o propiedad | Despojo; daño a la propiedad; allanamiento de morada | `violencia_o_arma`, `intencional` |
| 12 | Accidente o choque de tránsito | Lesiones u homicidio culposo; daño culposo; delitos contra la seguridad del tránsito | `intencional`, `gravedad_lesion`, `papel` |
| 13 | Me difamaron o revelaron algo privado | Difamación; calumnia; violación de la intimidad personal; revelación de secretos; violación de correspondencia o comunicación privada | `medio_digital`, `servidor_publico` |
| 14 | Abuso de la policía o de una autoridad | Abuso de autoridad; uso ilegal de la fuerza pública; tortura; intimidación; cohecho; concusión; negación del servicio público | `servidor_publico` |
| 15 | Discriminación | Discriminación | `servidor_publico` |
| 16 | Atención médica o de salud | Responsabilidad profesional; abandono o práctica indebida del servicio médico; aborto; esterilización forzada; peligro de contagio; sustancias modelantes; administración subrepticia de sustancias | `consentimiento`, `intencional`, `victima_mujer` |
| 17 | Niñas, niños o personas vulnerables | Corrupción de menores; trata de personas; lenocinio; explotación laboral de menores; omisión de cuidado | `edad_victima`, `relacion_partes` |
| 18 | Me acusan, me citaron o me detuvieron | (procedimiento: Código Nacional de Procedimientos Penales) más el delito del que se acusa, que se clasifica con los tipos 1–17 | `papel` |
| 19 | Animales o medio ambiente | Maltrato o crueldad contra animales; delitos contra el ambiente | `intencional` |
| 20 | Armas, pandillas o crimen organizado | Portación de objetos para agredir; pandilla; asociación delictuosa; delincuencia organizada (ley federal); operaciones con recursos de procedencia ilícita | `violencia_o_arma` |
| — | `otro` | Lo que no encaja; solo pide el lugar | — |

Quedan fuera, por ser muy poco probables en una consulta de una persona: delitos electorales, rebelión, sabotaje, motín, delitos en la administración de justicia cometidos por jueces, inhumación y exhumación, bigamia y estado civil, manipulación genética. Si aparecen, van a `otro`.

Un mensaje puede tener más de un tipo de caso (por ejemplo, 6 y 7: fotos y amenazas). El expediente de la consulta ya guarda `tipos_caso` como lista.

## Ejemplo: tipo 6, «Fotos, videos o mensajes íntimos»

El LLM clasifica el mensaje como tipo 6. El programa en Python pregunta los datos que faltan y aplica reglas como estas (las escribe Karen; aquí solo es la forma):

| Si | Delito posible |
|---|---|
| `edad_victima` < 18 | Pornografía de personas menores de edad; corrupción de menores (además de lo que siga) |
| `pide_dinero` = sí | Extorsión |
| `pide_dinero` = no, y amenaza con publicarlas | Amenazas |
| `ya_difundido` = sí, o se tomaron sin `consentimiento` | Contra la intimidad sexual (Ley Olimpia) |
| `victima_mujer` = sí | Además: Ley General de Acceso de las Mujeres (violencia digital, medidas de protección) |

«Las fotos» del estudio (Cris, 24 años, le piden 5,000 pesos, todavía no las publican) daría: extorsión, y además Ley General de Acceso de las Mujeres solo si Cris es mujer. Con `pide_dinero` y `ya_difundido`, el sistema distingue extorsión de Ley Olimpia sin que el LLM lo adivine.

## Fuentes apagadas

| Fuente apagada | ¿Da un tipo de caso? | Propuesta |
|---|---|---|
| Ley General de Acceso de las Mujeres a una Vida Libre de Violencias | No es un delito; define modalidades (familiar, laboral y docente, comunidad, institucional, política, digital y mediática, feminicida) y medidas de protección | Prenderla solo cuando `victima_mujer` = sí, en los tipos 1–7 y 16 |
| Violencia Digital (micrositio) | No; explica la violencia digital y la Ley Olimpia | Igual que la anterior, en los tipos 5 y 6 |
| LEY OLIMPIA ficha técnica | No; tabla de artículos y penas por estado | Igual, en el tipo 6. Sirve para que Karen encuentre el artículo de cada estado |
| LGEEPA, Manual de Derecho Ambiental, Nexos energético-ambiental, Temas selectos de derecho ambiental | Sí: tipo 19 (la parte ambiental) | Prenderlas solo en el tipo 19 |
| Tesis: herramientas legales para psicólogas en violencia contra las mujeres | No; guía para profesionales | Dejarla apagada |
| V-19-2025 (acuerdo del Consejo de la Judicatura de la CDMX) | No; fechas de juicios civiles y familiares, no penales | Dejarla apagada |

Esto cambia la razón de apagar: hoy están apagadas para todos; con el expediente de la consulta, se prenden solo cuando los datos de la persona dicen que aplican.

## Lo que falta (Karen)

1. Confirmar o cambiar la lista de tipos de caso y sus nombres.
2. Confirmar los datos decisivos de cada tipo y redactar cada pregunta.
3. Escribir las reglas de cada tipo (datos → delitos posibles), con el artículo de cada uno de los 4 códigos estatales y el federal.
4. Decidir qué hacer con lo que hoy queda en `otro`.
