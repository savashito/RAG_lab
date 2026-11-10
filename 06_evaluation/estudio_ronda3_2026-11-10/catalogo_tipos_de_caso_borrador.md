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

1. **Tipo de caso:** lo que le pasó a la persona, con palabras de todos los días. Son 25. **El LLM clasifica** el mensaje en uno o más tipos de caso de esta lista cerrada.
2. **Delitos posibles:** cada tipo de caso tiene su lista de delitos posibles y los datos del expediente que los distinguen. **El programa en Python** pregunta esos datos (con el texto de Karen) y, con las respuestas, decide qué delitos aplican. El LLM no elige el delito.

Así el LLM elige entre 25 tipos de caso, no entre 120 delitos. Y la distinción difícil (extorsión o Ley Olimpia) queda en una regla que Karen escribe y que se puede revisar.

## Datos del expediente

Lista única; cada tipo de caso dice cuáles usa. `lugar_hechos` aplica a todos.

| id | Pregunta (borrador) | Para qué distingue |
|---|---|---|
| `lugar_hechos` | ¿En qué estado pasó? | Qué código penal aplica (solo en delitos del fuero común; ver `federal`) |
| `papel` | ¿Te pasó a ti, te acusan a ti, o le pasó a otra persona? | Derechos de víctima o de imputado |
| `edad_victima` | ¿Qué edad tiene la víctima? | Menor de edad o adulta; los umbrales (por ejemplo, 12 años en la CDMX) cambian por estado |
| `victima_mujer` | ¿La víctima es mujer (incluida mujer trans)? | Feminicidio y transfeminicidio; Ley General de Acceso de las Mujeres. **No** cambia los delitos que protegen a cualquier persona (violencia familiar, acoso, Ley Olimpia), ni las medidas de protección del CNPP, que son para cualquier víctima |
| `relacion_partes` | ¿Qué relación tienen? (pareja o expareja, familiar, trabajo, escuela, ninguna) | Violencia familiar, hostigamiento, agravantes |
| `superior_o_docente` | ¿Esa persona es tu jefe, maestro o supervisa tu trabajo? | Hostigamiento sexual frente a acoso sexual |
| `servidor_publico` | ¿Quien lo hizo es policía o trabaja en el gobierno? | Abuso de autoridad, tortura, cohecho |
| `pide_dinero` | ¿Te pidieron dinero o algo a cambio? | Extorsión frente a amenazas o difusión |
| `ya_difundido` | ¿Ya publicaron o mandaron las imágenes a alguien? | Intimidad sexual consumada o amenaza |
| `violencia_o_arma` | ¿Hubo golpes, amenazas con arma o fuerza? | Robo con violencia, agravantes |
| `medio_digital` | ¿Pasó por internet, redes o teléfono? | Violencia digital; delitos a distancia |
| `intencional` | ¿Fue a propósito o fue un accidente? | Doloso frente a culposo (tránsito, médico) |
| `gravedad_lesion` | ¿Cuánto tarda en sanar la lesión? ¿Puso en riesgo la vida? | Grado de lesiones; los plazos (15 y 60 días en la CDMX) cambian por estado |
| `monto` | ¿Cuánto dinero o de qué valor? | Pena del robo y del fraude |
| `consentimiento` | ¿La persona estuvo de acuerdo? (tomar las imágenes, el procedimiento médico) | Intimidad sexual (en algunos estados), responsabilidad médica |
| `federal` | (no se pregunta; lo decide el tipo de caso o el delito) | Drogas, armas de fuego, delincuencia organizada y otros delitos federales: aplica el Código Penal Federal o la ley federal sin importar el estado |

## Tipos de caso

| # | Tipo de caso (palabras de la persona) | Delitos posibles (nombre en el Código Penal CDMX) | Datos del expediente además del lugar |
|---|---|---|---|
| 1 | Golpes, peleas o lesiones | Lesiones; lesiones con ácido; reglas de riña; disparo de arma | `papel`, `gravedad_lesion`, `violencia_o_arma`, `relacion_partes` |
| 2 | Murió una persona | Homicidio; feminicidio; transfeminicidio; ayuda o inducción al suicidio | `intencional`, `victima_mujer`, `relacion_partes` |
| 3 | Violencia en la familia o la pareja | Violencia familiar; violencia vicaria; incumplimiento de la obligación alimentaria | `relacion_partes`, `edad_victima` (`victima_mujer` solo agrega la Ley de Acceso de las Mujeres) |
| 4 | Agresión sexual | Violación; abuso sexual; estupro; incesto; delitos contra menores de 12 años; privación de la libertad con fines sexuales | `edad_victima`, `relacion_partes`, `consentimiento` |
| 5 | Acoso u hostigamiento sexual | Acoso sexual; hostigamiento sexual | `superior_o_docente`, `medio_digital` (`victima_mujer` solo agrega la Ley de Acceso de las Mujeres) |
| 6 | Fotos, videos o mensajes íntimos | Contra la intimidad sexual (Ley Olimpia); extorsión; amenazas; pornografía de personas menores de edad; corrupción de menores; federal: delitos contra la indemnidad de privacidad de la información sexual (CPF, título séptimo bis) | `pide_dinero`, `ya_difundido`, `edad_victima`, `consentimiento`, `victima_mujer` |
| 7 | Amenazas, extorsión o cobros | Amenazas; extorsión (Ley General en materia de Extorsión; en la CDMX el art. 236 está derogado desde el 12-dic-2024 y queda el 148 Quáter; revisar cada estado); cobranza ilegítima | `pide_dinero`, `medio_digital`, `violencia_o_arma` |
| 8 | Se llevaron a una persona o no aparece | Privación de la libertad; secuestro (Ley General en materia de Secuestro); desaparición de personas (ley general, **no está en el corpus**); sustracción o retención de menores; tráfico de menores; desaparición forzada por un servidor público (CDMX, art. 168) | `pide_dinero`, `relacion_partes`, `edad_victima` |
| 9 | Me robaron | Robo (y sus agravantes); abuso de confianza; encubrimiento por receptación | `violencia_o_arma`, `monto`, `relacion_partes` |
| 10 | Me estafaron o usaron mis datos | Fraude; administración fraudulenta; insolvencia fraudulenta; usurpación de identidad; falsificación de documentos; falsificación de sellos, llaves o contraseñas; falsificación de tarjetas o títulos de crédito; acceso ilícito a sistemas o equipos de informática (CPF, título noveno; Querétaro, título séptimo) | `monto`, `medio_digital` |
| 11 | Mi casa, terreno o propiedad | Despojo; daño a la propiedad; allanamiento de morada; responsabilidad de directores responsables de obra (construcción) | `violencia_o_arma`, `intencional` |
| 12 | Accidente o choque de tránsito | Lesiones u homicidio culposo; daño culposo; delitos contra la seguridad del tránsito; ataques a las vías de comunicación y a los medios de transporte | `intencional`, `gravedad_lesion`, `papel` |
| 13 | Me difamaron o revelaron algo privado | Violación de la intimidad personal; revelación de secretos; violación de correspondencia o comunicación privada. Difamación y calumnia: **derogadas en la CDMX** (arts. 214–218); revisar cada estado; en la CDMX la vía es civil | `medio_digital`, `servidor_publico` |
| 14 | Abuso de la policía o de una autoridad | Abuso de autoridad; uso ilegal de la fuerza pública; tortura (ley general, **no está en el corpus**; el código de la CDMX tiene los arts. 206 Bis y siguientes); intimidación; cohecho; concusión; negación del servicio público | `servidor_publico` |
| 15 | Discriminación | Discriminación; delitos contra el libre desarrollo de la personalidad y la identidad sexual (terapias de conversión) | `servidor_publico` |
| 16 | Atención médica o de salud | Responsabilidad profesional; abandono o práctica indebida del servicio médico; aborto; esterilización forzada; peligro de contagio; sustancias modelantes; administración subrepticia de sustancias; suministro de medicinas nocivas o inapropiadas; usurpación de profesión | `consentimiento`, `intencional`, `victima_mujer` |
| 17 | Niñas, niños o personas vulnerables | Corrupción de menores; trata de personas (ley general, **no está en el corpus**; el código de la CDMX tiene el art. 188 Bis); lenocinio; explotación laboral de menores; omisión de cuidado; turismo sexual; omisión de auxilio | `edad_victima`, `relacion_partes` |
| 18 | Me acusan, me citaron o me detuvieron | (procedimiento: Código Nacional de Procedimientos Penales) más el delito del que se acusa, que se clasifica con los tipos 1–17 | `papel` |
| 19 | Animales o medio ambiente | Maltrato o crueldad contra animales; delitos contra el ambiente; delitos contra la gestión ambiental | `intencional` |
| 20 | Armas, pandillas o crimen organizado | Portación de objetos para agredir; armas de fuego (Ley Federal de Armas de Fuego, **no está en el corpus**; federal); pandilla; asociación delictuosa; delincuencia organizada (ley federal); operaciones con recursos de procedencia ilícita | `violencia_o_arma` |
| 21 | Drogas | Delitos contra la salud (Código Penal Federal, título séptimo; narcomenudeo: Ley General de Salud, **no está en el corpus**) | `federal` |
| 22 | Corrupción en el gobierno (la persona la denuncia) | Peculado; enriquecimiento ilícito; tráfico de influencia; ejercicio abusivo de funciones; ejercicio ilegal y abandono del servicio público; coalición de servidores públicos; usurpación de funciones públicas; remuneración ilícita; corrupción inmobiliaria; distracción de recursos públicos | `servidor_publico` |
| 23 | Problemas con una autoridad por algo que hizo la persona | Desobediencia y resistencia de particulares; ultrajes a la autoridad; quebrantamiento de sellos; oposición a una obra pública; ejercicio ilegal del propio derecho (hacerse justicia por su mano); uso indebido de insignias y uniformes; uso indebido de las llamadas de emergencia; cohecho cometido por particulares (ofrecer «mordida») | `papel` |
| 24 | Problemas con la Fiscalía, un juzgado o un abogado | Denegación o retardo de justicia; delitos en la procuración de justicia; delitos en la administración de justicia; omisión de informes médico forenses; delitos en la ejecución penal; evasión de presos; fraude procesal; falsedad ante autoridades (falso testimonio); simulación de pruebas; variación del nombre o domicilio; delitos de abogados, patronos y asesores jurídicos; encubrimiento por favorecimiento | `papel`, `servidor_publico` |
| 25 | Piratería o derechos de autor | Delitos en materia de derechos de autor (CPF, título vigésimo sexto; federal) | `federal` |
| — | `otro` | Lo que no encaja en 1–25, incluidos los delitos poco probables de la lista de abajo; solo pide el lugar | — |

Van a `otro` (muy poco probables en una consulta de una persona), con su artículo en la CDMX:

- Delitos electorales (arts. 351–360).
- Rebelión (361); ataques con sustancias tóxicas, incendio o explosivos contra las instituciones (362); sabotaje (363); motín (364).
- Manipulación genética (154–155).
- Inhumación, exhumación y respeto a los cadáveres (207–208).
- Estado civil y bigamia (203–205).
- Solo federales (CPF): delitos contra la seguridad de la Nación (traición, espionaje, terrorismo), contra el derecho internacional, contra la humanidad (genocidio), falsificación de moneda.

No son delitos y no van en ningún tipo de caso: las reglas comunes y disposiciones comunes de cada título (por ejemplo, arts. 136–140, 182, 191–192, 219, 246–249, 256–258, 289, 348–350 de la CDMX) y los transitorios. El programa las usa al aplicar el delito, no al clasificar.

Comparé los delitos contra los capítulos del código de la CDMX y los títulos del Código Penal Federal. Los códigos de Querétaro, Estado de México y Morelos los comparé solo por título; Karen debe revisar si tienen delitos que no estén en la CDMX (por ejemplo, Querétaro: «delitos contra la seguridad y el orden en el desarrollo urbano»; Estado de México: «delitos contra la libertad de expresión»).

Un mensaje puede tener más de un tipo de caso (por ejemplo, 6 y 7: fotos y amenazas). El expediente de la consulta ya guarda `tipos_caso` como lista.

## Ejemplo: tipo 6, «Fotos, videos o mensajes íntimos»

El LLM clasifica el mensaje como tipo 6. El programa en Python pregunta los datos que faltan y aplica reglas como estas (las escribe Karen; aquí solo es la forma):

| Si | Delito posible |
|---|---|
| `edad_victima` < 18 | Pornografía de personas menores de edad; corrupción de menores (además de lo que siga) |
| `pide_dinero` = sí | Extorsión |
| `pide_dinero` = no, y amenaza con publicarlas | Amenazas |
| Querétaro: divulga **o amenaza con difundir**, con o sin consentimiento al obtenerlas | Art. 167 Quinquies (en el capítulo de acoso y hostigamiento sexual; aplica a víctimas de cualquier sexo) |
| CDMX: las tomó sin `consentimiento`, o las difunde sin consentimiento | Art. 181 Quintus, contra la intimidad sexual (aplica a víctimas de cualquier sexo). Karen: ¿la amenaza sola entra aquí o solo en amenazas o extorsión? |
| `victima_mujer` = sí | Además: Ley General de Acceso de las Mujeres (violencia digital, medidas de protección) |

«Las fotos» del estudio (Cris, 24 años, en Querétaro, le piden 5,000 pesos, todavía no las publican) daría: extorsión y el 167 Quinquies (la amenaza de difundir basta), y además la Ley General de Acceso de las Mujeres solo si Cris es mujer. Las reglas cambian por estado: por eso cada regla debe citar el artículo de cada código.

## Fuentes apagadas

| Fuente apagada | ¿Da un tipo de caso? | Propuesta |
|---|---|---|
| Ley General de Acceso de las Mujeres a una Vida Libre de Violencias | No es un delito; define modalidades (familiar, laboral y docente, comunidad, institucional, política, digital y mediática, feminicida) y medidas de protección | Prenderla solo cuando `victima_mujer` = sí, en los tipos 1–7 y 16 |
| Violencia Digital (micrositio) | No; explica las reformas de la Ley Olimpia al Código Penal Federal y a la Ley General de Acceso de las Mujeres | Prenderla en los tipos 5 y 6 para cualquier persona: los delitos contra la intimidad sexual protegen a cualquier persona, no solo a mujeres |
| LEY OLIMPIA ficha técnica | No; tabla de artículos y penas por estado | Prenderla en el tipo 6 para cualquier persona. Sirve también para que Karen encuentre el artículo de cada estado |
| LGEEPA, Manual de Derecho Ambiental, Nexos energético-ambiental, Temas selectos de derecho ambiental | Sí: tipo 19 (la parte ambiental) | Prenderlas solo en el tipo 19 |
| Tesis: herramientas legales para psicólogas en violencia contra las mujeres | No; guía para profesionales | Dejarla apagada |
| V-19-2025 (acuerdo del Consejo de la Judicatura de la CDMX) | No; fechas de juicios civiles y familiares, no penales | Dejarla apagada |

Esto cambia la razón de apagar: hoy están apagadas para todos; con el expediente de la consulta, se prenden solo cuando los datos de la persona dicen que aplican.

## Lo que falta (Karen)

0. Cada regla de este borrador la escribí sin leer todos los artículos; ya corregí los errores que encontré al leerlos (Querétaro 167 Quinquies, difamación y extorsión derogadas en la CDMX, `victima_mujer`). Cada regla debe citar el artículo de cada código antes de usarse.
1. Confirmar o cambiar la lista de tipos de caso y sus nombres.
2. Confirmar los datos del expediente de cada tipo y redactar cada pregunta.
3. Escribir las reglas de cada tipo (datos → delitos posibles), con el artículo de cada uno de los 4 códigos estatales y el federal.
4. Decidir qué hacer con lo que hoy queda en `otro`.
