"""
Genera bench_sets/familiar_50.json — benchmark de 50 preguntas de derecho familiar para el tab
🧪 Benchmark (tema derecho_familiar), con la misma metodología que el set penal:

* Respuestas esperadas redactadas desde el TEXTO DEL CORPUS (2026-10-01):
    - CFAMILIAREM.md  Código Familiar para el Estado Libre y Soberano de Morelos (sustantivo)
    - CPROFAMEM.md    Código Procesal Familiar para el Estado de Morelos
    - CNPCF           Código Nacional de Procedimientos Civiles y Familiares
    - Cuadernos de Jurisprudencia de la SCJN (compensación económica, alimentos entre pareja,
      filiación, patria potestad y guarda y custodia)
* Cada pregunta sobre legislación lleva MUST de cita de artículo (uno por código en las
  comparativas); las de jurisprudencia SCJN no (no hay artículo que recuperar).
* Dificultad: facil (artículo/caso concreto) · mediano (definición, clasificación, explicación)
  · dificil (análisis comparado de varias legislaciones/fuentes sobre un mismo tema).

    uv run python apps/rewrite_lab/bench_sets/build_familiar_50.py
"""

import json
from pathlib import Path


def C(kind, text, weight=1):
    return {'kind': kind, 'text': text, 'weight': weight}


M = lambda t, w=1: C('must', t, w)        # noqa: E731
S = lambda t, w=1: C('should', t, w)      # noqa: E731
N = lambda t, w=1: C('must_not', t, w)    # noqa: E731

LEY = {'MF': 'del Código Familiar para el Estado de Morelos',
       'MP': 'del Código Procesal Familiar para el Estado de Morelos',
       'CN': 'del Código Nacional de Procedimientos Civiles y Familiares'}


def cita(art, ley):
    return M(f'Cita el art. {art} {LEY[ley]}')


def cita_alguno(*pares):
    return M('Cita al menos uno de estos artículos: ' + '; '.join(f'art. {a} {LEY[l]}' for a, l in pares))


Q = []


def q(difficulty, question, expected, components, notes=''):
    Q.append({'question': question, 'difficulty': difficulty, 'expected_answer': expected,
              'notes': notes, 'components': components})


# ═══════════════════════════════ FÁCIL (22) ═══════════════════════════════
# Morelos — Código Familiar
q('facil', 'Según el Código Familiar para el Estado de Morelos, ¿de dónde se deriva la obligación de dar alimentos?',
  'Art. 35 del Código Familiar para el Estado de Morelos: la obligación de dar alimentos se deriva del matrimonio, del '
  'concubinato, por adopción, del parentesco, por mandamiento judicial o por disposición de la ley. Además es recíproca: '
  'el que los da tiene a su vez el derecho de pedirlos (art. 34).',
  [M('Matrimonio y concubinato como fuentes', 2), M('Parentesco y adopción como fuentes'),
   M('También por mandamiento judicial o disposición de la ley'), S('Menciona la reciprocidad alimentaria (art. 34)'),
   cita(35, 'MF'), N('Afirma que el concubinato no genera obligación alimentaria')])

q('facil', '¿Qué comprenden los alimentos en el Código Familiar de Morelos y hasta qué edad subsisten si el acreedor estudia?',
  'Art. 43: los alimentos comprenden la casa, la comida, el vestido, la atención médica y psicológica preventiva, la '
  'asistencia en caso de enfermedad, el esparcimiento, los gastos de embarazo y parto, los gastos para la educación básica '
  'y para proporcionar algún oficio, arte o profesión; y, para personas con discapacidad, lo necesario para su '
  'habilitación o rehabilitación. Subsisten pese a la mayoría de edad si el alimentista está incapacitado para trabajar, '
  'y hasta los veinticinco años si estudia, no causa baja y no tiene ingresos propios.',
  [M('Casa, comida, vestido y atención médica', 2), M('Educación y oficio, arte o profesión'),
   M('Subsisten hasta los 25 años si el acreedor estudia (sin causar baja ni tener ingresos propios)', 2),
   S('Incluye esparcimiento y gastos de embarazo y parto'), cita(43, 'MF'),
   N('Afirma que la obligación termina siempre a los 18 años')])

q('facil', '¿En qué casos cesa la obligación de dar alimentos según el Código Familiar de Morelos?',
  'Art. 55: cesa I. mientras el deudor esté en imposibilidad absoluta; II. cuando el acreedor deja de necesitarlos (subsiste '
  'por incapacidad o estudios hasta los 25 años); III. por delito, conducta antisocial o daños graves del acreedor contra el '
  'deudor, o violencia familiar; IV. si la necesidad depende de conducta delictuosa o viciosa del acreedor; V. si el '
  'acreedor abandona sin justificación la casa del deudor; VI. por muerte del acreedor. En los casos III a V la obligación '
  'subsiste hasta los dieciocho años.',
  [M('Imposibilidad absoluta del deudor'), M('El acreedor deja de necesitarlos'), M('Muerte del acreedor alimentario'),
   S('Violencia familiar o delito del acreedor contra el deudor'),
   S('En las fracciones III a V subsiste hasta los 18 años'), cita(55, 'MF')])

q('facil', '¿Qué características tiene el derecho a recibir alimentos en el Código Familiar de Morelos?',
  'Art. 56: no es renunciable ni puede ser objeto de transacción, compensación o convenio que establezca modalidad o '
  'reducción. Art. 57 (reformado en 2024): es imprescriptible, irrenunciable y retroactivo, y puede reclamarse en cualquier '
  'momento por quien lo acredite.',
  [M('Es imprescriptible', 2), M('Es irrenunciable'), M('Es retroactivo'),
   S('No admite transacción ni compensación'), cita_alguno((56, 'MF'), (57, 'MF')),
   N('Afirma que el derecho a alimentos prescribe')])

q('facil', '¿Cómo define el Código Familiar de Morelos el concubinato y cómo se acredita?',
  'Art. 65: es la unión de hecho de dos personas, ambas libres de matrimonio y sin impedimento para contraerlo, que viven '
  'de forma constante y permanente, generando derechos y obligaciones al procrear hijos o mantener la convivencia. Para '
  'acreditarlo, el juez considera que los concubinos hayan vivido en el mismo domicilio de manera ininterrumpida durante '
  'dos años, o que hayan cohabitado y procreado uno o más hijos en común.',
  [M('Unión de hecho de dos personas libres de matrimonio y sin impedimento para contraerlo', 2),
   M('Dos años de vida en común ininterrumpida', 2), M('O cohabitación con uno o más hijos en común'),
   cita(65, 'MF'), N('Afirma que exige cinco años de convivencia'),
   N('Afirma que el concubinato solo puede ser entre un hombre y una mujer')])

q('facil', '¿A qué edad pueden contraer matrimonio los contrayentes en Morelos?',
  'Art. 72 del Código Familiar para el Estado de Morelos: los contrayentes necesitan haber cumplido dieciocho años. La '
  'falta de edad requerida por la ley es un impedimento no dispensable (art. 77, fr. XVI).',
  [M('Dieciocho años', 2), cita(72, 'MF'), S('La falta de edad es impedimento no dispensable (art. 77)'),
   N('Afirma que puede casarse a los 16 años con dispensa o consentimiento de los padres')])

q('facil', '¿Cuáles son los impedimentos dispensables para contraer matrimonio en Morelos?',
  'Art. 78: I. derogada; II. estar inscrito en el Registro Nacional de Obligaciones Alimentarias (el oficial pide el '
  'certificado de no inscripción y, si aun así consienten, se celebra); III. el parentesco colateral desigual, que comprende '
  'sólo a tíos y sobrinos en tercer grado; IV. padecer enfermedad crónica e incurable contagiosa o hereditaria, si ambos '
  'acreditan conocer sus alcances, efectos y prevención y aun así consienten.',
  [M('Parentesco colateral desigual: tíos y sobrinos en tercer grado', 2),
   M('Enfermedad crónica e incurable contagiosa o hereditaria, con conocimiento acreditado de ambos'),
   S('Estar inscrito en el Registro Nacional de Obligaciones Alimentarias'), cita(78, 'MF'),
   N('Afirma que el parentesco por consanguinidad en línea recta es dispensable')])

q('facil', '¿Qué bienes pueden integrar el patrimonio de familia en Morelos y qué protección tienen?',
  'Art. 136: la casa habitación de la familia y los muebles de uso ordinario no suntuarios; un lote de parcela cultivable; '
  'en familias campesinas, semillas, maquinaria, instrumentos y animales para el cultivo; en artesanos, su equipo de '
  'trabajo; en trabajadores del volante, el vehículo de alquiler y su concesión si es su única fuente de ingreso; derechos '
  'de socio en cooperativas y mutualistas; y el equipo de trabajo de quienes prestan servicios independientes. Art. 138: '
  'esos bienes son inalienables y no están sujetos a embargo ni gravamen alguno.',
  [M('La casa habitación y los muebles de uso ordinario no suntuarios'), M('Son inalienables e inembargables', 2),
   S('Incluye parcela cultivable o equipo de trabajo'), cita_alguno((136, 'MF'), (138, 'MF'))])

q('facil', '¿Cuándo puede haber separación de bienes en el matrimonio según el Código Familiar de Morelos?',
  'Art. 116: puede haber separación de bienes en virtud de capitulaciones anteriores al matrimonio, durante éste por '
  'convenio de los consortes o por sentencia judicial; puede comprender los bienes de que sean dueños al casarse y también '
  'los que adquieran después.',
  [M('Por capitulaciones anteriores al matrimonio'), M('Durante el matrimonio por convenio de los consortes'),
   M('Por sentencia judicial'), S('Puede comprender bienes anteriores y posteriores'), cita(116, 'MF')])

q('facil', 'En Morelos, si el matrimonio fue bajo separación de bienes, ¿qué indemnización puede corresponder en el divorcio '
  'al cónyuge que se dedicó al hogar?',
  'Art. 178 del Código Familiar de Morelos: debe señalarse una indemnización, que no podrá ser superior al 50% del valor de '
  'los bienes que se hubieren adquirido, a favor del cónyuge que durante el matrimonio se haya dedicado preponderantemente '
  'al trabajo del hogar y, en su caso, al cuidado de los hijos; el Juez de lo Familiar resuelve según las circunstancias.',
  [M('Hasta el 50% del valor de los bienes adquiridos', 2), M('Aplica al matrimonio bajo separación de bienes'),
   M('A favor del cónyuge dedicado preponderantemente al hogar y al cuidado de los hijos'), cita(178, 'MF'),
   N('Afirma que la indemnización es siempre del 50% exacto de todos los bienes del otro cónyuge')])

q('facil', '¿Qué efecto tiene la reconciliación de los cónyuges en un procedimiento de divorcio en Morelos?',
  'Art. 176 del Código Familiar de Morelos: la reconciliación pone término al procedimiento de divorcio en cualquier estado '
  'en que se encuentre; los interesados deben comunicarla al Juez de lo Familiar. En el divorcio voluntario la '
  'reconciliación es además causa para archivar la solicitud (art. 497 del Código Procesal Familiar).',
  [M('Pone término al procedimiento en cualquier estado en que se encuentre', 2), M('Debe comunicarse al Juez de lo Familiar'),
   cita(176, 'MF')])

# CNPCF
q('facil', 'Conforme al Código Nacional de Procedimientos Civiles y Familiares, cuando se acredita la obligación alimentaria, '
  '¿cuándo debe dictarse el auto admisorio y qué se ordena?',
  'Art. 562 CNPCF: el auto admisorio se dicta a más tardar al día siguiente de recibida la solicitud, fijando una pensión '
  'alimenticia provisional y dando aviso sin demora a la persona física o moral de quien perciba ingresos el deudor para que '
  'haga el descuento, lo entregue al acreedor e informe sus percepciones. La fuente de trabajo debe atenderlo de inmediato e '
  'informar en tres días, so pena de multa de hasta 200 UMA y responsabilidad solidaria (art. 563).',
  [M('A más tardar al día siguiente de recibida la solicitud', 2), M('Se fija una pensión alimenticia provisional'),
   M('Se ordena el descuento a quien paga los ingresos del deudor'), S('Multa de hasta 200 UMA a la fuente de trabajo que no cumpla'),
   cita(562, 'CN')])

q('facil', 'Si no se acredita la capacidad económica del deudor alimentario, ¿cómo se fija la pensión según el CNPCF?',
  'Art. 564 CNPCF: la pensión se fija en salarios mínimos de la zona económica que corresponda, sin que pueda ser inferior a uno.',
  [M('Se fija en salarios mínimos de la zona económica', 2), M('No puede ser inferior a un salario mínimo'), cita(564, 'CN'),
   N('Afirma que sin acreditar ingresos no puede fijarse pensión')])

q('facil', '¿Cuándo debe inscribirse al deudor alimentario en el Registro Nacional de Obligaciones Alimentarias según el CNPCF?',
  'Art. 565 CNPCF: cuando el incumplimiento total o parcial del deudor dure más de 90 días, el juez ordena su inscripción; la '
  'Procuraduría de Protección de Niñas, Niños y Adolescentes con tutoría a su favor está legitimada para pedirla. Además, '
  'si tras la sentencia hay incumplimiento, el juez lo informa al Registro en tres días (art. 568).',
  [M('Incumplimiento total o parcial por más de 90 días', 2), cita(565, 'CN'),
   S('La Procuraduría de Protección de NNA puede solicitar la inscripción'), S('Tras la sentencia, se informa en tres días (art. 568)')])

q('facil', '¿En qué plazos deben dictarse y cumplirse las medidas u órdenes de protección según el CNPCF?',
  'Art. 575 CNPCF: deben dictarse dentro de las veinticuatro horas siguientes al conocimiento de los hechos y cumplimentarse '
  'en un término no mayor a setenta y dos horas, sin necesidad de que surta efectos notificación alguna; pueden modificarse '
  'durante el juicio, en la audiencia preliminar o en la sentencia, y el juez debe darles seguimiento.',
  [M('Se dictan dentro de las 24 horas', 2), M('Se cumplen en no más de 72 horas', 2),
   S('No requieren que surta efectos una notificación'), cita(575, 'CN')])

q('facil', '¿Qué medidas provisionales debe decretar de oficio la autoridad jurisdiccional en materia familiar según el CNPCF?',
  'Art. 569 CNPCF: debe intervenir de oficio y decretar, sin audiencia de la contraparte, las medidas provisionales necesarias '
  'de manera enunciativa: I. fijación de alimentos; II. guarda y custodia; III. régimen de convivencias; IV. órdenes o '
  'medidas de protección; V. cualquier otra para salvaguardar a la familia. Se revisan en la audiencia preliminar y contra '
  'la resolución procede apelación en efecto devolutivo.',
  [M('Alimentos, guarda y custodia y régimen de convivencias', 2), M('Órdenes o medidas de protección'),
   M('Se decretan sin audiencia de la contraparte'), S('Apelación en efecto devolutivo'), cita(569, 'CN')])

q('facil', '¿Cuándo procede el divorcio ante el Registro Civil conforme al CNPCF?',
  'Art. 662 CNPCF: cuando ambos cónyuges convengan en divorciarse, no tengan bienes o deudas del patrimonio conyugal, y no '
  'tengan hijos en común o, teniéndolos, sean mayores de edad y no requieran alimentos. El oficial, previa identificación y '
  'ratificación, levanta el acta de divorcio y anota el acta de matrimonio.',
  [M('Ambos cónyuges convienen en divorciarse'), M('No tienen bienes ni deudas del patrimonio conyugal', 2),
   M('Sin hijos en común, o mayores de edad que no requieran alimentos', 2), cita(662, 'CN')])

q('facil', 'En el divorcio bilateral ante la autoridad judicial previsto por el CNPCF, ¿qué debe acompañarse a la solicitud y '
  'cómo se resuelve?',
  'Arts. 656 y 657 CNPCF: se acompaña copia certificada del acta de matrimonio, las actas de nacimiento de hijos menores y '
  'una propuesta de convenio (guarda y custodia, alimentos y convivencias de los hijos, pensión para el o la divorciante y '
  'distribución de bienes según el régimen). Con vista al MP si hay derechos de NNA, se cita en diez días a una única '
  'audiencia; aprobado el convenio se dicta sentencia oral que, si disuelve el vínculo, es irrecurrible y causa ejecutoria.',
  [M('Acta de matrimonio, actas de nacimiento de hijos menores y propuesta de convenio', 2),
   M('Única audiencia dentro de los diez días siguientes'), M('Sentencia oral irrecurrible que causa ejecutoria'),
   cita_alguno((656, 'CN'), (657, 'CN'))])

q('facil', 'En la restitución nacional de niñas, niños y adolescentes del CNPCF, ¿qué autoridad es competente, en qué plazo '
  'debe proveer y quién puede solicitarla?',
  'Art. 630 CNPCF: es competente la autoridad del lugar de residencia habitual del menor, salvo procedimiento previo de '
  'custodia o patria potestad ante otra; recibida la solicitud tiene un plazo máximo de tres días para proveer. Art. 631: '
  'pueden solicitarla la madre, el padre o la persona o institución que tenga la custodia, salvo progenitores condenados '
  'por violencia sexual contra NNA o feminicidio.',
  [M('Autoridad del lugar de residencia habitual del menor', 2), M('Plazo máximo de tres días para proveer'),
   S('Legitimados: madre, padre o quien tenga la custodia'), cita(630, 'CN')])

q('facil', '¿En qué fases se divide la audiencia preliminar del juicio oral familiar en el CNPCF?',
  'Art. 671 CNPCF: en dos fases que se celebran el mismo día y de manera consecutiva: I. la junta anticipada, ante la persona '
  'secretaria judicial, no videograbada (queda acta mínima), y II. la audiencia ante la autoridad jurisdiccional. La junta '
  'anticipada sirve para intercambiar información y pruebas, proponer convenios, acordar hechos no controvertidos y '
  'proponer acuerdos probatorios (art. 672).',
  [M('Junta anticipada ante la persona secretaria judicial, no videograbada', 2), M('Audiencia ante la autoridad jurisdiccional'),
   M('Se celebran el mismo día y de manera consecutiva'), S('Objetivos de la junta anticipada (art. 672)'), cita(671, 'CN')])

# Morelos — Código Procesal Familiar
q('facil', 'Según el Código Procesal Familiar de Morelos, ¿en qué plazo debe el marido contradecir que un hijo nacido en el '
  'matrimonio es suyo? ¿Y cuándo puede demandarse el reconocimiento de paternidad?',
  'Art. 447 del Código Procesal Familiar para el Estado de Morelos: el marido debe deducir su pretensión dentro de sesenta '
  'días contados desde el nacimiento si estaba presente, desde que llegó al lugar si estaba ausente, o desde que descubrió el '
  'fraude si se le ocultó el nacimiento. Art. 449: la demanda de reconocimiento de paternidad y maternidad puede interponerse '
  'en cualquier tiempo.',
  [M('Sesenta días', 2), M('Desde el nacimiento, desde su llegada o desde que descubrió el fraude'),
   M('El reconocimiento de paternidad puede demandarse en cualquier tiempo (art. 449)'), cita(447, 'MP')])

q('facil', 'En el divorcio voluntario regulado por el Código Procesal Familiar de Morelos, ¿pueden los cónyuges comparecer '
  'por medio de apoderado?',
  'No. Art. 491 del Código Procesal Familiar de Morelos: a todos los actos del divorcio voluntario los consortes deben '
  'comparecer personalmente, sin representantes ni mandatarios. La audiencia de divorcio debe fijarse en un plazo máximo de '
  'quince días (art. 492).',
  [M('No: deben comparecer personalmente', 2), cita(491, 'MP'), S('Audiencia dentro de un plazo máximo de 15 días (art. 492)'),
   N('Afirma que pueden comparecer mediante apoderado o mandatario')])

# ═══════════════════════════════ MEDIANO (16) ═══════════════════════════════
q('mediano', 'Clasifica los impedimentos para contraer matrimonio en el Código Familiar de Morelos y explica la diferencia '
  'entre ellos.',
  'Art. 75: impedimento es todo hecho que legalmente prohíbe celebrar el matrimonio. Art. 76: hay dispensables (prohíben '
  'casarse, pero si se celebra el matrimonio es convalidable) y no dispensables (prohíben gravemente e impiden su validez). '
  'No dispensables (art. 77): incapacidad permanente, parentesco consanguíneo en línea recta sin límite, colateral igual, '
  'afinidad en línea recta, homicidio o atentado contra un cónyuge para casarse con el otro, error, tutor–pupila, '
  'adoptante–adoptado, violencia familiar, embriaguez habitual o drogas, enfermedad mental incurable, falta de edad y '
  'matrimonio subsistente. Dispensables (art. 78): tíos y sobrinos, enfermedad crónica contagiosa o hereditaria con '
  'conocimiento, e inscripción en el Registro Nacional de Obligaciones Alimentarias.',
  [M('Dispensables: el matrimonio celebrado puede convalidarse', 2), M('No dispensables: impiden la validez del matrimonio', 2),
   M('Ejemplo de no dispensable (consanguinidad en línea recta, matrimonio subsistente o falta de edad)'),
   M('Ejemplo de dispensable (tíos y sobrinos o enfermedad crónica con conocimiento)'), cita(76, 'MF')])

q('mediano', '¿Cómo se miden los grados y las líneas de parentesco según el Código Familiar de Morelos?',
  'Arts. 29 y 30: cada generación forma un grado y la serie de grados constituye la línea de parentesco. La línea es recta '
  'o transversal: la recta es la serie de grados entre personas que descienden unas de otras; la transversal, la serie de '
  'grados entre personas que, sin descender unas de otras, proceden de un progenitor o tronco común.',
  [M('Cada generación forma un grado', 2), M('Línea recta: personas que descienden unas de otras'),
   M('Línea transversal: proceden de un tronco común sin descender unas de otras'), cita_alguno((29, 'MF'), (30, 'MF'))])

q('mediano', '¿Qué son las capitulaciones matrimoniales y qué regímenes patrimoniales prevé el Código Familiar de Morelos?',
  'Art. 101: las capitulaciones matrimoniales son los pactos que los cónyuges celebran respecto de los bienes que aportan al '
  'matrimonio y los que adquieran con motivo de éste o durante su vigencia. El código regula la sociedad conyugal (cap. VII) '
  'y la separación de bienes (cap. VIII, art. 116), que puede pactarse antes, convenirse durante el matrimonio o decretarse '
  'judicialmente.',
  [M('Pactos de los cónyuges sobre los bienes que aportan o adquieren', 2), M('Sociedad conyugal'), M('Separación de bienes'),
   cita(101, 'MF')])

q('mediano', 'Explica los principios básicos de las órdenes de protección en el Código Nacional de Procedimientos Civiles y '
  'Familiares.',
  'Art. 571 CNPCF: las órdenes de protección buscan salvaguardar integralmente a las víctimas de violencia y su familia, '
  'previniendo, interrumpiendo o impidiendo la violencia. Sus principios incluyen: protección de la víctima (recuperar la '
  'sensación de seguridad y romper el círculo de violencia), urgencia (implementarse de inmediato), accesibilidad '
  '(procedimiento sencillo y gratuito) y utilidad procesal (facilitar la integración y conservación de pruebas).',
  [M('Protección de la víctima'), M('Urgencia'), M('Accesibilidad: procedimiento sencillo y gratuito'),
   S('Utilidad procesal'), cita(571, 'CN')])

q('mediano', '¿En qué consiste el procedimiento de justicia restaurativa en materia familiar del CNPCF y en qué casos no '
  'procede?',
  'Art. 584 CNPCF: las partes de común acuerdo pueden sujetarse a él para reconocer el conflicto, asumir su responsabilidad y '
  'participar en la reparación del daño y la reestructuración de la dinámica familiar. Se exceptúan los casos de violencia '
  'sexual contra niñas, niños y adolescentes; no es obligatorio; el juicio puede suspenderse hasta tres meses manteniéndose '
  'las medidas cautelares. Se auxilia de facilitadores certificados (art. 585) y nunca puede pactarse la renuncia de '
  'derechos de NNA (art. 586).',
  [M('Voluntario y de común acuerdo; no es obligatorio'), M('Finalidad: reconocer el conflicto, responsabilizarse y reparar el daño'),
   M('Se exceptúan los casos de violencia sexual contra niñas, niños y adolescentes', 2),
   S('Suspensión del juicio por no más de tres meses'), cita(584, 'CN'),
   N('Afirma que la justicia restaurativa es obligatoria antes de acudir a juicio')])

q('mediano', '¿Cómo debe escucharse a niñas, niños y adolescentes en los juicios familiares según el CNPCF?',
  'Art. 558 CNPCF: pueden ser escuchados en audiencia videograbada; la comparecencia no debe celebrarse en ambiente hostil y '
  'debe estar presente un equipo interdisciplinario: un profesional en psicología (de preferencia en desarrollo infantil), '
  'el Ministerio Público y una persona tutora especial del DIF. Art. 557: el juez debe atender el interés superior y valorar '
  'la necesidad de su testimonio con base en el principio de mínima intervención.',
  [M('Audiencia videograbada'), M('Equipo interdisciplinario con profesional en psicología', 2), M('Presencia del Ministerio Público'),
   S('Ambiente no hostil y principio de mínima intervención'), cita(558, 'CN')])

q('mediano', '¿Qué debe hacer la autoridad jurisdiccional familiar si advierte violencia respecto de las convivencias o la '
  'guarda y custodia, según el CNPCF?',
  'Art. 561 CNPCF: debe modificar o suspender el régimen de convivencias o la guarda y custodia y puede ordenar convivencias '
  'supervisadas en centros del Poder Judicial o por videoconferencia supervisada si es deseo del niño, niña o adolescente; '
  'dicta medidas para salvaguardar el orden familiar y da vista al Ministerio Público. Además, no puede convocar a '
  'conciliación cuando hay violencia (art. 560, fr. I).',
  [M('Modificar o suspender convivencias o guarda y custodia', 2), M('Convivencias supervisadas (centros o videoconferencia)'),
   M('Dar vista al Ministerio Público'), S('No procede conciliación en casos de violencia (art. 560)'), cita(561, 'CN')])

q('mediano', '¿Qué es la violencia vicaria y qué obligación impone al juez familiar el CNPCF?',
  'Art. 554 CNPCF: es la violencia ejercida contra las mujeres a través de sus hijos. Ante conductas violentas u omisiones '
  'graves en la familia, el juez debe adoptar las medidas provisionales para que cesen de plano y, en violencia vicaria, '
  'salvaguardar la integridad de niñas, niños, adolescentes y mujeres para evitar la violencia institucional prevista en la '
  'Ley General de Acceso de las Mujeres a una Vida Libre de Violencia.',
  [M('Violencia contra las mujeres ejercida a través de sus hijos', 2),
   M('Salvaguardar la integridad de niñas, niños, adolescentes y mujeres'), S('Evitar la violencia institucional'),
   cita(554, 'CN')])

q('mediano', '¿Cómo concreta el CNPCF el principio de interés superior de la infancia en los trámites familiares?',
  'Art. 557 CNPCF: el juez provee de inmediato los ajustes razonables y debe, entre otras cosas: I. actuar más allá de la '
  'demanda puntual cuando sea en aras del interés superior; II. priorizar la protección especial contra todo sufrimiento, '
  'abuso o descuido y el desarrollo en ambiente libre de violencia; III. atender las características y necesidades de cada '
  'menor sin discriminación; IV. cerciorarse de la necesidad de su testimonio con base en el principio de mínima intervención.',
  [M('Actuar más allá de la demanda puntual', 2), M('Priorizar la protección contra sufrimiento, abuso o descuido'),
   S('Mínima intervención en el testimonio de NNA'), cita(557, 'CN')])

q('mediano', '¿Qué es la compensación económica en el divorcio y cuál es su finalidad según la jurisprudencia de la SCJN?',
  'Según los Cuadernos de Jurisprudencia de la SCJN, es la asignación de hasta el 50% de los bienes adquiridos durante el '
  'matrimonio celebrado bajo separación de bienes, a favor del cónyuge que se dedicó preponderantemente al trabajo del hogar '
  'y al cuidado de los hijos. Busca componer el desequilibrio patrimonial de quien, por esa dedicación, no pudo crear un '
  'patrimonio propio; es reparadora y no sancionatoria, opera solo sobre bienes adquiridos durante el matrimonio, la carga '
  'de la prueba es del solicitante y no depende de que haya un cónyuge culpable (procede en el divorcio sin expresión de causa).',
  [M('Hasta el 50% de los bienes adquiridos durante el matrimonio', 2), M('A favor del cónyuge dedicado al hogar y al cuidado de los hijos'),
   M('Finalidad: componer el desequilibrio patrimonial'), S('Es reparadora, no sancionatoria'),
   S('No depende de la culpabilidad (procede en divorcio sin expresión de causa)'),
   N('Afirma que solo procede si hay un cónyuge culpable')])

q('mediano', 'Según la SCJN, ¿qué diferencia hay entre los alimentos entre cónyuges y la pensión compensatoria?',
  'Los alimentos entre cónyuges (y concubinos) derivan de los deberes de solidaridad y asistencia mutuos y se mantienen aun '
  'en la separación; al disolverse el matrimonio esa obligación termina y puede surgir una pensión compensatoria, de '
  'naturaleza distinta: asistencial y resarcitoria, derivada del desequilibrio económico que la disolución provoca. Su '
  'presupuesto es que la disolución coloque a un cónyuge en desventaja económica que afecte su capacidad de sufragar sus '
  'necesidades.',
  [M('Los alimentos entre cónyuges se basan en la solidaridad y asistencia mutuas', 2),
   M('Al disolverse el matrimonio puede surgir la pensión compensatoria, de naturaleza distinta'),
   M('La pensión compensatoria es asistencial y resarcitoria por el desequilibrio económico', 2),
   N('Afirma que la pensión compensatoria es una sanción al cónyuge culpable')])

q('mediano', 'Según la SCJN, ¿qué consecuencia tiene que el presunto progenitor se niegue a practicarse la prueba genética '
  'en un juicio de paternidad?',
  'La Primera Sala ha sostenido que, para no dejar el interés superior del menor a merced de la voluntad del presunto '
  'progenitor y proteger su derecho a conocer su identidad, ante la negativa a practicarse la prueba genética opera la '
  'presunción de la filiación. Esa presunción es una medida de protección reforzada acorde con el interés superior de la '
  'infancia.',
  [M('Opera la presunción de la filiación (paternidad)', 2), M('Protege el derecho del menor a conocer su identidad'),
   S('Es una medida de protección reforzada acorde con el interés superior'),
   N('Afirma que la negativa no tiene consecuencias o que obliga a desechar la demanda')])

q('mediano', '¿Tiene la madre un derecho preferente a la guarda y custodia de los hijos según la SCJN?',
  'No. La SCJN ha sostenido que la preferencia materna no es un derecho, que la presunción de idoneidad de la madre no es '
  'absoluta, que las presunciones legales de preferencia materna deben interpretarse libres de estereotipos y ha declarado '
  'inconstitucional la presunción legal de preferencia materna (AR 331/2019). La guarda y custodia se decide conforme al '
  'interés superior del menor en cada caso.',
  [M('No: la preferencia materna no es un derecho ni una presunción absoluta', 2),
   M('Se decide conforme al interés superior del menor'), S('Debe evitarse resolver con estereotipos de género'),
   N('Afirma que la madre tiene siempre derecho preferente a la custodia de los hijos pequeños')])

q('mediano', 'Según la SCJN, ¿cómo deben valorarse las pruebas para acreditar un concubinato en un juicio de alimentos?',
  'Con perspectiva de género y sin estereotipos: la Corte consideró inconstitucional valorar las relaciones no '
  'matrimoniales con el prejuicio de que son efímeras, pasajeras o sin seriedad, y sostuvo que, con base en el acceso a la '
  'justicia y la igualdad, las pruebas deben analizarse en conjunto.',
  [M('Con perspectiva de género, sin estereotipos', 2), M('Las pruebas se valoran en conjunto'),
   S('Rechaza el prejuicio de que las relaciones no matrimoniales son efímeras')])

q('mediano', 'Según la SCJN, ¿por cuánto tiempo subsiste el derecho a alimentos al terminar un concubinato y qué factores '
  'se consideran?',
  'Cuando la ley no regula expresamente el caso, se aplican las reglas generales de alimentos y las del divorcio: necesidades '
  'del acreedor, posibilidades del deudor, capacidad para trabajar y situación económica de los concubinos. El derecho '
  'subsiste por el tiempo que duró el concubinato y en tanto el acreedor no contraiga nupcias o se una en concubinato con '
  'otra persona. La Corte también consideró inconstitucional fijar un plazo de un año para ejercer la acción por la '
  'imprescriptibilidad e irrenunciabilidad de los alimentos.',
  [M('Subsiste por el tiempo que duró el concubinato', 2), M('Mientras el acreedor no se case ni se una en otro concubinato'),
   M('Necesidades del acreedor y posibilidades del deudor'), S('Capacidad para trabajar y situación económica')])

q('mediano', '¿Qué deberes tienen los padres para con sus hijos según el Código Familiar de Morelos?',
  'Art. 181: las facultades que la ley les atribuye se confieren para que cumplan los deberes de la paternidad y la '
  'maternidad, entre ellos proporcionar: un ambiente familiar y social propicio para su desarrollo; educación; una conducta '
  'positiva y ejemplar; alimentos; una familia estable y solidaria; dirección y orientación acordes con la evolución de sus '
  'facultades sin restringir sus derechos; y un entorno afectivo, comprensivo y sin violencia.',
  [M('Ambiente familiar propicio y familia estable', 2), M('Educación y alimentos'), M('Entorno afectivo y sin violencia'),
   S('Orientación sin restringir sus derechos'), cita(181, 'MF')])

# ═══════════════════════════════ DIFÍCIL (12) ═══════════════════════════════
q('dificil', 'Compara el divorcio voluntario del Código Procesal Familiar de Morelos con el divorcio bilateral del Código '
  'Nacional de Procedimientos Civiles y Familiares.',
  'Morelos (arts. 491–497 del Código Procesal Familiar): los cónyuges deben comparecer personalmente; la audiencia se fija '
  'en un plazo máximo de quince días; hay junta de avenencia en la que el juez, ante el Ministerio Público, los exhorta a '
  'reconciliarse; juez y MP revisan el convenio y proponen modificaciones; el MP puede oponerse si no se aceptan; la '
  'solicitud caduca si pasan más de tres meses sin impulso o si no asisten a la junta. CNPCF (arts. 655–662): puede '
  'tramitarse ante el juez, ante notario (sin hijos menores ni bienes) o ante el Registro Civil (sin bienes ni hijos que '
  'requieran alimentos); ante el juez hay una única audiencia en diez días con sentencia oral irrecurrible; si alguien falta, '
  'se reprograma una sola vez.',
  [M('Morelos: junta de avenencia con exhorto a la reconciliación ante el Ministerio Público', 2),
   M('Morelos: comparecencia personal obligatoria'), M('CNPCF: puede tramitarse ante juez, notario o Registro Civil', 2),
   M('CNPCF: única audiencia con sentencia oral irrecurrible'), cita(493, 'MP'), cita_alguno((655, 'CN'), (657, 'CN')),
   S('Morelos: caducidad por tres meses de inactividad'),
   N('Afirma que el CNPCF también exige una junta de avenencia para reconciliar')])

q('dificil', 'Compara la separación de personas como acto previo en el Código Procesal Familiar de Morelos y en el CNPCF, '
  'en especial respecto de la custodia de los hijos menores.',
  'Morelos (arts. 207–212): la puede pedir quien intente demandar divorcio o nulidad, o denunciar o querellarse contra su '
  'cónyuge o concubino; en urgencia el juez decreta con premura el depósito o separación y los alimentos; a falta de convenio '
  'y si no hay riesgo, deja a la madre el cuidado de los hijos menores de siete años y fija visitas. CNPCF (arts. 578–581): '
  'la puede pedir quien intente demandar, denunciar o querellarse; si por violencia hay imposibilidad, cualquier persona puede '
  'solicitarla bajo protesta; al admitirla el juez decreta órdenes de protección, guarda y custodia provisional, alimentos y '
  'convivencias provisionales, sin presunción a favor de la madre.',
  [M('Morelos: a falta de convenio, la madre conserva el cuidado de los menores de siete años', 2),
   M('CNPCF: el juez decide la guarda y custodia provisional junto con alimentos y convivencias', 2),
   M('CNPCF: cualquier persona puede solicitarla si la violencia impide hacerlo a la interesada'),
   cita(212, 'MP'), cita_alguno((580, 'CN'), (581, 'CN')),
   N('Afirma que el CNPCF otorga la custodia a la madre de los menores de siete años')])

q('dificil', 'Compara cómo se regulan las pruebas científicas o biológicas en el Código Procesal Familiar de Morelos y en el '
  'CNPCF, y qué ha dicho la SCJN sobre la negativa a la prueba genética.',
  'Morelos (arts. 360–362): se admiten registros dactiloscópicos, exámenes de laboratorio y otros elementos científicos; el '
  'juez los admite según su prudente arbitrio y fija plazo y diligencia; los gastos los cubre quien los ofrece. CNPCF '
  '(art. 552): las partes están obligadas a facilitar exámenes físicos o mentales y a proporcionar muestras orgánicas o '
  'biológicas, con el apercibimiento de tener por ciertas las afirmaciones de la contraparte si no cumplen. SCJN: ante la '
  'negativa del presunto progenitor a la prueba genética opera la presunción de filiación, para proteger el derecho a la '
  'identidad y el interés superior.',
  [M('Morelos: la parte oferente cubre los gastos y el juez admite según su prudente arbitrio'),
   M('CNPCF: obligación de proporcionar muestras, con apercibimiento de tener por ciertas las afirmaciones contrarias', 2),
   M('SCJN: la negativa genera presunción de filiación', 2), cita_alguno((360, 'MP'), (362, 'MP')), cita(552, 'CN')])

q('dificil', '¿Cómo se articulan las reglas sustantivas de alimentos del Código Familiar de Morelos con las reglas procesales '
  'del CNPCF para fijarlos y cobrarlos?',
  'Sustantivo (Código Familiar de Morelos): la obligación deriva del matrimonio, concubinato, adopción o parentesco (art. 35); '
  'comprende casa, comida, vestido, salud, educación y esparcimiento (art. 43) y debe ser proporcional a la posibilidad del '
  'deudor y la necesidad del acreedor, tomando como base la totalidad de las percepciones (art. 46). Procesal (CNPCF): el juez '
  'fija pensión provisional al día siguiente y ordena el descuento (art. 562); si no se acredita capacidad económica la fija '
  'en salarios mínimos, no menos de uno (art. 564); con más de 90 días de incumplimiento ordena inscribir al deudor en el '
  'Registro Nacional de Obligaciones Alimentarias (art. 565).',
  [M('Proporcionalidad entre posibilidad del deudor y necesidad del acreedor (Morelos)', 2),
   M('Pensión provisional al día siguiente con orden de descuento (CNPCF)'),
   M('Inscripción en el Registro Nacional de Obligaciones Alimentarias por más de 90 días de incumplimiento (CNPCF)'),
   cita(46, 'MF'), cita_alguno((562, 'CN'), (565, 'CN'))])

q('dificil', 'Compara el procedimiento de adopción del Código Procesal Familiar de Morelos con el del CNPCF.',
  'Morelos (arts. 510–512): deben consentir quien ejerce la patria potestad, el tutor, quienes lo acogieron como hijo o el MP '
  'si no hay quién; el mayor de doce años también consiente; el juez resuelve dentro del tercer día e informa al Registro '
  'Civil, al DIF estatal, a la SRE y a la autoridad migratoria; la adopción puede revocarse si el adoptado corre riesgo. '
  'CNPCF (arts. 642–645): es competente el juez del domicilio de quien se pretende adoptar; la solicitud se recibe por '
  'escrito o comparecencia videograbada y se provee el mismo día; se da conocimiento al DIF; si los adoptantes no tienen '
  'abogado se designa defensoría pública; basta exhibir actas de nacimiento y manifestar bajo protesta los datos requeridos; '
  'la oposición legítima se tramita por vía incidental.',
  [M('Morelos: el mayor de doce años debe consentir su adopción', 2), M('Morelos: el juez resuelve dentro del tercer día'),
   M('CNPCF: competente el juez del domicilio de quien se pretende adoptar'),
   M('CNPCF: solicitud por escrito o comparecencia videograbada, proveída el mismo día'),
   cita(510, 'MP'), cita_alguno((642, 'CN'), (644, 'CN'))])

q('dificil', 'En un divorcio en Morelos, ¿cuándo procede pensión alimenticia para un excónyuge según el Código Familiar, y '
  'cómo se relaciona con la pensión compensatoria de la jurisprudencia de la SCJN?',
  'Código Familiar de Morelos: al disolverse el matrimonio o concubinato, los alimentos se otorgan si el cónyuge acredita '
  'imposibilidad de obtenerlos por edad, estado físico o mental o incapacidad, y que los necesita por no tener bienes que le '
  'generen ingresos (art. 37); en el divorcio el juez considera la capacidad para trabajar y la situación económica de los '
  'cónyuges, y en el voluntario se respeta el convenio salvo que sea lesivo (art. 179). SCJN: tras la disolución la '
  'obligación alimentaria ordinaria termina y puede surgir una pensión compensatoria, asistencial y resarcitoria, cuyo '
  'presupuesto es la desventaja económica que la disolución provoca a un cónyuge.',
  [M('Morelos: procede si acredita imposibilidad (edad, salud, incapacidad) y necesidad', 2),
   M('Morelos: el juez considera capacidad para trabajar y situación económica'),
   M('SCJN: pensión compensatoria asistencial y resarcitoria por desequilibrio económico', 2),
   cita_alguno((37, 'MF'), (179, 'MF'))])

q('dificil', 'Compara la indemnización al cónyuge dedicado al hogar del Código Familiar de Morelos con la compensación '
  'económica analizada por la SCJN.',
  'Morelos (art. 178): en matrimonios bajo separación de bienes, indemnización no superior al 50% del valor de los bienes '
  'adquiridos, a favor del cónyuge dedicado preponderantemente al hogar y al cuidado de los hijos; el juez resuelve según '
  'las circunstancias. SCJN (compensación económica, p. ej. art. 267 fr. VI del Código Civil del DF): mismo tope de hasta '
  '50% y mismo régimen, con finalidad reparadora del desequilibrio patrimonial —no sancionatoria—, solo sobre bienes '
  'adquiridos durante el matrimonio, carga de la prueba del solicitante y procedencia independiente de la culpa (divorcio '
  'sin expresión de causa).',
  [M('Ambos: hasta el 50% y régimen de separación de bienes', 2), M('Ambos: a favor del cónyuge dedicado al hogar y a los hijos'),
   M('SCJN: finalidad reparadora del desequilibrio, no sancionatoria'), S('SCJN: independiente de la culpa'),
   cita(178, 'MF')])

q('dificil', 'Compara cómo se acredita el concubinato en el Código Familiar de Morelos con los criterios de la SCJN para '
  'valorar su existencia y la duración de los alimentos tras terminar.',
  'Morelos (art. 65): unión de hecho de dos personas libres de matrimonio y sin impedimento, que se acredita con dos años de '
  'vida en común ininterrumpida o con cohabitación y procreación de un hijo en común; genera obligación alimentaria '
  '(art. 37). SCJN: las pruebas deben valorarse en conjunto, con perspectiva de género y sin el estereotipo de que las '
  'relaciones no matrimoniales son efímeras; tras terminar, los alimentos subsisten por el tiempo que duró la relación y '
  'mientras el acreedor no se case ni se una en otro concubinato.',
  [M('Morelos: dos años de vida en común o un hijo en común', 2), M('SCJN: valoración en conjunto y sin estereotipos', 2),
   M('SCJN: alimentos por el tiempo que duró el concubinato'), cita(65, 'MF')])

q('dificil', 'Compara las medidas urgentes que puede dictar el juez familiar en Morelos al pedirse la separación de personas '
  'con las medidas provisionales y de protección del CNPCF.',
  'Morelos (arts. 208 y 210 del Código Procesal Familiar): en urgencia el juez decreta con premura el depósito o la '
  'separación y los alimentos; resuelve sin más trámite y puede variar las disposiciones si hay causa justa. CNPCF: decreta '
  'de oficio y sin audiencia de la contraparte alimentos, guarda y custodia, convivencias y órdenes de protección '
  '(art. 569); las órdenes de protección se dictan en 24 horas y se cumplen en 72, sin esperar notificación (art. 575); '
  'incluyen la desocupación del domicilio por el agresor y la prohibición de acercarse (art. 573).',
  [M('Morelos: en urgencia decreta con premura la separación y los alimentos', 2),
   M('CNPCF: medidas de oficio sin audiencia de la contraparte'), M('CNPCF: órdenes de protección en 24 horas y cumplidas en 72'),
   cita(208, 'MP'), cita_alguno((569, 'CN'), (575, 'CN'))])

q('dificil', 'Analiza la custodia de hijos pequeños: la regla del Código Procesal Familiar de Morelos, el interés superior en '
  'el CNPCF y los criterios de la SCJN sobre la preferencia materna.',
  'Morelos (art. 212): en la separación, a falta de convenio y si no hay riesgo, deja a la madre el cuidado de los hijos '
  'menores de siete años. CNPCF (art. 557): obliga a actuar más allá de la demanda en aras del interés superior y a atender '
  'las necesidades de cada menor sin discriminación. SCJN: la preferencia materna no es un derecho, la presunción de '
  'idoneidad de la madre no es absoluta, debe interpretarse sin estereotipos y se ha declarado inconstitucional la presunción '
  'legal de preferencia materna; por ello la regla de Morelos debe aplicarse —o inaplicarse— a la luz del interés superior '
  'del menor en cada caso.',
  [M('Morelos: la madre conserva a los menores de siete años a falta de convenio', 2),
   M('SCJN: la preferencia materna no es un derecho ni es absoluta (incluso inconstitucional)', 2),
   M('Debe prevalecer el interés superior del menor en cada caso'), cita(212, 'MP'), cita(557, 'CN'),
   N('Concluye que la madre tiene derecho automático a la custodia por ser madre')])

q('dificil', 'Relaciona los plazos para impugnar o reclamar la paternidad en Morelos con los alimentos derivados del '
  'reconocimiento de paternidad y con el criterio de la SCJN sobre la prueba genética.',
  'Código Procesal Familiar de Morelos: el marido tiene sesenta días para contradecir que el hijo de matrimonio es suyo '
  '(art. 447), mientras que el reconocimiento de paternidad o maternidad puede demandarse en cualquier tiempo (art. 449). '
  'Código Familiar de Morelos: la pensión derivada de una sentencia de reconocimiento de paternidad es retroactiva al momento '
  'del nacimiento (art. 38). SCJN: si el presunto padre se niega a la prueba genética opera la presunción de filiación, para '
  'proteger la identidad y el interés superior del menor.',
  [M('Sesenta días para que el marido impugne; el reconocimiento puede demandarse en cualquier tiempo', 2),
   M('Alimentos retroactivos al nacimiento tras el reconocimiento de paternidad', 2),
   M('SCJN: la negativa a la prueba genética genera presunción de filiación'),
   cita(449, 'MP'), cita(38, 'MF')])

q('dificil', '¿Cómo se sanciona o enfrenta la violencia familiar en el Código Familiar de Morelos y en el CNPCF?',
  'Código Familiar de Morelos: la violencia familiar determinada por sentencia firme es impedimento no dispensable para '
  'casarse (art. 77, fr. XII) y la violencia familiar del acreedor contra el deudor es causa de cese de alimentos (art. 55, '
  'fr. III). CNPCF: el juez debe dictar medidas para que cese la violencia y proteger en la violencia vicaria (art. 554); '
  'ante violencia modifica o suspende convivencias o custodia y puede ordenar convivencias supervisadas (art. 561); no '
  'convoca a conciliación (art. 560) y dicta órdenes de protección como la desocupación del domicilio por el agresor '
  '(art. 573).',
  [M('Morelos: impedimento no dispensable para el matrimonio'), M('Morelos: causa de cese de alimentos'),
   M('CNPCF: modificar o suspender convivencias o custodia; convivencias supervisadas', 2),
   M('CNPCF: órdenes de protección (p. ej. desocupación del domicilio por el agresor)'),
   cita_alguno((77, 'MF'), (55, 'MF')), cita_alguno((561, 'CN'), (573, 'CN'))])

assert len(Q) == 50, len(Q)
from collections import Counter  # noqa: E402
cnt = Counter(x['difficulty'] for x in Q)
assert cnt == {'facil': 22, 'mediano': 16, 'dificil': 12}, cnt

OUT = Path(__file__).with_name('familiar_50.json')
OUT.write_text(json.dumps({
    'format': 'rag-lab-bench/v1',
    'name': 'Derecho familiar · 50 (Morelos, CNPCF, SCJN)',
    'topic': 'derecho_familiar',
    'description': ('22 fáciles, 16 medianas, 12 difíciles. Fuentes: Código Familiar y Código Procesal Familiar de '
                    'Morelos, Código Nacional de Procedimientos Civiles y Familiares y Cuadernos de Jurisprudencia de '
                    'la SCJN (texto del corpus al 2026-10-01). Las de Morelos fallarán la recuperación mientras esos '
                    'códigos sigan etiquetados en el tema penal.'),
    'questions': Q,
}, ensure_ascii=False, indent=1))
print(f'{len(Q)} preguntas · {sum(len(x["components"]) for x in Q)} componentes · {dict(cnt)} → {OUT}')
