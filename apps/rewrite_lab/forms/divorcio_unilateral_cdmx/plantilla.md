<!--
Plantilla: SOLICITUD DE DIVORCIO UNILATERAL (incausado) — Ciudad de México.
Sintaxis (la llena el código, no el LLM; ver forms/README.md):
  {campo}                      → valor que dio la persona
  [SI campo] … [/SI]           → bloque que solo aparece si el campo es verdadero / no vacío
  [SI NO campo] … [/SI]        → bloque que solo aparece si el campo es falso / vacío
  [SI campo = valor] … [/SI]   → bloque que solo aparece si el campo tiene ese valor
  [CADA x EN lista] … [/CADA]  → se repite por cada elemento ({x.nombre}, {x.fecha_nacimiento}, {x.numero})
  {#serie} / {#R serie} / {#A serie} → numeración automática 1, 2, 3… / I, II, III… / A, B, C… (no brinca si se omite un bloque)
Los comentarios «REVISAR (Karen)» marcan lo que necesita confirmación jurídica antes de publicar.
-->

**C. JUEZA O JUEZ DE LO FAMILIAR EN TURNO DEL TRIBUNAL SUPERIOR DE JUSTICIA DE LA CIUDAD DE MÉXICO**
**P R E S E N T E**

**{nombre_solicitante}**, por mi propio derecho, señalando como domicilio para oír y recibir notificaciones el ubicado en {domicilio_notificaciones}; número telefónico {telefono} y correo electrónico {correo} para los mismos efectos procesales; [SI grupo_vulnerable]manifestando que pertenezco a un grupo en situación de vulnerabilidad: {grupo_vulnerable}; [/SI]y designando como persona representante autorizada a {representante_autorizado}, ante Usted, con el debido respeto, comparezco y expongo:

Que por medio del presente escrito, por mi propio derecho y en la vía oral familiar, vengo a solicitar el **DIVORCIO** de **{nombre_conyuge}**, quien puede ser emplazada o emplazado en el domicilio ubicado en {domicilio_conyuge}, de conformidad con las siguientes:

## PRETENSIONES

**{#A pretensiones}).** La disolución del vínculo matrimonial que me une con {nombre_conyuge}.

**{#A pretensiones}).** La aprobación de la propuesta de convenio que se acompaña al presente escrito para regular las consecuencias inherentes a la disolución del vínculo matrimonial y, en su defecto, que se resuelva sobre ellas conforme a derecho.

[SI hay_hijos_menores]**{#A pretensiones}).** Que se fije lo relativo a la guarda y custodia, el régimen de convivencias y los alimentos de nuestras hijas e hijos menores de edad, en los términos de la propuesta de convenio.

[/SI]Fundo mi solicitud en los siguientes hechos y consideraciones de derecho:

## HECHOS

**1.** Con fecha {fecha_matrimonio} contraje matrimonio civil con {nombre_conyuge}[SI lugar_matrimonio], ante {lugar_matrimonio}[/SI], bajo el régimen de [SI regimen = sociedad_conyugal]**sociedad conyugal**[/SI][SI regimen = separacion_bienes]**separación de bienes**[/SI], como lo acredito con la copia certificada del acta de matrimonio[SI numero_acta_matrimonio] número {numero_acta_matrimonio}[/SI], que anexo al presente.

**2.** Establecimos nuestro último domicilio conyugal en {ultimo_domicilio_conyugal}.

[SI hay_hijos_menores]**3.** De nuestro matrimonio procreamos a:
[CADA hijo EN hijos]
- {hijo.nombre}, nacida o nacido el {hijo.fecha_nacimiento};
[/CADA]
como lo acredito con las copias certificadas de sus actas de nacimiento, que anexo al presente.
[/SI][SI NO hay_hijos_menores]**3.** De nuestro matrimonio no procreamos ni adoptamos hijas o hijos menores de edad[SI hijos_mayores_con_apoyo], salvo lo que se precisa en la propuesta de convenio respecto de hijas o hijos mayores de edad que requieren algún apoyo o salvaguardia[/SI].
[/SI]

**4.** [SI regimen = sociedad_conyugal]Durante el matrimonio adquirimos los bienes que se relacionan en el inventario de la propuesta de convenio, por lo que es procedente liquidar la sociedad conyugal.[/SI][SI regimen = separacion_bienes]Al haber celebrado el matrimonio bajo el régimen de separación de bienes, no existe sociedad conyugal que liquidar[SI pide_compensacion]; no obstante, solicito la compensación prevista en la fracción VI del artículo 267 del Código Civil, en los términos de la propuesta de convenio[/SI].[/SI]

**5.** Es mi voluntad no continuar con el matrimonio, por lo que solicito su disolución sin que sea necesario señalar la causa por la que la solicito, en términos del artículo 266 del Código Civil para el Distrito Federal, aplicable en la Ciudad de México.

[SI hay_violencia]**6.** Manifiesto que existen hechos de violencia familiar, por lo que solicito que se dicten de inmediato las medidas de protección que la persona juzgadora estime pertinentes, conforme a la fracción I del apartado A del artículo 282 del Código Civil.
[/SI]

## PROPUESTA DE CONVENIO

En términos del artículo 267 del Código Civil, propongo regular las consecuencias de la disolución del vínculo matrimonial conforme a las siguientes:

### CLÁUSULAS

[SI hay_hijos_menores]**PRIMERA. Guarda y custodia.** La guarda y custodia de nuestras hijas e hijos menores de edad quedará a cargo de {guarda_custodia}, quien la ejercerá en el domicilio ubicado en {domicilio_custodia}.

**SEGUNDA. Convivencias.** El progenitor que no detente la guarda y custodia convivirá con nuestras hijas e hijos conforme al siguiente régimen, respetando sus horarios de comida, descanso y estudio: {regimen_convivencias}.

**TERCERA. Alimentos.** Por concepto de pensión alimenticia a favor de nuestras hijas e hijos, {deudor_alimentario} aportará {monto_alimentos}, que se pagará {forma_pago_alimentos}. Para garantizar su cumplimiento se propone: {garantia_alimentos}.

[/SI][SI alimentos_conyuge]**CLÁUSULA DE ALIMENTOS ENTRE CÓNYUGES.** Solicito que se fije una pensión alimenticia a mi favor por {monto_alimentos_conyuge}, toda vez que {motivo_alimentos_conyuge}, en términos del artículo 288 del Código Civil.

[/SI]**DOMICILIO Y MENAJE.** El uso y disfrute del domicilio conyugal y del menaje corresponderá a {uso_domicilio_conyugal}[SI fecha_desocupacion]; el otro cónyuge deberá desocuparlo a más tardar el {fecha_desocupacion}[/SI].

[SI regimen = sociedad_conyugal]**SOCIEDAD CONYUGAL.** Durante el procedimiento y hasta su liquidación, los bienes de la sociedad conyugal serán administrados por {administrador_bienes}. Se exhiben las capitulaciones matrimoniales, si las hubiere, y el siguiente inventario:
[CADA bien EN bienes]
- {bien.descripcion}[SI bien.valor], con un valor aproximado de {bien.valor}[/SI];
[/CADA]
Propongo liquidar la sociedad conyugal de la siguiente forma: {propuesta_liquidacion}.

[/SI][SI regimen = separacion_bienes]**COMPENSACIÓN.** [SI pide_compensacion]Solicito una compensación equivalente al {porcentaje_compensacion} del valor de los bienes adquiridos durante el matrimonio por {nombre_conyuge}, toda vez que {motivo_compensacion}, en términos de la fracción VI del artículo 267 del Código Civil.[/SI][SI NO pide_compensacion]Ninguno de los cónyuges solicita la compensación prevista en la fracción VI del artículo 267 del Código Civil.[/SI]

[/SI][SI hay_animales_compania]**ANIMALES DE COMPAÑÍA.** El cuidado de los animales de compañía quedará a cargo de {responsable_animales}, conforme al siguiente plan de cuidados: {plan_cuidados_animales}.

[/SI]## MEDIDAS PROVISIONALES

Con fundamento en el artículo 282 del Código Civil, solicito que, desde la admisión de esta solicitud, se decreten las siguientes medidas provisionales:

**{#R medidas}.** La separación de los cónyuges.
[SI hay_hijos_menores]
**{#R medidas}.** Que provisionalmente la guarda y custodia de nuestras hijas e hijos quede a cargo de {guarda_custodia} y se fijen alimentos provisionales a su favor.
[/SI][SI regimen = sociedad_conyugal]
**{#R medidas}.** Que se tomen las medidas necesarias para que ninguno de los cónyuges cause perjuicio en los bienes de la sociedad conyugal y, en su caso, la anotación preventiva de la demanda en el Registro Público de la Propiedad.
[/SI][SI hay_violencia]
**{#R medidas}.** Las medidas de protección que se estimen necesarias por los hechos de violencia familiar manifestados.
[/SI]

## DERECHO

En cuanto al fondo, son aplicables los artículos 266, 267, 282, 283, 287 y 288 del Código Civil para el Distrito Federal, aplicable en la Ciudad de México.

En cuanto al procedimiento, son aplicables los artículos 235, 663, 664, 665 y 677 del Código Nacional de Procedimientos Civiles y Familiares, vigente en materia familiar en la Ciudad de México.
<!-- REVISAR (Karen): (1) artículo del CNPCF que fija la competencia en divorcio unilateral (el 654 es del bilateral);
     (2) si conviene citar otros del Juicio Oral Familiar; (3) que el CNPCF ya rige este trámite en CDMX
     (declaratoria del Congreso: familiar desde el 1 de junio de 2026). -->

## PRUEBAS

Con fundamento en el artículo 664 del Código Nacional de Procedimientos Civiles y Familiares, ofrezco desde este momento las siguientes pruebas, que relaciono con los hechos de esta solicitud:

**{#pruebas}. DOCUMENTAL PÚBLICA.** Copia certificada del acta de matrimonio, que relaciono con los hechos 1 y 2.
[SI hay_hijos_menores]
**{#pruebas}. DOCUMENTAL PÚBLICA.** Copias certificadas de las actas de nacimiento de nuestras hijas e hijos, que relaciono con el hecho 3.
[/SI][SI regimen = sociedad_conyugal]
**{#pruebas}. DOCUMENTALES.** Los documentos que acreditan la existencia y valor de los bienes de la sociedad conyugal y, en su caso, las capitulaciones matrimoniales, que relaciono con el hecho 4.
[/SI]
**{#pruebas}. INSTRUMENTAL DE ACTUACIONES**, en todo lo que favorezca a mis intereses, que relaciono con todos los hechos.

**{#pruebas}. PRESUNCIONAL LEGAL Y HUMANA**, en todo lo que favorezca a mis intereses, que relaciono con todos los hechos.
<!-- REVISAR (Karen): el modelo de 2008 ofrecía confesional y testimonial para probar los hechos; en el
     divorcio sin causa no hay que acreditar causa, por eso se omitieron. ¿Hace falta alguna otra prueba
     (p. ej. de ingresos del deudor alimentario) cuando se piden alimentos? -->

Por lo antes expuesto,

**A USTED C. JUEZA O JUEZ DE LO FAMILIAR**, atentamente pido se sirva:

**PRIMERO.** Tenerme por presentada o presentado en los términos de este escrito, solicitando el divorcio de {nombre_conyuge}, con la propuesta de convenio que se acompaña.

**SEGUNDO.** Ordenar el emplazamiento de {nombre_conyuge} en el domicilio señalado, corriéndole traslado con las copias exhibidas.

**TERCERO.** Decretar las medidas provisionales solicitadas.

**CUARTO.** Tener por ofrecidas las pruebas señaladas.

**QUINTO.** En su oportunidad, aprobar el convenio propuesto o, en su defecto, decretar la disolución del vínculo matrimonial y resolver sobre sus consecuencias conforme a derecho.

**PROTESTO LO NECESARIO**

Ciudad de México, a {fecha_firma}.

&nbsp;

______________________________
**{nombre_solicitante}**
