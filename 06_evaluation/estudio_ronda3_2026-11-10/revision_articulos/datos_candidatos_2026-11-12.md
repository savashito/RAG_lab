# Datos candidatos para el expediente

Propuestos por gemma-4-31b (razonando) a partir de lo que, al leer cada artículo, el LLM dijo que hace falta saber para decidir si aplica. Primero familia, luego penal; por tipo de caso, de más a menos frases. **existente** = un dato que ya está en la pestaña Datos del expediente.

## Quiero reclamar una herencia o iniciar un juicio sucesorio (`herencias_y_sucesiones`, familiar) · 338 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **existe_testamento** | ¿La persona que falleció dejó un testamento? | si_no | r148, r149 | `existe_testamento = si` | Determina si el juicio es sucesorio testamentario o intestamentario | 16 |
| **parentesco_finado** | ¿Qué relación de parentesco tiene usted con la persona fallecida? | opcion: Cónyuge o concubino, Hijo/a, Padre/Madre, Hermano/a, Otro familiar, Ninguno | r148, r149, r153 | `parentesco_finado = Hijo/a` | Define el orden de prelación para heredar en casos intestados y derechos hereditarios | 13 |
| **rol_sucesorio** | ¿En calidad de qué participa usted en este proceso? | opcion: Heredero, Legatario, Albacea, Acreedor, Otro | r150, r151, r153 | `rol_sucesorio = Albacea` | Identifica si aplican reglas de administración, albaceazgo o adjudicación de legados | 9 |
| **hay_conflicto** | ¿Existe algún desacuerdo o controversia entre los herederos sobre la repartición de los bienes? | si_no | r151, r153 | `hay_conflicto = si` | Determina si se requiere un proceso de partición judicial o una reclamación de derechos | 2 |
| **requiere_alimentos** | ¿Necesita usted reclamar una pensión alimenticia o apoyo económico con cargo a la herencia? | si_no | r152 | `requiere_alimentos = si` | Activa las reglas sobre cargas alimentarias y pensiones en la sucesión | 3 |

## Necesito nombrar un tutor o representante para un menor o incapacitado (`tutela_y_curatela`, familiar) · 167 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **condicion_persona** | ¿La persona que requiere el tutor es menor de edad o es un adulto con alguna discapacidad o incapacidad legal? | opcion: menor_edad, adulto_incapacitado, ambos | r154, r157, r158 | `condicion_persona = menor_edad` | Determina si aplican reglas de tutela para menores o apoyos y capacidad jurídica para adultos | 12 |
| **rol_usuario** | ¿En qué situación te encuentras respecto a la tutela? | opcion: quiero_ser_tutor, ya_soy_tutor, quiero_quitar_a_un_tutor, me_nombraron_pero_no_puedo_aceptar | r154, r155, r156 | `rol_usuario = ya_soy_tutor` | Define si el caso es de nombramiento, administración, remoción o excusa del cargo | 25 |
| **existe_testamento** | ¿Existe algún testamento donde se nombre a un tutor o representante? | si_no | r154 | `existe_testamento = si` | Determina si la tutela es testamentaria o debe ser nombrada por el juez | 18 |
| **tiene_bienes** | ¿La persona que necesita el tutor tiene bienes (como casas, terrenos, cuentas bancarias o herencias) que deban administrarse? | si_no | r155 | `tiene_bienes = si` | Activa las reglas de administración de bienes, inventarios y garantías | 22 |
| **proceso_activo** | ¿Ya hay un proceso legal abierto o un documento de un juez que nombre a un tutor? | si_no | r154, r156 | `proceso_activo = si` | Diferencia entre iniciar un trámite de nombramiento o gestionar una tutela ya existente | 10 |
| **relacion_partes** (existente: `relacion_partes`) | ¿Qué relación tienes con la persona que requiere la tutela? | opcion: pareja o expareja, familiar, trabajo, escuela, ninguna | r154 | `relacion_partes = familiar` | Establece la prelación y el parentesco para el nombramiento del tutor | 10 |

## Tengo un juicio activo y quiero saber sobre las etapas, pruebas o recursos (`procedimiento_judicial_general`, familiar) · 75 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **papel** (existente: `papel`) | ¿Te pasó a ti, te acusan a ti, o le pasó a otra persona? | opcion: actor (quien demanda), demandado (a quien demandan), tercero interesado, otra persona | r185, r186 | `papel = demandado` | Determina si la persona puede reconvenir, contestar la demanda o si es la parte actora | 4 |
| **etapa_actual** | ¿En qué momento se encuentra tu juicio? | opcion: Apenas voy a demandar o me acaban de notificar, Estamos en el periodo de presentar pruebas y audiencias, El juez ya dictó una sentencia, Ya hay sentencia pero no se ha cumplido | r185, r187, r188, r189 | `etapa_actual = Ya hay sentencia pero no se ha cumplido` | Define si aplican reglas de trámite, pruebas, recursos o ejecución de sentencia | 15 |
| **tipo_juicio_familiar** | ¿De qué trata el juicio? | opcion: Alimentos (pensión), Divorcio, Custodia, Patria Potestad o Visitas, Sucesión (herencias), Otro trámite familiar | r185, r191 | `tipo_juicio_familiar = Alimentos (pensión)` | Determina el tipo de procedimiento (oral, sumario) y plazos de prescripción | 8 |
| **notificado_formalmente** | ¿Ya recibiste la notificación oficial del juzgado en tu domicilio? | si_no | r186 | `notificado_formalmente = no` | Decide si el emplazamiento fue correcto o si hay que analizar la nulidad de notificaciones | 6 |
| **existe_impugnacion** | ¿Estás inconforme con una decisión del juez y quieres cambiarla, o ya presentaste una apelación? | si_no | r188 | `existe_impugnacion = si` | Determina si aplican los artículos de recursos, apelaciones e impugnaciones | 4 |
| **personas_vulnerables** | ¿El caso involucra a niños, niñas, adolescentes o personas con alguna discapacidad? | si_no | r185, r187 | `personas_vulnerables = si` | Activa reglas especiales de protección, pruebas específicas y prioridad procesal | 4 |

## Tengo problemas con el reconocimiento de hijos o la patria potestad (`patria_potestad_y_filiacion`, familiar) · 66 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **edad_hijo** (existente: `edad_victima`) | ¿Qué edad tiene el hijo o los hijos? | numero | r143, r144, r145, r146 | `edad_hijo < 18` | Determina si es menor de edad, mayor de edad o si aplica la incapacidad de ejercicio hasta los 22 años | 15 |
| **estado_civil_nacimiento** | ¿Cuál era la relación o estado civil de los padres al momento del nacimiento del hijo? | opcion: Casados, Concubinato, Solteros / Ninguna | r143, r144 | `estado_civil_nacimiento = 'Casados'` | Define si el hijo nació dentro del matrimonio o si existe presunción de paternidad | 6 |
| **reconocimiento_legal** | ¿El hijo ya está reconocido legalmente en el acta de nacimiento? | si_no | r143, r144 | `reconocimiento_legal = 'no'` | Diferencia entre un proceso de reconocimiento inicial y una impugnación de filiación | 6 |
| **motivo_patria_potestad** | ¿Cuál es el motivo por el que se cuestiona la patria potestad? | opcion: Violencia o riesgo para el menor, Adicciones o salud mental, Abandono o falta de cuidado, Incumplimiento de obligaciones, Incapacidad legal | r145 | `motivo_patria_potestad = 'Violencia o riesgo para el menor'` | Determina la causa de suspensión, pérdida o extinción de la patria potestad | 4 |
| **tiene_bienes** | ¿El hijo tiene bienes a su nombre (como casas, terrenos, cuentas bancarias o rentas)? | si_no | r146 | `tiene_bienes = 'si'` | Activa las reglas sobre la administración de bienes de menores y conflictos de interés | 8 |
| **fallecimiento_parte** | ¿Alguna de las personas involucradas (padre, madre o hijo) ha fallecido? | si_no | r143, r144, r145 | `fallecimiento_parte = 'si'` | Aplica reglas especiales de filiación post-mortem o extinción de patria potestad | 5 |

## Necesito pedir, cobrar o cancelar una pensión alimenticia (`pension_alimenticia`, familiar) · 60 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **objetivo_pension** | ¿Qué necesitas hacer con la pensión alimenticia? | opcion: Pedirla por primera vez, Cobrar una que ya me deben o que no se paga completa, Cambiar el monto (aumentar o disminuir), Cancelar la pensión o dejar de pagarla | r132, r133, r134, r135 | `objetivo_pension = 'Pedirla por primera vez'` | Define si el caso es de solicitud, cobro, modificación o cancelación | 10 |
| **vinculo_legal** (existente: `relacion_partes`) | ¿Cuál es el vínculo legal con la persona que debe dar la pensión? | opcion: Matrimonio, Concubinato (unión libre), Padre/Madre e hijo(a), Otro parentesco (abuelos, hermanos, etc.) | r132, r135, r136 | `vinculo_legal = 'Matrimonio'` | Determina los artículos según el parentesco o estado civil | 12 |
| **tiene_sentencia** | ¿Ya existe un documento o sentencia de un juez que obligue al pago de la pensión? | si_no | r133, r134, r137 | `tiene_sentencia = si` | Diferencia entre iniciar un juicio o ejecutar una sentencia ya existente | 15 |
| **condicion_alimentista** | ¿La persona que recibe la pensión es menor de edad, tiene alguna discapacidad o se dedica exclusivamente al hogar? | opcion: Menor de edad, Persona con discapacidad, Dedicado al hogar, Ninguna de las anteriores | r132, r134, r135 | `condicion_alimentista = 'Menor de edad'` | Identifica vulnerabilidad para aplicar reglas de monto o cese de pensión | 6 |
| **tiempo_incumplimiento** | ¿Hace cuántos meses que no se paga la pensión o se paga incompleta? | numero | r133 | `tiempo_incumplimiento >= 3` | Determina si se puede iniciar un proceso de ejecución o cobro forzoso | 5 |

## Me quiero divorciar o separarme de mi pareja (`divorcio_y_separacion`, familiar) · 57 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **acuerdo_mutuo** | ¿Tú y tu pareja están de acuerdo en divorciarse y en los términos de la separación? | si_no | r125, r126 | `acuerdo_mutuo = si` | Determina si procede el divorcio administrativo o un trámite bilateral más rápido | 8 |
| **hijos_menores_o_discapacidad** | ¿Tienen hijos menores de edad o hijos con alguna discapacidad? | si_no | r125, r126, r129 | `hijos_menores_o_discapacidad = si` | Define la necesidad de convenios de alimentos, custodia y excluye el divorcio administrativo simple | 4 |
| **bienes_pendientes** | ¿Tienen bienes, propiedades o deudas que deban repartirse? | si_no | r126, r130 | `bienes_pendientes = si` | Activa las reglas de liquidación de la sociedad conyugal o donaciones | 4 |
| **busca_nulidad** | ¿Buscas anular el matrimonio porque hubo algún engaño, error o problema legal al momento de casarse? | si_no | r127 | `busca_nulidad = si` | Diferencia el divorcio (disolución) de la nulidad (el matrimonio nunca fue válido) | 6 |
| **riesgo_o_violencia** | ¿Existe alguna situación de violencia o riesgo urgente para tu salud o integridad? | si_no | r128, r129 | `riesgo_o_violencia = si` | Determina la aplicación de medidas provisionales urgentes y protección | 5 |
| **juicio_activo** | ¿Ya iniciaron algún trámite o juicio de divorcio ante un juez? | si_no | r131 | `juicio_activo = si` | Identifica la etapa procesal y si se requiere seguimiento de un expediente existente | 8 |

## Una persona desapareció y necesito declarar su ausencia o muerte (`ausencia_y_presuncion_muerte`, familiar) · 41 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **tiempo_desaparicion** | ¿Cuánto tiempo ha pasado desde que la persona desapareció? | numero | r180, r181 | `tiempo_desaparicion >= 2` | Determina si procede la declaración de ausencia o la presunción de muerte según los plazos legales | 2 |
| **causa_desastre** | ¿La desaparición ocurrió durante un desastre natural, un accidente o una situación de peligro? | si_no | r181 | `causa_desastre = si` | Reduce los plazos para declarar la presunción de muerte en casos de riesgo | 2 |
| **estado_civil_ausente** | ¿Cuál era el estado civil de la persona desaparecida? | opcion: soltero, casado, divorciado, viudo, concubinato | r183 | `estado_civil_ausente = casado` | Define si aplica la liquidación de la sociedad conyugal o derechos del cónyuge | 5 |
| **tiene_hijos_dependientes** | ¿La persona desaparecida tiene hijos menores de edad o personas que dependan económicamente de ella? | si_no | r184 | `tiene_hijos_dependientes = si` | Determina la obligación de fijar pensiones alimenticias y la representación de los hijos | 3 |
| **declaracion_previa** | ¿Ya existe algún trámite legal iniciado o una sentencia que declare la ausencia o la muerte de la persona? | si_no | r180, r181, r182 | `declaracion_previa = si` | Evita duplicidad de procesos y define si se pasa a la etapa de posesión de bienes | 7 |
| **testamento_o_apoderado** | ¿Sabes si la persona dejó un testamento o nombró a alguien como apoderado general para manejar sus bienes? | si_no | r182 | `testamento_o_apoderado = si` | Define quién debe administrar los bienes y si se requiere un tutor o representante legal | 5 |

## Tengo dudas sobre mis bienes, la sociedad conyugal o el patrimonio familiar (`bienes_matrimoniales_y_familiares`, familiar) · 39 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **estatus_matrimonial** | ¿Cuál es su situación matrimonial actual? | opcion: casados, divorciados, separados, no_casados | r168, r169 | `estatus_matrimonial = casados` | Determina si aplica el régimen matrimonial o la liquidación de la sociedad | 2 |
| **regimen_patrimonial** | ¿Bajo qué régimen se casaron: sociedad conyugal (bienes mancomunados) o separación de bienes? | opcion: sociedad_conyugal, separacion_bienes, no_lo_se | r168, r169, r173 | `regimen_patrimonial = sociedad_conyugal` | Es el dato principal para decidir qué artículos de reparto y propiedad aplican | 12 |
| **tiene_capitulaciones** | ¿Firmaron algún convenio o contrato donde acordaron cómo repartir sus bienes (capitulaciones matrimoniales)? | si_no | r168, r169 | `tiene_capitulaciones = si` | Determina si prevalecen los acuerdos privados sobre la ley general | 5 |
| **hubo_donaciones_herencias** | ¿Alguna de las personas recibió o dio alguna donación o herencia de bienes? | si_no | r171 | `hubo_donaciones_herencias = si` | Define si los bienes son propios o entran en la sociedad conyugal | 5 |
| **hijos_menores_o_patrimonio** | ¿Tienen hijos menores de edad o algún bien registrado legalmente como patrimonio de familia? | si_no | r170, r172 | `hijos_menores_o_patrimonio = si` | Activa reglas de protección de bienes y patria potestad | 4 |
| **trabajo_hogar** | ¿Alguna de las personas se dedicó principalmente al trabajo del hogar o al cuidado de los hijos? | si_no | r169 | `trabajo_hogar = si` | Determina el derecho a compensación económica en el reparto de bienes | 1 |

## Quiero adoptar un niño o recuperar a un menor trasladado (`adopcion_y_restitucion`, familiar) · 35 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **objetivo_tramite** | ¿Qué es lo que buscas hacer exactamente? | opcion: adoptar a un menor, recuperar a un menor que fue trasladado, anular una adopción ya realizada | r163, r164, r165, r166, r167 | `objetivo_tramite = 'adoptar a un menor'` | Define si el caso es de adopción, restitución o nulidad | 5 |
| **es_internacional** | ¿Tú o el menor viven en otro país, o el menor fue llevado fuera de México? | si_no | r164, r166 | `es_internacional = si` | Diferencia entre procesos nacionales e internacionales | 12 |
| **existe_sentencia** | ¿Ya existe una sentencia o un documento legal de un juez sobre la adopción o la custodia del menor? | si_no | r167, r165, r166 | `existe_sentencia = si` | Determina si aplica la nulidad de adopción o si hay un proceso de custodia previo | 6 |
| **edad_victima** (existente: `edad_victima`) | ¿Qué edad tiene el niño o niña? | numero | r163, r164 | `edad_victima < 18` | Verifica si el menor cumple la edad para adopción o si es adolescente | 7 |
| **relacion_partes** (existente: `relacion_partes`) | ¿Qué relación tienes con el menor? | opcion: pareja o expareja, familiar, trabajo, escuela, ninguna | r163 | `relacion_partes = 'familiar'` | Identifica si existe parentesco consanguíneo para la adopción | 3 |
| **traslado_ilegal** | ¿El menor fue trasladado o retenido sin el permiso de quien tiene la custodia legal? | si_no | r165, r166 | `traslado_ilegal = si` | Confirma si el caso es de restitución por traslado ilegal | 4 |

## Quiero regularizar la custodia de mis hijos o mis visitas (`custodia_y_convivencias`, familiar) · 17 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **edad_victima** (existente: `edad_victima`) | ¿Qué edad tienen los niños o niñas? | numero | r138, r139, r140, r141 | `edad_victima < 18` | Determina si son menores de edad, niños o adolescentes para aplicar derechos específicos | 3 |
| **parentesco_con_menor** | ¿Qué parentesco tiene usted con el menor? | opcion: padre o madre, abuelo o abuela, otro familiar, ninguno | r138, r139, r141 | `parentesco_con_menor = 'abuelo o abuela'` | Define si la solicitud de convivencia es de un progenitor o de un ascendiente | 3 |
| **acuerdo_custodia_previo** | ¿Ya existe algún acuerdo o convenio sobre la custodia y las visitas, o viven juntos los padres? | opcion: viven juntos, hay acuerdo de custodia, no hay acuerdo ni viven juntos | r138, r139 | `acuerdo_custodia_previo = 'hay acuerdo de custodia'` | Determina si se debe establecer la custodia desde cero o regularizar un acuerdo existente | 3 |
| **residencia_internacional** | ¿Alguno de los padres vive en otro país? | si_no | r142 | `residencia_internacional = si` | Activa las reglas de cooperación internacional y trámites especiales | 2 |
| **capacidad_juridica_vulnerable** | ¿La persona involucrada tiene alguna discapacidad o condición que le impida tomar decisiones legales por sí misma? | si_no | r141, r142 | `capacidad_juridica_vulnerable = si` | Determina si se requiere representación jurídica especial o protección de grupos vulnerables | 2 |
| **orden_judicial_previa** | ¿Ya existe una orden de un juez para que el menor se presente o sea entregado? | si_no | r139, r142 | `orden_judicial_previa = si` | Identifica si el caso es una solicitud nueva o el cumplimiento de una orden judicial | 1 |

## Necesito corregir un acta o cambiar mi nombre o género (`registro_civil_y_estado_civil`, familiar) · 15 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **tramite_objetivo** | ¿Qué trámite necesitas realizar? | opcion: corregir_acta, cambio_nombre_genero, matrimonio, acreditar_estado_civil, otro | r174, r175, r176, r177, r178, r179 | `tramite_objetivo = 'cambio_nombre_genero'` | Define la regla principal y el tipo de acta involucrada | 4 |
| **papel** (existente: `papel`) | ¿Te pasó a ti, te acusan a ti, o le pasó a otra persona? | opcion: ti, otra_persona | r174, r177, r178 | `papel = 'otra_persona'` | Determina el parentesco con el titular del acta y la capacidad de concurrir | 3 |
| **resolucion_judicial** | ¿Ya cuentas con una sentencia o resolución de un juez sobre este trámite? | si_no | r174, r177 | `resolucion_judicial = 'si'` | Diferencia entre trámite administrativo y ejecución de sentencia judicial | 1 |
| **lugar_acto_mexico** | ¿El acto que quieres registrar o corregir ocurrió dentro de México? | si_no | r177, r178, r179 | `lugar_acto_mexico = 'no'` | Determina si aplica la ley nacional o trámites de actas extranjeras | 3 |
| **impedimento_matrimonial** | En caso de matrimonio, ¿alguna de las personas tiene una sentencia por violencia familiar o es menor de edad? | si_no | r175, r176 | `impedimento_matrimonial = 'si'` | Identifica impedimentos legales para la validez del matrimonio | 3 |
| **pueblo_indigena** | ¿La persona interesada pertenece a algún pueblo indígena? | si_no | r174, r177, r179 | `pueblo_indigena = 'si'` | Aplica reglas especiales de registro para comunidades indígenas | 1 |

## Busco designar apoyos para tomar decisiones legales (`apoyos_y_capacidad_juridica`, familiar) · 9 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **puede_manifestar_voluntad** | ¿La persona puede expresar sus deseos, preferencias o voluntad? | si_no | r159, r161, r162 | `puede_manifestar_voluntad = no` | Determina si la designación es directa o si requiere intervención de terceros o procesos especiales | 2 |
| **tiene_apoyo_previo** | ¿Ya cuenta la persona con alguien designado como apoyo para tomar decisiones? | si_no | r160 | `tiene_apoyo_previo = si` | Define si el trámite es una designación inicial o una modificación/revocación | 2 |
| **tiene_discapacidad** | ¿La persona tiene alguna discapacidad? | si_no | r159, r162 | `tiene_discapacidad = si` | Aplica reglas específicas sobre el alcance de la capacidad jurídica y el tipo de apoyo | 1 |
| **papel** (existente: `papel`) | ¿Te pasó a ti, te acusan a ti, o le pasó a otra persona? | opcion: Te pasó a ti, te acusan a ti, le pasó a otra persona | r161 | `papel = le pasó a otra persona` | Identifica si la solicitud de apoyos es realizada por la propia persona o por un tercero | 1 |
| **problemas_con_apoyo** | ¿Ha habido algún incumplimiento, conflicto de intereses o mala fe por parte del apoyo actual? | si_no | r160 | `problemas_con_apoyo = si` | Justifica la revocación o modificación urgente de los apoyos designados | 2 |
| **tipo_apoyo** | ¿El apoyo será una persona física o una organización sin fines de lucro? | opcion: persona, organizacion_sin_fines_lucro | r159 | `tipo_apoyo = organizacion_sin_fines_lucro` | Determina los requisitos legales según la naturaleza jurídica del apoyo | 1 |

## Me acusan, me citaron o me detuvieron (`proceso_penal`, penal) · 598 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **detenido** | ¿Te encuentras detenido o privado de tu libertad en este momento? | si_no | r083 | `detenido = si` | Determina si aplican reglas de flagrancia, prisión preventiva o plazos de detención | 12 |
| **etapa_actual** | ¿En qué punto se encuentra tu proceso? | opcion: Apenas me citaron o acusan, Ya me vincularon a proceso, Estoy en la etapa de juicio, Ya hubo una sentencia | r083 | `etapa_actual = 'Ya me vincularon a proceso'` | Define qué artículos del CNPP aplican según la fase procesal | 35 |
| **sentencia_previa** | ¿Ya cuentas con una sentencia condenatoria firme por este o cualquier otro delito? | si_no | r083 | `sentencia_previa = si` | Determina si es delincuente primario o si aplica la ejecución de penas | 18 |
| **tipo_persona** | ¿La acusación es contra ti como persona física o contra una empresa o sociedad? | opcion: Persona física, Empresa o sociedad (persona moral) | r083 | `tipo_persona = 'Empresa o sociedad (persona moral)'` | Diferencia la responsabilidad penal de personas físicas frente a personas jurídicas | 12 |
| **asistencia_internacional** | ¿Tu caso involucra a otro país, personas que viven fuera de México o requiere ayuda legal internacional? | si_no | r083 | `asistencia_internacional = si` | Activa las reglas de asistencia jurídica internacional y exhortos | 10 |
| **condicion_mental** | ¿Tienes alguna discapacidad o condición de salud mental que afecte tu capacidad de comprender el proceso? | si_no | r083 | `condicion_mental = si` | Determina si la persona es inimputable | 8 |

## Animales o medio ambiente (`animales_ambiente`, penal) · 98 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **sujeto_afectado** | ¿El problema es sobre maltrato a animales o sobre daño al medio ambiente (como tala, contaminación o incendios)? | opcion: animales, medio_ambiente | r084, r085, r086 | `sujeto_afectado = animales` | Determina si el caso se orienta a maltrato animal o a delitos ambientales/gestión | 100 |
| **detalle_animal** | Si es sobre animales, ¿qué sucedió? (por ejemplo: murió, fue herido, se usó para peleas, fines sexuales o se prolongó su agonía) | opcion: muerte_o_lesion_grave, peleas_o_fines_sexuales, crueldad_agonía, otros | r084 | `detalle_animal = muerte_o_lesion_grave` | Define la gravedad del maltrato y si aplica el delito de crueldad | 12 |
| **area_protegida** | ¿El lugar donde ocurrió es un área natural protegida, suelo de conservación, barranca o área verde urbana? | si_no | r085, r086 | `area_protegida = si` | Aumenta la gravedad del delito ambiental y cambia los artículos aplicables | 10 |
| **tipo_daño_ambiental** | ¿En qué consistió el daño al ambiente? (por ejemplo: tala de árboles, incendio forestal, derrame de sustancias o residuos peligrosos) | opcion: tala_incendio, contaminacion_residuos, otros | r085, r086 | `tipo_daño_ambiental = contaminacion_residuos` | Identifica la conducta específica para aplicar la regla de delitos contra el ambiente | 8 |
| **persona_moral** | ¿La persona o entidad involucrada es una empresa, institución o asociación, o es un individuo? | opcion: empresa_institucion, individuo | r085, r086 | `persona_moral = empresa_institucion` | Determina si la responsabilidad es de una persona moral, común en gestión ambiental | 4 |
| **verificacion_vehicular** | ¿El caso tiene que ver con la verificación de vehículos, centros de verificación o alteración de equipos para aprobarla? | si_no | r086 | `verificacion_vehicular = si` | Aplica específicamente a delitos contra la gestión ambiental | 5 |

## Me robaron (`robo`, penal) · 96 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **objeto_robado** | ¿Qué fue lo que robaron? | opcion: Vehículo o autopartes, Ganado o animales, Dinero, joyas o artículos de valor, Documentos oficiales, Energía eléctrica o fluidos, Equipo agrícola o industrial, Otro | r035 | `objeto_robado = 'Ganado o animales'` | Determina agravantes específicas y si el delito es robo simple o especializado | 25 |
| **lugar_especifico** | ¿En qué lugar ocurrió el robo? | opcion: Casa habitación o cuarto, Local comercial o bodega, Transporte público o vehículo, Lugar solitario o despoblado, Oficina pública, Otro | r035 | `lugar_especifico = 'Casa habitación o cuarto'` | Define si el robo es calificado por el lugar del hecho | 12 |
| **tenencia_previa** | ¿La persona que tomó el objeto ya lo tenía en su poder legalmente (por ejemplo, se lo prestaron o era su trabajo cuidarlo)? | si_no | r036 | `tenencia_previa = 'si'` | Diferencia entre robo y abuso de confianza | 8 |
| **conocimiento_ilícito** | ¿Se sabía que el objeto provenía de un robo o de un delito? | si_no | r037 | `conocimiento_ilícito = 'si'` | Determina si aplica el delito de encubrimiento por receptación | 5 |
| **restitucion_daños** | ¿Se devolvió el objeto o se pagaron los daños antes de que la autoridad interviniera? | si_no | r035, r036 | `restitucion_daños = 'si'` | Identifica causas de reducción de pena o extinción de la acción penal | 7 |
| **num_participantes** | ¿Cuántas personas participaron en el robo? | numero | r035 | `num_participantes > 1` | Determina si el robo fue cometido en banda o por varias personas (agravante) | 2 |

## Problemas con la Fiscalía, un juzgado o un abogado (`justicia_abogados`, penal) · 77 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **profesion_especifica** | ¿La persona señalada es abogado, perito, médico o algún otro profesional? | opcion: abogado, perito, medico, otro_profesional, ninguno | r115, r122 | `profesion_especifica = abogado` | Determina si aplican delitos específicos de abogados, peritos o personal de salud | 12 |
| **estatus_libertad** | ¿La persona estaba presa, en reclusión domiciliaria o en libertad? | opcion: preso, reclusion_domiciliaria, libre | r116, r117 | `estatus_libertad = preso` | Define si el caso es de evasión de presos o delitos en ejecución penal | 10 |
| **manipulacion_pruebas** | ¿Hubo mentiras en declaraciones, testigos falsos o se alteraron documentos y pruebas? | si_no | r118, r119, r120 | `manipulacion_pruebas = si` | Identifica fraude procesal, falsedad ante autoridades o simulación de pruebas | 15 |
| **conducta_servidor** | ¿El servidor público ignoró un plazo legal, desobedeció a un jefe o negó un trámite? | si_no | r112, r113, r114 | `conducta_servidor = si` | Diferencia entre retardo de justicia y delitos en la administración o procuración | 8 |
| **ayuda_a_delincuente** | ¿Se ayudó a alguien a esconderse, a ocultar pruebas o a evitar que lo atraparan? | si_no | r123 | `ayuda_a_delincuente = si` | Determina si se trata de un delito de encubrimiento por favorecimiento | 6 |

## Atención médica o de salud (`salud`, penal) · 71 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **profesion_salud** | ¿La persona señalada es profesional de la salud (como médico, enfermera, partera o farmacéutico) o dice serlo sin tener título? | opcion: Es profesional con título, Dice ser profesional pero no tiene título, Es empleado de farmacia, No es profesional de la salud | r067, r068, r074, r075 | `profesion_salud = 'Es profesional con título'` | Determina si aplica responsabilidad profesional, usurpación de profesión o delitos cometidos por personal de farmacia | 15 |
| **contexto_reproductivo** | ¿El caso tiene que ver con un embarazo, la interrupción de uno, o la capacidad de tener hijos (esterilización)? | si_no | r069, r070 | `contexto_reproductivo = si` | Define si el caso se orienta hacia aborto o esterilización forzada | 12 |
| **sustancias_procedimientos** | ¿Se aplicó alguna sustancia, medicamento o se realizó un procedimiento médico o estético? | si_no | r072, r073, r074 | `sustancias_procedimientos = si` | Identifica si hubo administración de sustancias nocivas, modelantes o medicinas inapropiadas | 10 |
| **enfermedad_contagio** | ¿El problema es que alguien contagió a otra persona de una enfermedad grave sabiendo que la padecía? | si_no | r071 | `enfermedad_contagio = si` | Aplica la regla de peligro de contagio | 4 |
| **vulnerabilidad_victima** | ¿La persona afectada tiene alguna discapacidad mental, es adulto mayor o se encuentra en una situación de extrema pobreza o ignorancia? | si_no | r069, r073 | `vulnerabilidad_victima = si` | Determina agravantes por incapacidad o vulnerabilidad de la víctima | 5 |
| **administrador_salud_funeraria** | ¿La persona señalada es el dueño, director o administrador de una clínica, centro de salud o funeraria y retuvo a alguien o algo por una deuda? | si_no | r068 | `administrador_salud_funeraria = si` | Aplica la regla de abandono o práctica indebida relacionada con retención por adeudo | 4 |

## Problemas con una autoridad por algo que hizo la persona (`conflicto_con_autoridad`, penal) · 71 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **grupo_personas** | ¿Se encontraba usted con más personas o se pusieron de acuerdo para realizar esta acción? | si_no | r104, r105, r108 | `grupo_personas = si` | Determina si el acto fue tumultuario o hubo común acuerdo | 12 |
| **uso_insignias** | ¿Utilizó, fabricó, vendió o portaba uniformes, insignias, placas o identificaciones de seguridad pública o del ejército? | si_no | r109 | `uso_insignias = si` | Identifica el uso indebido de insignias y uniformes | 8 |
| **llamada_falsa** | ¿Realizó usted una llamada de emergencia o reportó hechos que resultaron ser falsos? | si_no | r110 | `llamada_falsa = si` | Determina el uso indebido de servicios de emergencia | 6 |
| **romper_sellos** | ¿Rompiste sellos, candados o cintas que la autoridad había colocado para clausurar o suspender un lugar? | si_no | r106 | `romper_sellos = si` | Identifica el quebrantamiento de sellos oficiales | 3 |
| **desobedecer_orden** | ¿Ignoró usted una orden directa, un citatorio o una sentencia emitida por un juez o autoridad? | si_no | r104 | `desobedecer_orden = si` | Determina la existencia de desobediencia a mandatos judiciales o administrativos | 7 |
| **ofrecer_dinero** | ¿Le ofreció usted dinero, regalos o algún beneficio a un servidor público para obtener un favor? | si_no | r111 | `ofrecer_dinero = si` | Identifica el cohecho cometido por particulares | 1 |

## Me estafaron o usaron mis datos (`fraude_datos`, penal) · 68 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **administraba_bienes** | ¿La persona que te afectó tenía a su cargo el cuidado o la administración de tu dinero, tus propiedades o tus bienes? | si_no | r039, r040 | `administraba_bienes = si` | Determina si es administración fraudulenta o insolvencia en lugar de fraude simple | 5 |
| **suplantacion_identidad** | ¿La persona se hizo pasar por ti, usó tu nombre, tu voz o tu parecido físico para engañar a otros o identificarse como tú? | si_no | r041 | `suplantacion_identidad = si` | Identifica el delito de usurpación de identidad | 3 |
| **objeto_falsificado** | ¿Se falsificó, alteró o se usó indebidamente algún documento, firma, sello, llave, tarjeta bancaria o cheque? | si_no | r042, r043, r044 | `objeto_falsificado = si` | Diferencia entre fraude simple y delitos de falsificación | 18 |
| **tipo_documento_falsificado** | Si hubo algo falsificado, ¿era un documento oficial del gobierno, un contrato privado, una tarjeta de crédito/débito o un objeto como sellos o llaves? | opcion: oficial, privado, tarjeta_credito, objeto_sello_llave, otro | r042, r043, r044 | `tipo_documento_falsificado = oficial` | Define qué artículo de falsificación aplica según la naturaleza del objeto | 12 |
| **acceso_sistema_informatico** | ¿Entraron sin permiso a una computadora, cuenta de internet, sistema de videovigilancia o base de datos? | si_no | r045 | `acceso_sistema_informatico = si` | Determina si aplica el delito de acceso ilícito a sistemas informáticos | 11 |
| **modalidad_engaño** | ¿El engaño tuvo que ver con una oferta de trabajo, una inversión, una deuda que no querían pagar o la venta de un terreno? | opcion: empleo, deuda_insolvencia, terreno_propiedad, otro_engaño | r038, r040 | `modalidad_engaño = empleo` | Clasifica la modalidad del fraude para aplicar agravantes o reglas específicas | 7 |

## Murió una persona (`muerte`, penal) · 66 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **ayuda_suicidio** | ¿La persona murió porque alguien la ayudó o la convenció de quitarse la vida? | si_no | r008 | `ayuda_suicidio = si` | Determina si el caso es de ayuda o inducción al suicidio | 5 |
| **signos_genero** | ¿Hubo signos de violencia sexual, el cuerpo fue expuesto en un lugar público, hubo mutilaciones o la persona estaba incomunicada? | si_no | r006, r007 | `signos_genero = si` | Identifica razones de género para feminicidio o transfeminicidio | 10 |
| **victima_trans** | ¿La víctima era una mujer trans? | si_no | r007 | `victima_trans = si` | Diferencia entre feminicidio y transfeminicidio | 3 |
| **contexto_muerte** | ¿La muerte ocurrió durante una pelea (riña), un robo, un secuestro o una violación? | opcion: pelea, robo_secuestro_violacion, ninguno | r005 | `contexto_muerte = pelea` | Define circunstancias calificativas del homicidio | 7 |
| **enfermedad_terminal** | ¿La persona padecía una enfermedad incurable o en fase terminal? | si_no | r008 | `enfermedad_terminal = si` | Evalúa si aplica la ley de voluntad anticipada o eutanasia | 4 |

## Golpes, peleas o lesiones (`golpes_lesiones`, penal) · 64 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **uso_sustancias_quimicas** | ¿Se utilizaron ácidos, sustancias químicas, corrosivas o líquidos a altas temperaturas para causar la lesión? | si_no | r002 | `uso_sustancias_quimicas = si` | Determina si aplica la regla de lesiones con ácido | 6 |
| **pelea_mutua** | ¿Fue una pelea donde ambas personas se agredieron mutuamente o hubo una provocación? | si_no | r003 | `pelea_mutua = si` | Determina si el caso se clasifica como riña | 9 |
| **uso_arma_fuego** | ¿Se realizó algún disparo de arma de fuego durante los hechos? | si_no | r004 | `uso_arma_fuego = si` | Determina si aplica la regla de disparo de arma | 2 |
| **ventaja_agresor** | ¿El agresor tenía alguna ventaja, como ser más fuerte, usar un arma, o sorprendió a la víctima sin que pudiera defenderse? | si_no | r001 | `ventaja_agresor = si` | Identifica circunstancias calificativas de las lesiones | 8 |
| **perfil_victima_especial** | ¿La víctima es integrante de una institución de seguridad, periodista, defensora de derechos humanos o persona con discapacidad? | si_no | r001 | `perfil_victima_especial = si` | Aplica agravantes según la calidad de la víctima | 5 |
| **estado_agresor_auxilio** | ¿La persona que agredió estaba bajo el efecto del alcohol o drogas, o se fue del lugar sin prestar auxilio a la víctima? | si_no | r001 | `estado_agresor_auxilio = si` | Determina agravantes por estado del agresor u omisión de auxilio | 10 |

## Violencia en la familia o la pareja (`violencia_familiar`, penal) · 56 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **uso_hijos_daño** | ¿Se han utilizado a los hijos, padres o personas a su cargo como un medio para causarle daño o sufrimiento? | si_no | r010, r194 | `uso_hijos_daño = si` | Determina si se configura violencia vicaria | 3 |
| **problema_alimentos** | ¿Existe un problema relacionado con el incumplimiento de una pensión alimenticia o manutención? | si_no | r011 | `problema_alimentos = si` | Identifica delitos de incumplimiento de obligaciones alimentarias | 7 |
| **medidas_proteccion_refugio** | ¿Cuenta actualmente con una orden de protección vigente o se encuentra en un refugio? | si_no | r193, r196 | `medidas_proteccion_refugio = si` | Define la urgencia de medidas de protección y el riesgo actual | 6 |
| **estado_vulnerabilidad** | ¿Se encuentra en estado de embarazo, tiene alguna discapacidad o padece alguna enfermedad? | si_no | r009, r192 | `estado_vulnerabilidad = si` | Establece agravantes por vulnerabilidad de la víctima | 6 |
| **convivencia_bienes** | ¿Habita la misma casa que la persona agresora o comparten bienes y patrimonio? | si_no | r195 | `convivencia_bienes = si` | Determina la aplicación de protección en divorcio y violencia patrimonial | 4 |
| **proceso_legal_abierto** | ¿Ya existe una denuncia formal, una investigación penal abierta o una sentencia judicial sobre este caso? | si_no | r196 | `proceso_legal_abierto = si` | Define la etapa procesal y la aplicación de reglas de seguimiento legal | 3 |

## Armas, pandillas o crimen organizado (`armas_crimen_organizado`, penal) · 56 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **num_personas** | ¿Cuántas personas estaban involucradas o participaron en los hechos? | numero | r089, r090, r091 | `num_personas >= 3` | Determina si el caso encuadra en pandilla, asociación delictuosa o delincuencia organizada | 13 |
| **organizacion_delictiva** | ¿Estas personas estaban organizadas, eran una pandilla o formaban parte de un grupo criminal? | si_no | r089, r090, r091 | `organizacion_delictiva = si` | Diferencia entre un delito cometido por varias personas y el crimen organizado | 7 |
| **permiso_arma** | ¿Tenías permiso, licencia o un motivo legal (como el trabajo) para portar el arma u objeto? | si_no | r087, r088 | `permiso_arma = no` | Determina si la portación de armas u objetos es legal o constituye un delito | 6 |
| **recursos_ilicitos** | ¿Se utilizó dinero, bienes o propiedades que provengan de actividades ilegales? | si_no | r092 | `recursos_ilicitos = si` | Aplica la regla de operaciones con recursos de procedencia ilícita (lavado de dinero) | 8 |
| **rol_organizacion** | ¿Qué función desempeñaba la persona en el grupo? (por ejemplo: mando/administración, operativo o ninguna) | opcion: mando, operativo, ninguna | r091 | `rol_organizacion = mando` | Define la gravedad de la pena según la jerarquía en la organización criminal | 3 |

## Niñas, niños o personas vulnerables (`menores_vulnerables`, penal) · 53 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **capacidad_o_discapacidad** | ¿La víctima tiene alguna discapacidad física o mental, o alguna condición que le impida valerse por sí misma o comprender lo que estaba pasando? | si_no | r076, r077, r078, r080, r082 | `capacidad_o_discapacidad = si` | Determina si la víctima es vulnerable por capacidad cognitiva o física | 15 |
| **obligacion_legal_cuidado** | ¿La persona señalada es el tutor legal, tiene la patria potestad o tiene la obligación legal de cuidar a la víctima? | si_no | r076, r079, r080 | `obligacion_legal_cuidado = si` | Identifica si existe un deber legal de cuidado (agravante o elemento del tipo) | 8 |
| **tipo_explotacion** | ¿Cuál era el objetivo o qué se obtenía? (por ejemplo: trabajo forzado, actos sexuales, mendicidad, extracción de órganos o dinero) | opcion: sexual, laboral, mendicidad, organos, otro | r077, r078, r079, r081 | `tipo_explotacion = sexual` | Diferencia entre trata, lenocinio y explotación laboral | 6 |
| **lugar_nocivo** | ¿El hecho ocurrió en un lugar como un bar, antro, cantina o algún sitio donde se vendan alcohol o drogas? | si_no | r078, r079, r081 | `lugar_nocivo = si` | Determina si el entorno es nocivo para el desarrollo de menores | 5 |
| **auxilio_sin_riesgo** | ¿La persona que no ayudó podía prestar auxilio sin ponerse en riesgo ella misma o poner en riesgo a otros? | si_no | r082 | `auxilio_sin_riesgo = si` | Define si la omisión de auxilio es punible | 4 |
| **vulnerabilidad_social** | ¿La víctima pertenece a un pueblo indígena, afromexicano o se encuentra en una situación de pobreza extrema (marginalidad)? | si_no | r077, r078 | `vulnerabilidad_social = si` | Identifica condiciones de vulnerabilidad social adicionales | 3 |

## Corrupción en el gobierno (la persona la denuncia) (`corrupcion_gobierno`, penal) · 51 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **coalicion_servidores** | ¿Hubo un acuerdo o coalición entre dos o más servidores públicos para cometer el acto? | si_no | r099 | `coalicion_servidores = si` | Determina si aplica el delito de coalición de servidores públicos | 4 |
| **corrupcion_inmobiliaria** | ¿El caso tiene que ver con permisos de construcción, obras públicas, inmuebles o cambio de uso de suelo? | si_no | r102, r097 | `corrupcion_inmobiliaria = si` | Identifica si el caso cae en corrupción inmobiliaria o delitos de obra pública | 5 |
| **cargo_confianza_electo** | ¿La persona que cometió el acto es un funcionario de confianza o fue elegido por voto popular? | si_no | r098, r101 | `cargo_confianza_electo = si` | Diferencia la gravedad y el artículo según el nivel jerárquico o nombramiento | 7 |
| **usurpacion_identidad** | ¿La persona se hizo pasar por servidor público, usó un uniforme o una identificación falsa sin serlo? | si_no | r100 | `usurpacion_identidad = si` | Determina si hubo usurpación de funciones públicas | 4 |
| **enriquecimiento_evidente** | ¿Notaste que la persona aumentó sus bienes o riquezas de forma que no coincide con su sueldo legítimo? | si_no | r095 | `enriquecimiento_evidente = si` | Aplica para casos de enriquecimiento ilícito | 3 |
| **desvio_contratos** | ¿El acto consistió en desviar dinero público, otorgar contratos, licencias o usar información privilegiada? | si_no | r094, r097, r103 | `desvio_contratos = si` | Distingue entre peculado, distracción de recursos o ejercicio abusivo de funciones | 8 |

## Se llevaron a una persona o no aparece (`privacion_libertad`, penal) · 48 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **estado_victima** | ¿Cuál es la situación actual de la persona? | opcion: sigue_desaparecida, fue_liberada_o_aparecio, fallecio | r029, r030, r031, r034 | `estado_victima = fallecio` | Diferencia entre desaparición, secuestro consumado o privación con resultado de muerte | 5 |
| **duracion_privacion** | ¿Cuánto tiempo estuvo o está la persona privada de su libertad? | opcion: menos_de_24_horas, mas_de_24_horas, no_se_sabe | r029, r030, r032 | `duracion_privacion = menos_de_24_horas` | Determina agravantes o atenuantes según el tiempo de cautiverio | 7 |
| **proposito_privacion** | Además de pedir dinero, ¿sabes si tenían algún otro objetivo? (por ejemplo: fines sexuales, obligar a hacer algo, tráfico de órganos o mendicidad) | opcion: sexual, daño_perjuicio, trafico_mendicidad, ninguno_otro | r030, r032, r033 | `proposito_privacion = sexual` | Clasifica el tipo de secuestro o sustracción de menores | 6 |
| **custodia_legal** | ¿La persona que se llevó al menor tiene algún derecho legal sobre él, como la patria potestad, tutela o custodia? | si_no | r032, r033 | `custodia_legal = no` | Determina si es sustracción ilícita o un conflicto de custodia | 6 |
| **circunstancias_hecho** | ¿Cómo ocurrió el hecho? (por ejemplo: si fueron varias personas, si fue en transporte público o si entraron a una casa) | opcion: grupo, transporte_publico, allanamiento_domicilio, lugar_solitario, ninguna | r029, r030 | `circunstancias_hecho = grupo` | Identifica agravantes por modo de ejecución | 5 |
| **rol_especifico_servidor** | ¿El servidor público que lo hizo trabaja específicamente en una cárcel, centro de detención o se encarga de investigar delitos? | si_no | r034 | `rol_especifico_servidor = si` | Aplica la regla de desaparición forzada por servidor público con atribuciones específicas | 2 |

## Agresión sexual (`agresion_sexual`, penal) · 45 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **hubo_penetración** | ¿Hubo penetración o introducción de algún objeto o parte del cuerpo (por vía vaginal, anal o bucal)? | si_no | r012, r013 | `hubo_penetración = si` | Diferencia entre violación y abuso sexual | 6 |
| **capacidad_resistencia** | ¿La persona estaba en condiciones de resistirse o comprender lo que pasaba (por ejemplo, estaba dormida, drogada, alcoholizada o tiene alguna discapacidad)? | si_no | r013, r014, r016 | `capacidad_resistencia = no` | Determina si la falta de consentimiento es por incapacidad de comprender o resistir | 12 |
| **engaño_seduccion** | ¿El consentimiento se obtuvo mediante mentiras, engaños o promesas (seducción)? | si_no | r014 | `engaño_seduccion = si` | Identifica si el delito es estupro | 4 |
| **parentesco_directo** | ¿El agresor es padre, madre, hijo, hija o hermano/a de la víctima? | si_no | r015 | `parentesco_directo = si` | Determina si aplica la regla de incesto | 4 |
| **num_agresores** | ¿Cuántas personas participaron en la agresión? | numero | r012, r013 | `num_agresores > 1` | Identifica agravantes por número de participantes | 7 |
| **privacion_libertad** | ¿A la persona la obligaron a ir a otro lugar o le impidieron salir para cometer el acto? | si_no | r017 | `privacion_libertad = si` | Determina si hubo privación de la libertad con fines sexuales | 1 |

## Accidente o choque de tránsito (`transito`, penal) · 39 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **estado_conductor** | ¿El conductor estaba bajo los efectos del alcohol, drogas o usando el celular al momento del accidente? | opcion: sobrio, alcohol_drogas, celular | r050, r051, r052 | `estado_conductor = alcohol_drogas` | Determina si hay agravantes por estado de ebriedad o distracción | 6 |
| **tipo_vehiculo** | ¿El vehículo involucrado era de servicio público, escolar o particular? | opcion: particular, servicio_publico, escolar | r050, r051, r052, r053 | `tipo_vehiculo = servicio_publico` | Define si aplica la normativa de transporte público o escolar | 8 |
| **accion_post_accidente** | ¿Se brindó auxilio a los lesionados o el conductor se dio a la fuga? | opcion: auxilio, fuga, no_hubo_lesionados | r050, r052 | `accion_post_accidente = fuga` | Identifica el delito de omisión de auxilio o abandono de persona | 5 |
| **metodo_daño** | ¿El daño fue por un choque común o se usaron explosivos, fuego o se bloquearon las vías? | opcion: choque_simple, explosivos_fuego, obstruccion_via | r052, r053 | `metodo_daño = explosivos_fuego` | Diferencia entre un accidente culposo y un ataque a las vías de comunicación | 7 |
| **ocupado_personas** | ¿El vehículo o la vía afectada estaban ocupados por personas en ese momento? | si_no | r050, r053 | `ocupado_personas = si` | Aumenta la gravedad del delito en ataques a transportes o vías | 4 |

## Mi casa, terreno o propiedad (`propiedad`, penal) · 36 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **tipo_propiedad** | ¿Qué tipo de propiedad es? | opcion: casa o domicilio particular, local, despacho o negocio, terreno ejidal o comunal, área natural protegida, bien público o equipamiento urbano, otro | r046, r047, r048 | `tipo_propiedad = 'terreno ejidal o comunal'` | Determina si es allanamiento de morada, despojo de tierras ejidales o daño a bienes públicos | 8 |
| **medio_daño_entrada** | ¿Cómo ocurrió el daño o la entrada a la propiedad? | opcion: incendio, inundación o explosión, engaño o entró a escondidas, uso de drones, otro | r047, r048 | `medio_daño_entrada = 'incendio, inundación o explosión'` | Identifica agravantes en daño a la propiedad o la modalidad del allanamiento | 7 |
| **num_personas_involucradas** | ¿Cuántas personas participaron en los hechos? | numero | r046, r048 | `num_personas_involucradas > 1` | El número de personas es un agravante tanto en despojo como en allanamiento | 5 |
| **condicion_victima** | ¿La persona afectada tiene alguna de estas condiciones: discapacidad, es mujer embarazada o persona indígena? | opcion: discapacidad, embarazo, indígena, ninguna | r046, r048 | `condicion_victima = 'discapacidad'` | Aplica agravantes específicos para víctimas vulnerables en despojo y allanamiento | 5 |
| **estatus_legal_propiedad** | ¿La propiedad tiene algún problema legal, como estar en juicio, ser un terreno sin permisos de lotificación o estar desocupada? | opcion: está en juicio o litigio, falta de permisos para lotificar/dividir, estaba desocupada o en venta, se alteraron los límites o linderos, ninguna | r046 | `estatus_legal_propiedad = 'está en juicio o litigio'` | Define la tipicidad del despojo y conflictos administrativos de urbanización | 8 |
| **rol_construccion** | En caso de ser un problema de construcción, ¿cuál era su papel? | opcion: director responsable de obra (DRO), corresponsable, dueño, constructor | r049 | `rol_construccion = 'director responsable de obra (DRO)'` | Determina la responsabilidad penal según el rol en la obra | 1 |

## Abuso de la policía o de una autoridad (`abuso_autoridad`, penal) · 31 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **rol_especifico_autoridad** | ¿La persona es policía, agente de migración, aduana, o algún cargo electo (como diputado o regidor)? | opcion: policia, migracion_aduana, cargo_electo, otro_servidor | r058, r059 | `rol_especifico_autoridad = 'policia'` | Determina si aplica el uso ilegal de la fuerza pública o delitos específicos de legisladores | 5 |
| **fin_intimidacion** | ¿Lo hicieron para obligarte a confesar algo, para que no denunciaras o como castigo por haber denunciado? | si_no | r060, r061 | `fin_intimidacion = si` | Diferencia entre abuso general, intimidación y tortura | 7 |
| **concepto_pago** | ¿Te pidieron el dinero diciendo que era un impuesto, una multa, un trámite oficial o un pago obligatorio? | si_no | r062, r063 | `concepto_pago = si` | Distingue entre cohecho (soborno) y concusión (exigencia ilegal de impuesto/pago) | 4 |
| **negacion_servicio** | ¿La autoridad se negó a darte un servicio, ignoró tu petición o retrasó el trámite a propósito? | si_no | r064 | `negacion_servicio = si` | Identifica la negación o retardación del servicio público | 3 |
| **victima_servidor_publico** | ¿Usted también es servidor público o trabaja en el gobierno? | si_no | r058, r061 | `victima_servidor_publico = si` | Verifica si la víctima tiene calidad de servidor público para agravantes o reglas específicas | 1 |

## Amenazas, extorsión o cobros (`amenazas_extorsion`, penal) · 22 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **es_por_deuda** | ¿El dinero que te piden es para pagar una deuda? | si_no | r027, r028 | `es_por_deuda = si` | Diferencia entre extorsión y cobranza ilegítima, y detecta si es deuda federal | 4 |
| **perfil_victima_especial** | ¿Alguna de estas opciones describe tu situación: eres comerciante o transportista, tienes alguna discapacidad, o eres testigo o víctima en otro proceso penal? | opcion: comerciante_transportista, discapacidad, testigo_victima_penal, ninguna | r026, r027 | `perfil_victima_especial = comerciante_transportista` | Determina agravantes basadas en la ocupación o vulnerabilidad de la víctima | 4 |
| **agresor_especial** | ¿El agresor es parte de un grupo criminal, hay más de una persona involucrada, o te contactaron desde una cárcel? | opcion: delincuencia_organizada, varias_personas, desde_carcel, ninguna | r027 | `agresor_especial = delincuencia_organizada` | Identifica agravantes por la naturaleza del agresor o el lugar desde donde opera | 2 |
| **medio_fisico_publico** | ¿La amenaza fue mediante mantas, cartulinas, lonas o algún papel pegado en la calle o tu casa? | si_no | r026, r027 | `medio_fisico_publico = si` | Detecta modalidades específicas de amenaza física pública | 1 |
| **peligro_real_o_cumplido** | ¿Sientes que tu vida o salud están en peligro real, o la amenaza ya se llevó a cabo? | si_no | r026, r027 | `peligro_real_o_cumplido = si` | Evalúa la gravedad del riesgo y si el delito ya se consumó | 2 |

## Fotos, videos o mensajes íntimos (`imagenes_intimas`, penal) · 16 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **consentimiento_difusion** (existente: `consentimiento_difusion`) | ¿La persona estuvo de acuerdo en que se compartieran o publicaran las imágenes? | si_no | r020, r025 | `consentimiento_difusion = no` | Determina si hubo una violación a la intimidad sexual o si fue un acto consentido | 1 |
| **capacidad_cognitiva** | ¿La persona afectada tiene alguna discapacidad mental, cognitiva o alguna condición que le impida comprender lo que pasaba o resistirse? | si_no | r023, r024 | `capacidad_cognitiva = si` | Identifica vulnerabilidad cognitiva que agrava el delito o cambia la tipificación | 6 |
| **fines_lucro** | ¿El material fue guardado o compartido con la intención de venderlo o ganar dinero con él? | si_no | r020, r023, r025 | `fines_lucro = si` | Diferencia entre difusión simple y comercialización de material íntimo/pornográfico | 2 |
| **estado_consciencia** | ¿La persona se encontraba bajo los efectos del alcohol o alguna droga al momento de los hechos? | si_no | r020, r023 | `estado_consciencia = si` | Determina si el consentimiento estaba viciado por el estado de la víctima | 1 |
| **uso_ia** | ¿Se utilizó inteligencia artificial para crear o modificar las imágenes (por ejemplo, poner el rostro de alguien en otro cuerpo)? | si_no | r020, r025 | `uso_ia = si` | Identifica el uso de tecnologías de manipulación digital (deepfakes) | 1 |
| **identidad_confirmada** | ¿La persona que aparece en las imágenes es realmente la víctima o es alguien que se hace pasar por ella? | opcion: es la victima, es otra persona | r020, r025 | `identidad_confirmada = es la victima` | Verifica la identidad del sujeto en el contenido para acreditar la afectación | 1 |

## Acoso u hostigamiento sexual (`acoso_hostigamiento`, penal) · 13 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **conducta_reiterada** | ¿Esto pasó una sola vez o se repitió en varias ocasiones? | opcion: una vez, dos o más veces | r018, r019 | `conducta_reiterada = 'dos o más veces'` | Determina si la conducta es persistente o reiterada para tipificar el acoso | 4 |
| **lugar_publico** | ¿El hecho ocurrió en un lugar público, como la calle, un parque o el transporte público? | si_no | r018 | `lugar_publico = si` | Identifica si el acoso ocurrió en espacios públicos o medios de transporte | 3 |
| **condicion_vulnerabilidad** | ¿La persona tiene alguna discapacidad, está embarazada o hay alguna situación que le impidiera resistirse o comprender lo que pasaba? | si_no | r018, r019 | `condicion_vulnerabilidad = si` | Evalúa la capacidad de resistencia o comprensión y agravantes por vulnerabilidad | 4 |
| **daño_psicoemocional** | ¿Esto causó un daño emocional, miedo o sufrimiento psicológico a la víctima? | si_no | r018, r019 | `daño_psicoemocional = si` | Determina la existencia de perjuicio o daño psicoemocional | 3 |
| **finalidad_coaccion** | ¿La persona buscaba obligar a la víctima a hacer algo o a desistir de un proceso legal? | si_no | r018, r019 | `finalidad_coaccion = si` | Identifica si la conducta tenía como fin la coacción o el control | 1 |

## Me difamaron o revelaron algo privado (`intimidad_honor`, penal) · 13 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **tiene_custodia_legal** | ¿La persona que lo hizo tiene la custodia legal, tutela o la patria potestad de la víctima? | si_no | r054, r055, r056 | `tiene_custodia_legal = si` | Determina si hay una excepción o agravante por el parentesco legal y custodia | 3 |
| **conocido_por_trabajo** | ¿La persona conoció la información o el secreto debido a su trabajo, profesión u oficio? | si_no | r055 | `conocido_por_trabajo = si` | Define si aplica la revelación de secretos profesionales o industriales | 3 |
| **causo_perjuicio** | ¿Esta revelación o acción causó algún daño económico, moral o afectó la reputación de la persona? | si_no | r055 | `causo_perjuicio = si` | Es un requisito para que la revelación de secretos sea punible | 2 |
| **intervencion_comunicacion** | ¿La información fue obtenida interceptando una comunicación privada o la persona trabaja en una empresa de telecomunicaciones o correos? | si_no | r056 | `intervencion_comunicacion = si` | Determina la violación de correspondencia o comunicaciones privadas | 3 |
| **orden_judicial** | ¿Existía alguna orden de un juez que permitiera revisar esa información o comunicación? | si_no | r054, r055, r056 | `orden_judicial = si` | Excluye la responsabilidad penal si hubo un mandato judicial | 1 |

## Discriminación (`discriminacion`, penal) · 13 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **motivo_discriminacion** | ¿Por qué razón considera que fue discriminada? (por ejemplo: edad, sexo, raza, religión, orientación sexual, etc.) | opcion: Edad, Sexo o Género, Raza o Etnia, Religión, Orientación sexual o Identidad de género, Discapacidad, Condición social o económica, Otro | r065 | `motivo_discriminacion = 'Raza o Etnia'` | Determina el motivo del acto discriminatorio para aplicar la regla general | 5 |
| **terapia_conversion** | ¿El objetivo de los procedimientos o acciones era cambiar la orientación sexual o la identidad de género de la persona? | si_no | r066 | `terapia_conversion = si` | Identifica delitos contra el libre desarrollo de la personalidad | 2 |
| **condicion_vulnerabilidad** | ¿La persona afectada tiene alguna discapacidad, está embarazada, es madre o se encuentra en periodo de lactancia? | opcion: Discapacidad, Embarazo/Maternidad/Lactancia, Ninguna | r065 | `condicion_vulnerabilidad = 'Discapacidad'` | Aplica agravantes por condición de vulnerabilidad | 2 |
| **ambito_politico** | ¿La persona es candidata, ocupa un cargo público o el acto ocurrió mientras ejercía sus derechos políticos o electorales? | si_no | r065 | `ambito_politico = si` | Determina si hay agravantes por ejercicio de derechos políticos | 3 |
| **ambito_publico** | ¿El acto ocurrió en un lugar público o en el ámbito público? | si_no | r065 | `ambito_publico = si` | Determina si el acto ocurrió en el ámbito público | 1 |

## Drogas (`drogas`, penal) · 11 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **actividad_droga** | ¿Cuál era la actividad que se realizaba? (por ejemplo: poseer, fabricar, sembrar, cultivar o desviar químicos) | opcion: posesión, fabricación/producción, siembra/cultivo, desvío de químicos/maquinaria, otra | r093 | `actividad_droga = siembra/cultivo` | Determina si aplica la regla de producción, cultivo o desvío de precursores | 3 |
| **finalidad_posesion** | ¿Para qué se tenía la sustancia? (por ejemplo: consumo personal, venta, tratamiento médico o uso ceremonial) | opcion: consumo personal, venta/tráfico, tratamiento médico, uso ceremonial indígena, otra | r093 | `finalidad_posesion = uso ceremonial indígena` | Diferencia entre narcomenudeo, tráfico o excepciones por salud/cultura | 2 |
| **cantidad_sustancia** | ¿Qué cantidad de sustancia se encontró aproximadamente? (indicar en gramos o kilos) | numero | r093 | `cantidad_sustancia > 5` | Define si la cantidad excede los límites del narcomenudeo | 2 |
| **perfil_profesional_lugar** | ¿La persona es profesional de la salud, o el hecho ocurrió en una escuela, hospital, cárcel o estación de policía? | si_no | r093 | `perfil_profesional_lugar = si` | Identifica agravantes por el cargo de la persona o el lugar del hecho | 1 |
| **farmacodependiente** | ¿La persona es dependiente de las drogas o tiene una adicción? | si_no | r093 | `farmacodependiente = si` | Determina si aplica una reducción de pena o tratamiento por farmacodependencia | 1 |
| **antecedentes_penales** | ¿La persona ya había sido condenada anteriormente por un delito? | si_no | r093 | `antecedentes_penales = si` | Evalúa la reincidencia para la aplicación de la pena | 1 |

## Piratería o derechos de autor (`derechos_autor`, penal) · 8 frases

| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |
|---|---|---|---|---|---|---|
| **fines_lucro** | ¿Se realizó la actividad para ganar dinero o obtener algún beneficio económico? | si_no | r124 | `fines_lucro = si` | Determina si hubo fines de lucro o especulación comercial | 6 |
| **sustitucion_autor** | ¿Se cambió el nombre del autor original por el de otra persona? | si_no | r124 | `sustitucion_autor = si` | Determina si hubo sustitución de la autoría de la obra | 1 |
| **venta_publica** | ¿La venta o distribución de los materiales se hizo en la calle, plazas o lugares públicos? | si_no | r124 | `venta_publica = si` | Determina si la explotación ocurrió en vías o lugares públicos | 1 |

