"""
Genera bench_sets/penal_mx_50.json — benchmark de 50 preguntas de derecho penal mexicano
(delitos sexuales / cópula, parte general y CNPP) para el tab 🧪 Benchmark.

Las respuestas esperadas se redactaron a partir del TEXTO DEL CORPUS (tabla
sistema_penal__qwen06__legal, tema derecho_penal_mexicano) al 2026-09-30: Código Penal de la
Ciudad de México, Código Penal del Estado de México, Código Penal Federal, CNPP y Código Penal
de Morelos. Querétaro NO está en el corpus: las preguntas que lo mencionan esperan que el
sistema lo reconozca y no invente artículos (prueba de honestidad). Si se ingesta el código de
Querétaro, hay que actualizar esas preguntas (marcadas con 'QRO' en notes).

    uv run python apps/rewrite_lab/bench_sets/build_penal_mx.py
"""

import json
from pathlib import Path


def C(kind, text, weight=1):
    return {'kind': kind, 'text': text, 'weight': weight}


M = lambda t, w=1: C('must', t, w)        # noqa: E731
S = lambda t, w=1: C('should', t, w)      # noqa: E731
N = lambda t, w=1: C('must_not', t, w)    # noqa: E731

Q = []


def q(question, expected, components, notes=''):
    Q.append({'question': question, 'expected_answer': expected, 'notes': notes, 'components': components})


QRO_MISSING = M('Indica que los fragmentos/contexto disponibles no contienen la legislación penal de Querétaro '
                '(o que no hay información suficiente sobre Querétaro)', 2)
QRO_INVENT = N('Atribuye al Código Penal de Querétaro un número de artículo, una edad o una pena concretos', 2)

# ═══════════════════════ I. Delitos sexuales y cópula (30) ═══════════════════════

q('Por favor verifica la legislación de las entidades Ciudad de México, Estado de México y Querétaro y dime las '
  'particularidades de cada entidad en cuanto al delito de estupro y sus elementos del delito conforme a la '
  'dogmática penal.',
  'Ciudad de México (art. 180 CPCDMX): comete estupro quien tiene cópula con persona mayor de doce y menor de '
  'dieciocho años, obteniendo su consentimiento por medio de cualquier tipo de engaño; pena de seis meses a cuatro '
  'años de prisión; se persigue por querella. Estado de México (arts. 271 y 272 CPEM): cópula con persona mayor de '
  'quince y menor de dieciocho años obteniendo su consentimiento por medio de cualquier tipo de seducción; uno a '
  'cinco años de prisión; sólo se procede por querella de la ofendida, sus padres o, a falta de éstos, sus '
  'representantes legítimos. Querétaro: el corpus no contiene su Código Penal, por lo que no puede afirmarse su '
  'regulación. Dogmáticamente: conducta de acción dolosa consistente en la cópula; sujeto activo indiferenciado; '
  'sujeto pasivo calificado por la edad; medio comisivo (engaño en CDMX, seducción en Edomex) que vicia el '
  'consentimiento; bien jurídico: libertad y seguridad sexuales y normal desarrollo psicosexual (así titula el CPCDMX '
  'el Título Quinto); tipicidad, antijuridicidad, culpabilidad (dolo) y punibilidad; querella como requisito de '
  'procedibilidad.',
  [M('CDMX (art. 180): el sujeto pasivo es mayor de 12 y menor de 18 años', 2),
   M('CDMX: el consentimiento se obtiene mediante engaño'),
   M('Estado de México (art. 271): el sujeto pasivo es mayor de 15 y menor de 18 años', 2),
   M('Estado de México: el consentimiento se obtiene mediante seducción'),
   QRO_MISSING,
   S('Penas: CDMX de 6 meses a 4 años; Estado de México de 1 a 5 años de prisión'),
   S('En ambas entidades el estupro se persigue por querella'),
   S('Analiza elementos dogmáticos: conducta (cópula), sujetos, medio comisivo, bien jurídico, dolo'),
   QRO_INVENT,
   N('Afirma que en la Ciudad de México el estupro exige que la víctima sea mayor de 15 años')],
  'QRO · pregunta modelo del usuario')

q('¿Cómo define la ley el concepto de cópula en el Código Penal de la Ciudad de México, en el del Estado de México '
  'y en el Código Penal Federal? Señala las diferencias.',
  'CDMX (art. 174): introducción del pene en el cuerpo humano por vía vaginal, anal o bucal. Estado de México '
  '(art. 273): introducción del miembro viril en el cuerpo de la víctima por vía vaginal, anal u oral, '
  'independientemente de su sexo, exista eyaculación o no. CPF (art. 265): introducción del miembro viril en el '
  'cuerpo de la víctima por vía vaginal, anal u oral, independientemente de su sexo. La diferencia principal es que el '
  'Estado de México aclara expresamente que no se requiere eyaculación; las tres coinciden en las tres vías.',
  [M('Cópula = introducción del pene/miembro viril en el cuerpo de la víctima', 2),
   M('Comprende las vías vaginal, anal y oral/bucal', 2),
   M('Señala que el Estado de México precisa que exista eyaculación o no'),
   S('Cita art. 174 CPCDMX, art. 273 CPEM y art. 265 CPF'),
   N('Afirma que la cópula requiere eyaculación')])

q('¿Cuáles son los elementos del delito de estupro en la Ciudad de México y cómo se persigue?',
  'Art. 180 CPCDMX: al que tenga cópula con persona mayor de doce y menor de dieciocho años, obteniendo su '
  'consentimiento por medio de cualquier tipo de engaño, se le impondrá de seis meses a cuatro años de prisión. El '
  'delito se persigue por querella.',
  [M('Conducta: tener cópula'), M('Sujeto pasivo mayor de 12 y menor de 18 años', 2),
   M('Consentimiento obtenido por cualquier tipo de engaño', 2), M('Pena de seis meses a cuatro años de prisión'),
   M('Se persigue por querella'), S('Cita el artículo 180 del Código Penal de la Ciudad de México'),
   N('Afirma que se persigue de oficio')])

q('¿Qué establece el Código Penal del Estado de México sobre el delito de estupro y quién puede presentar la querella?',
  'Art. 271 CPEM: comete estupro quien tenga cópula con una persona mayor de quince años y menor de dieciocho '
  'obteniendo su consentimiento por medio de cualquier tipo de seducción; uno a cinco años de prisión. Art. 272: no '
  'se procede sino por querella de la parte ofendida, de sus padres o, a falta de éstos, de sus representantes '
  'legítimos.',
  [M('Sujeto pasivo mayor de 15 y menor de 18 años', 2), M('Medio: cualquier tipo de seducción', 2),
   M('Pena de uno a cinco años de prisión'),
   M('Querella de la parte ofendida, de sus padres o, a falta de éstos, de sus representantes legítimos'),
   S('Cita los artículos 271 y 272 del Código Penal del Estado de México'),
   N('Afirma que el medio típico en el Estado de México es la violencia física o moral')])

q('En el Código Penal Federal, ¿cómo se tipifica el estupro, cómo se persigue y prescribe su sanción?',
  'Art. 262 CPF: al que tenga cópula con persona mayor de quince años y menor de dieciocho, obteniendo su '
  'consentimiento por medio de engaño, se le aplicarán de tres meses a cuatro años de prisión. Art. 263: sólo se '
  'procede por queja del ofendido o de sus representantes. Art. 266 Ter: son imprescriptibles las sanciones de los '
  'artículos 261, 262 y 266.',
  [M('Pasivo mayor de 15 y menor de 18 años; consentimiento obtenido por engaño', 2),
   M('Pena de tres meses a cuatro años de prisión'), M('Se procede por queja del ofendido o sus representantes (art. 263)'),
   M('Las sanciones del estupro (art. 262) son imprescriptibles según el art. 266 Ter', 2),
   N('Afirma que el estupro federal prescribe en los plazos ordinarios')])

q('Desde la dogmática penal, ¿cuál es la diferencia entre estupro y violación?',
  'En ambos la conducta es la cópula, pero difieren en el medio comisivo y en el consentimiento. En la violación la '
  'cópula se obtiene por medio de la violencia física o moral, sin la voluntad de la víctima (art. 174 CPCDMX; art. '
  '273 CPEM; art. 265 CPF). En el estupro existe consentimiento, pero está viciado porque se obtuvo mediante engaño '
  '(CDMX, CPF) o seducción (Edomex) de una persona dentro de un rango de edad (mayor de 12/15 y menor de 18). El '
  'estupro se persigue por querella; la violación, en regla general, de oficio (salvo supuestos como el de pareja).',
  [M('La violación requiere violencia física o moral', 2),
   M('En el estupro hay consentimiento obtenido mediante engaño o seducción', 2),
   M('El estupro exige un sujeto pasivo dentro de un rango de edad menor de 18 años'),
   S('Menciona que ambos comparten la cópula como conducta'), S('Distingue la querella en el estupro'),
   N('Afirma que el estupro requiere violencia física o moral')])

q('¿Cómo se sanciona la violación en la Ciudad de México y qué ocurre si entre el activo y el pasivo existe matrimonio '
  'o concubinato?',
  'Art. 174 CPCDMX: al que por medio de la violencia física o moral realice cópula con persona de cualquier sexo, '
  'prisión de seis a diecisiete años. Se sanciona igual la introducción por vía vaginal o anal de cualquier elemento, '
  'instrumento o parte del cuerpo distinta al pene con violencia. Si existe vínculo matrimonial, de concubinato o de '
  'pareja, se impone la misma pena y el delito se persigue por querella.',
  [M('Medio: violencia física o moral; cópula con persona de cualquier sexo'), M('Pena de seis a diecisiete años de prisión', 2),
   M('Con vínculo matrimonial, concubinato o de pareja se impone la misma pena', 2),
   M('En esos casos el delito se persigue por querella', 2),
   N('Afirma que entre cónyuges no hay delito de violación')])

q('¿Qué particularidades tiene el tipo de violación en el Código Penal del Estado de México, incluida la regla sobre '
  'adolescentes de entre trece y quince años?',
  'Art. 273 CPEM: al que por medio de la violencia física o moral tenga cópula con una persona sin su voluntad, de '
  'diez a veinte años de prisión y de doscientos a dos mil días multa. También es violación introducir cualquier '
  'parte del cuerpo, objeto o instrumento diferente al miembro viril con violencia. Se equipara la cópula con persona '
  'privada de razón o sentido, que no pueda resistir, o menor de quince años. Si el ofendido es menor de quince y '
  'mayor de trece, consintió, no concurre modificativa, existe relación afectiva y la diferencia de edad no es mayor '
  'de cinco años, se extingue la acción penal o la pena.',
  [M('Pena de diez a veinte años de prisión (y de 200 a 2000 días multa)', 2),
   M('Se equipara a violación la cópula con menor de quince años'),
   M('Extinción de la acción penal si el ofendido tiene entre 13 y 15 años, consintió, hay relación afectiva y la diferencia de edad no excede cinco años', 2),
   S('Incluye la introducción de objeto o instrumento distinto al miembro viril'), S('Cita el artículo 273 CPEM'),
   N('Afirma que la pena básica de violación en el Estado de México es de seis a diecisiete años')])

q('¿Cómo tipifica y sanciona la violación el Código Penal Federal y qué pasa si la víctima es la esposa o concubina?',
  'Art. 265 CPF: comete violación quien por medio de la violencia física o moral realice cópula con persona de '
  'cualquier sexo; prisión de ocho a veinte años. También es violación introducir por vía vaginal o anal cualquier '
  'elemento o instrumento distinto al miembro viril con violencia. Art. 265 bis: si la víctima es la esposa o '
  'concubina se impone la misma pena y el delito se persigue por querella de parte ofendida.',
  [M('Pena de ocho a veinte años de prisión', 2), M('Medio: violencia física o moral'),
   M('Si la víctima es esposa o concubina se aplica la misma pena (art. 265 bis)'),
   M('En ese supuesto se persigue por querella'),
   N('Afirma que la violación entre cónyuges tiene una pena atenuada')])

q('Compara el tratamiento de la violación entre cónyuges o parejas en la Ciudad de México, el Estado de México y el '
  'Código Penal Federal.',
  'CDMX (art. 174, último párrafo): vínculo matrimonial, de concubinato o de pareja → misma pena, perseguible por '
  'querella. CPF (art. 265 bis): esposa o concubina → misma pena, perseguible por querella. Estado de México (art. '
  '274, fr. II): si el delito es cometido por uno de los cónyuges (entre otros parientes), además de las sanciones del '
  'art. 273 se imponen de tres a nueve años de prisión y de treinta a setenta y cinco días multa; es una agravante.',
  [M('CDMX: misma pena y persecución por querella'), M('CPF (265 bis): misma pena y persecución por querella'),
   M('Estado de México: la comisión por cónyuge es una circunstancia agravante (art. 274 fr. II)', 2),
   S('Estado de México: se agregan de tres a nueve años de prisión'),
   N('Afirma que en el Estado de México la violación entre cónyuges se persigue por querella')])

q('¿Qué conductas se equiparan a la violación en el Código Penal de la Ciudad de México?',
  'Art. 175 CPCDMX: se equipara a la violación y se sanciona con la misma pena al que I. realice cópula con persona '
  'que no tenga capacidad de comprender el significado del hecho o por cualquier causa no pueda resistirlo, o II. '
  'introduzca por vía anal o vaginal cualquier elemento, instrumento o parte del cuerpo distinto del pene en una '
  'persona en esas condiciones. Si se ejerce violencia física o moral, la pena se aumenta en una mitad.',
  [M('Cópula con persona sin capacidad de comprender el significado del hecho o que no pueda resistirlo', 2),
   M('Introducción de elemento, instrumento o parte del cuerpo distinta del pene en esa persona'),
   M('Si hay violencia física o moral la pena aumenta en una mitad'), S('Cita el artículo 175 CPCDMX')])

q('Según el Código Penal Federal, ¿qué es la violación equiparada y cuál es su pena?',
  'Art. 266 CPF: se equipara a la violación y se sanciona de ocho a treinta años de prisión: I. al que sin violencia '
  'realice cópula con persona menor de dieciocho años; II. al que sin violencia realice cópula con persona que no '
  'tenga capacidad de comprender el hecho o no pueda resistirlo; III. al que sin violencia y con fines lascivos '
  'introduzca un elemento o instrumento distinto del miembro viril en una persona menor de dieciocho años o incapaz. '
  'Con violencia física o moral, el mínimo y el máximo se aumentan hasta en una mitad.',
  [M('Pena de ocho a treinta años de prisión', 2), M('Cópula sin violencia con persona menor de dieciocho años', 2),
   M('Cópula sin violencia con persona sin capacidad de comprender o de resistir'),
   S('Incluye la introducción de instrumentos con fines lascivos'), S('Con violencia la pena aumenta hasta en una mitad'),
   N('Afirma que la violación equiparada federal se refiere a menores de doce años')])

q('¿Constituye violación introducir un objeto o una parte del cuerpo distinta al pene? Explica cómo lo regulan la '
  'Ciudad de México, el Estado de México y la Federación.',
  'Sí. CDMX (art. 174, tercer párrafo): se sanciona con la misma pena al que introduzca por vía vaginal o anal '
  'cualquier elemento, instrumento o parte del cuerpo distinto al pene, con violencia física o moral. Estado de México '
  '(art. 273, segundo párrafo): comete también violación quien introduzca por vía vaginal o anal cualquier parte del '
  'cuerpo, objeto o instrumento diferente al miembro viril con violencia. CPF (art. 265, tercer párrafo): también es '
  'violación introducir por vía vaginal o anal cualquier elemento o instrumento distinto al miembro viril con violencia.',
  [M('Sí constituye violación (o se sanciona como tal) en las tres legislaciones', 2),
   M('Por vía vaginal o anal'), M('Requiere violencia física o moral'),
   N('Afirma que la introducción de objetos se tipifica sólo como abuso sexual')])

q('¿Cuáles son las agravantes de la violación y el abuso sexual en el Código Penal de la Ciudad de México y en cuánto '
  'aumenta la pena?',
  'Art. 178 CPCDMX: las penas se aumentan en dos terceras partes cuando se cometen: I. con intervención de dos o más '
  'personas; II. por ascendiente contra descendiente, hermanos, tutor, padrastro o madrastra, amasio, etc. (además '
  'pierde patria potestad, tutela y derechos sucesorios); III. valiéndose de empleo, cargo o comisión públicos, '
  'profesión o ministerio religioso; IV. por quien tenga al ofendido bajo custodia, guarda o educación; V. a bordo de '
  'un vehículo particular o de servicio público; VI. en despoblado o lugar solitario; VII. dentro de centros '
  'educativos, culturales, deportivos, religiosos o de trabajo; VIII. en inmuebles públicos.',
  [M('El aumento es de dos terceras partes', 2), M('Intervención de dos o más personas'),
   M('Parentesco o relación familiar (ascendiente, hermano, tutor, padrastro, etc.)'),
   S('Víctima a bordo de vehículo o en despoblado'), S('Cargo público, profesión o ministerio religioso'),
   N('Afirma que el aumento es de una mitad')])

q('¿Qué circunstancias modifican la pena de violación en el Estado de México cuando participan varias personas, se '
  'causa la muerte o la víctima es menor de quince o mayor de sesenta años?',
  'Art. 274 CPEM: I. si participan dos o más personas, de cuarenta a setenta años de prisión; IV. si se causa la '
  'muerte, de cuarenta a setenta años; V. si el ofendido es menor de quince o mayor de sesenta años, de quince a '
  'treinta años de prisión. También agravan: parentesco o cónyuge (fr. II), servidor público (fr. III), discapacidad '
  '(fr. VI), transporte público (fr. VII) y relación de confianza o subordinación (fr. VIII).',
  [M('Dos o más personas: de 40 a 70 años de prisión', 2), M('Si se causa la muerte: de 40 a 70 años de prisión'),
   M('Menor de quince o mayor de sesenta años: de 15 a 30 años'), S('Cita el artículo 274 CPEM')])

q('¿Qué distingue al abuso sexual de la violación? Compara la Ciudad de México, el Estado de México y el Código Penal '
  'Federal.',
  'El abuso sexual se comete sin el propósito de llegar a la cópula: ejecutar un acto sexual sin consentimiento, '
  'obligar a observarlo o hacerlo ejecutar. CDMX (art. 176): uno a seis años; acto sexual es cualquier acción dolosa '
  'con sentido lascivo. CPF (art. 260) y Edomex (art. 270): tres a siete años; acto sexual incluye tocamientos, '
  'caricias, roces corporales, exhibiciones o representaciones sexuales explícitas; también obligar a exhibir el '
  'cuerpo; el consentimiento no puede presumirse del silencio, la pasividad o la falta de resistencia física.',
  [M('El abuso sexual se comete sin el propósito de llegar a la cópula', 2),
   M('CDMX: pena de uno a seis años de prisión'), M('CPF y Estado de México: pena de tres a siete años de prisión'),
   S('El consentimiento no puede presumirse del silencio o la falta de resistencia (CPF/Edomex)'),
   S('Define acto sexual como tocamientos, caricias, roces o exhibiciones'),
   N('Afirma que el abuso sexual requiere cópula')])

q('¿El abuso sexual se persigue de oficio o por querella en la Ciudad de México, en el Estado de México y en el ámbito '
  'federal?',
  'CDMX (art. 176): se persigue por querella, salvo que concurra violencia. CPF (art. 260): se persigue de oficio. '
  'Estado de México (art. 270): se persigue de oficio.',
  [M('CDMX: por querella, salvo que concurra violencia', 2), M('CPF: de oficio', 2), M('Estado de México: de oficio', 2),
   N('Afirma que en las tres legislaciones el abuso sexual se persigue por querella')])

q('¿Cuál es la diferencia entre hostigamiento sexual y acoso sexual en el Estado de México y cómo se regula el '
  'hostigamiento en el Código Penal Federal?',
  'Edomex art. 269 (hostigamiento): conducta sexual no consentida contra persona subordinada, valiéndose de la '
  'posición jerárquica laboral, docente, doméstica u otra; dos a seis años o multa; de oficio. Art. 269 Bis (acoso): '
  'conducta de naturaleza sexual no consentida que lesiona la dignidad, sin requerir jerarquía; incluye grabar o '
  'difundir imágenes con propósitos lascivos y conductas en transporte público; uno a cuatro años. CPF art. 259 Bis: '
  'asedio reiterado con fines lascivos valiéndose de la posición jerárquica; hasta ochocientos días multa; sólo '
  'punible si causa perjuicio o daño; a petición de parte ofendida.',
  [M('El hostigamiento implica subordinación o jerarquía; el acoso no la requiere', 2),
   M('CPF: el hostigamiento se sanciona con multa (hasta 800 días multa), no con prisión'),
   M('CPF: sólo es punible si causa perjuicio o daño y se persigue a petición de parte'),
   S('Edomex: hostigamiento de 2 a 6 años; acoso de 1 a 4 años'),
   N('Afirma que el hostigamiento federal se castiga con prisión de dos a seis años')])

q('¿Cómo se regula el acoso sexual en la Ciudad de México y cuándo se agrava?',
  'Art. 179 CPCDMX: a quien solicite favores sexuales para sí o para un tercero o realice una conducta de naturaleza '
  'sexual indeseable que le cause daño o sufrimiento psicoemocional que lesione su dignidad, de uno a tres años de '
  'prisión. Si existe relación jerárquica de subordinación (laboral, docente, doméstica), la pena aumenta en una '
  'tercera parte; si es servidor público, además destitución e inhabilitación. Se persigue por querella.',
  [M('Pena de uno a tres años de prisión'), M('Requiere daño o sufrimiento psicoemocional que lesione la dignidad'),
   M('Con relación jerárquica la pena aumenta en una tercera parte'), M('Se persigue por querella'),
   S('Servidor público: destitución e inhabilitación')])

q('¿Cómo se sanciona el incesto en la Ciudad de México, el Estado de México y el Código Penal Federal?',
  'CDMX (art. 181): hermanos y ascendientes o descendientes consanguíneos en línea recta que con conocimiento del '
  'parentesco tengan cópula: prisión o tratamiento en libertad de uno a seis años; si uno es mayor de 18 y el otro '
  'menor de 12, al primero de ocho a veinte años. Estado de México (art. 221): ascendientes que tengan cópula con sus '
  'descendientes, tres a siete años; a los descendientes uno a tres años; misma pena menor para hermanos. CPF (art. '
  '272): ascendientes con descendientes mayores de edad, uno a seis años; si la víctima es menor, la conducta siempre '
  'se entiende como violación.',
  [M('Exige conocimiento del parentesco / relación entre ascendientes, descendientes o hermanos'),
   M('CDMX: uno a seis años de prisión (o tratamiento en libertad)'),
   M('Estado de México: ascendientes de tres a siete años; descendientes y hermanos de uno a tres años'),
   M('CPF: si la víctima es menor de edad la conducta se considera violación', 2)])

q('¿Qué es la pederastia y cómo la sancionan el Estado de México y la Ciudad de México?',
  'Estado de México (art. 205 Bis): a quien se aproveche de la confianza, subordinación o superioridad sobre un menor '
  'de dieciocho años (parentesco, tutela, relación docente, religiosa, laboral, médica, etc.) y ejecute, obligue, '
  'induzca o convenza a ejecutar cualquier acto sexual, con o sin su consentimiento: nueve a dieciocho años de prisión; '
  'con violencia física, aumento de una mitad; pérdida de patria potestad, tutela, etc. CDMX (art. 181 Bis, segundo '
  'párrafo): quien valiéndose de relación de confianza o subordinación convenza a una persona menor de dieciocho años '
  'para realizar cópula: diecisiete a veinticuatro años.',
  [M('Aprovechamiento de una relación de confianza, subordinación o superioridad sobre un menor de 18 años', 2),
   M('Estado de México: nueve a dieciocho años de prisión'), M('CDMX: diecisiete a veinticuatro años de prisión'),
   S('Es irrelevante el consentimiento del menor'), S('Pérdida de patria potestad o tutela')])

q('¿Qué delito comete en la Ciudad de México quien, por redes sociales o internet, contacta a un menor de dieciocho '
  'años para pedirle imágenes sexuales o un encuentro sexual?',
  'Art. 179 Bis CPCDMX: se impondrán de cuatro a seis años de prisión y de 500 a 1000 UMA a quien, haciendo uso de '
  'medios de radiodifusión, telecomunicaciones, informáticos u otro medio de transmisión de datos, contacte a una '
  'persona menor de dieciocho años (o sin capacidad de comprender o resistir) y le requiera o comparta imágenes, audio '
  'o video de actividades sexuales explícitas o actos de connotación sexual, o le solicite un encuentro sexual.',
  [M('Pena de cuatro a seis años de prisión', 2), M('Uso de medios informáticos, telecomunicaciones o transmisión de datos'),
   M('Requerir o compartir imágenes/video sexuales o solicitar un encuentro sexual con un menor de 18'),
   S('Cita el artículo 179 Bis CPCDMX')])

q('¿Qué conductas constituyen el delito contra la intimidad sexual en la Ciudad de México y cuál es su pena?',
  'Art. 181 Quintus CPCDMX: I. videograbar, audiograbar, fotografiar, filmar o elaborar imágenes, audios o videos '
  'reales o simulados de contenido sexual íntimo de una persona sin su consentimiento o mediante engaño; II. exponer, '
  'distribuir, difundir, exhibir, compartir, etc. dicho contenido a sabiendas de que no hay consentimiento. Pena de '
  'cuatro a seis años de prisión y multa de 500 a 1000 UMA; se agrava en una mitad por relación de pareja, parentesco, '
  'servidor público, etc.; se persigue por querella.',
  [M('Grabar o elaborar contenido sexual íntimo sin consentimiento'), M('Difundir o compartir ese contenido sin consentimiento'),
   M('Pena de cuatro a seis años de prisión', 2), M('Se persigue por querella'),
   S('Agravante de una mitad si hubo relación sentimental o de pareja')])

q('Si de un delito sexual resultan hijos, ¿qué comprende la reparación del daño? ¿Y qué medida de seguridad prevé la '
  'Ciudad de México para los sentenciados por delitos sexuales?',
  'CDMX (art. 182) y CPF (art. 276 bis): cuando a consecuencia de los delitos sexuales resulten hijos, la reparación '
  'del daño comprende el pago de alimentos para éstos y para la madre en los términos de la legislación civil. CDMX '
  '(art. 178 Bis): el juez ordenará inscribir al sentenciado en el Registro Público de Personas Agresoras Sexuales como '
  'medida de seguridad, salvo que el delito se persiga por querella.',
  [M('La reparación comprende el pago de alimentos para los hijos y para la madre', 2),
   M('Inscripción en el Registro Público de Personas Agresoras Sexuales'),
   S('La inscripción no procede en delitos perseguibles por querella'),
   S('Cita art. 182 CPCDMX / 276 bis CPF y 178 Bis CPCDMX')])

q('Compara el delito de estupro en el Código Penal de Morelos con el de la Ciudad de México.',
  'Morelos (art. 159): cópula con persona mayor de doce y menor de dieciocho años obteniendo su consentimiento por '
  'seducción o engaño; cinco a diez años de prisión; seis a doce años si el activo convive con el pasivo por '
  'familiaridad, actividad docente o en centros educativos o de asistencia social (con destitución si es servidor '
  'público). Art. 160: se procede por queja del ofendido, sus padres o representantes. CDMX (art. 180): mismo rango de '
  'edad, pero sólo engaño como medio y pena de seis meses a cuatro años; querella. Morelos castiga con mucha mayor '
  'severidad.',
  [M('Ambos: pasivo mayor de 12 y menor de 18 años'), M('Morelos admite seducción o engaño; CDMX sólo engaño', 2),
   M('Morelos: cinco a diez años; CDMX: seis meses a cuatro años', 2),
   S('Morelos agrava (6 a 12 años) por convivencia familiar o docente'), S('En ambos se requiere querella/queja')])

q('¿Qué establece el Código Penal del Estado de Querétaro sobre el delito de violación y sus agravantes?',
  'El corpus disponible no contiene el Código Penal del Estado de Querétaro, por lo que no es posible responder con '
  'fundamento sobre su regulación. Una respuesta correcta lo indica y, en su caso, sólo refiere lo que sí consta '
  '(p. ej. CDMX, Estado de México o CPF) aclarando que no es legislación de Querétaro.',
  [QRO_MISSING, QRO_INVENT,
   S('Si menciona otras legislaciones, aclara que no corresponden a Querétaro')],
  'QRO · prueba de honestidad (no inventar)')

q('Un sujeto es detenido en flagrancia por un delito de estupro. Como el estupro se persigue por querella, ¿qué debe '
  'ocurrir con la querella y cuánto tiempo puede permanecer detenido?',
  'Art. 148 CNPP: cuando se detenga a una persona por un delito que requiera querella, se informará inmediatamente a '
  'quien pueda presentarla y se le concederá un plazo razonable que en ningún caso podrá ser mayor de doce horas desde '
  'que la víctima u ofendido fue notificado, o de veinticuatro horas desde la detención si no fue posible localizarla. '
  'Si no se presenta la querella, el detenido será puesto en libertad de inmediato. Si la víctima tiene imposibilidad '
  'física, pueden legitimarla parientes consanguíneos hasta el tercer grado o por afinidad en primer grado.',
  [M('Se informa de inmediato a quien pueda presentar la querella'),
   M('Plazo máximo de doce horas desde la notificación a la víctima', 2),
   M('O veinticuatro horas desde la detención si no se localiza a la víctima', 2),
   M('Sin querella, el detenido es puesto en libertad de inmediato'), S('Cita el artículo 148 del CNPP')])

q('¿El delito de violación amerita prisión preventiva oficiosa conforme al CNPP?',
  'Sí. El art. 167 CNPP ordena que la persona juzgadora de control imponga la prisión preventiva oficiosamente, entre '
  'otros, en los casos de abuso o violencia sexual contra menores, homicidio doloso, feminicidio, violación, secuestro '
  'y trata de personas.',
  [M('Sí, la violación está en el catálogo de prisión preventiva oficiosa', 2), M('Fundamento: artículo 167 del CNPP'),
   S('Menciona también el abuso o violencia sexual contra menores'),
   N('Afirma que en la violación el Ministerio Público debe justificar la necesidad de cautela para la prisión preventiva')])

q('¿Proceden los acuerdos reparatorios en el estupro? ¿Y un criterio de oportunidad en un delito sexual cometido con '
  'violencia?',
  'Acuerdos reparatorios (art. 187 CNPP): proceden en delitos que se persiguen por querella o que admiten el perdón, '
  'delitos culposos y patrimoniales sin violencia; el estupro se persigue por querella, por lo que en principio procede '
  '(salvo acuerdos previos por el mismo delito doloso o incumplimiento anterior). Criterios de oportunidad (art. 256): '
  'la fracción I exige que el delito no se haya cometido con violencia, y no se aplican en delitos contra el libre '
  'desarrollo de la personalidad ni violencia familiar; por tanto no procede en un delito sexual violento.',
  [M('Los acuerdos reparatorios proceden en delitos perseguibles por querella, como el estupro', 2),
   M('El criterio de oportunidad no procede en delitos cometidos con violencia'),
   S('Excepciones de 187: acuerdos previos por el mismo delito doloso o incumplimiento previo; violencia familiar'),
   S('Art. 256: excluye delitos contra el libre desarrollo de la personalidad'),
   N('Afirma que los acuerdos reparatorios nunca proceden en delitos sexuales')])

q('Conforme al Código Penal Federal, ¿prescribe la acción penal por abuso sexual de menores, estupro y violación '
  'equiparada?',
  'No. El art. 266 Ter CPF establece que son imprescriptibles las sanciones de los artículos 261 (abuso sexual de '
  'menores o incapaces), 262 (estupro) y 266 (violación equiparada).',
  [M('Son imprescriptibles', 2), M('Artículo 266 Ter del CPF'),
   M('Se refiere a los artículos 261, 262 y 266'),
   N('Da un plazo de prescripción para esos delitos')])

# ═══════════════════════ II. Parte general / dogmática (10) ═══════════════════════

q('¿Cuáles son los elementos del delito según la dogmática penal y cómo lo define el Código Penal del Estado de México?',
  'El art. 6 del CPEM define el delito como la conducta típica, antijurídica, culpable y punible. La dogmática '
  'distingue así la conducta (acción u omisión), la tipicidad (adecuación a la descripción legal), la antijuridicidad '
  '(contrariedad al derecho sin causa de justificación), la culpabilidad (reprochabilidad; dolo o culpa) y la '
  'punibilidad. El CPF (art. 7o) lo define como el acto u omisión que sancionan las leyes penales.',
  [M('Conducta típica, antijurídica, culpable y punible (art. 6 CPEM)', 2), M('Explica la conducta como acción u omisión'),
   S('Explica tipicidad, antijuridicidad y culpabilidad'), S('Menciona la definición del art. 7o CPF')])

q('¿Cuándo se actúa con dolo y cuándo con culpa según el Código Penal de la Ciudad de México y el Código Penal Federal?',
  'CDMX (art. 18) y CPF (art. 9o): obra dolosamente quien, conociendo los elementos del tipo penal (del hecho típico) '
  'o previendo como posible el resultado típico, quiere o acepta su realización. Obra culposamente quien produce el '
  'resultado típico que no previó siendo previsible o previó confiando en que no se produciría, en virtud de la '
  'violación de un deber de cuidado.',
  [M('Dolo: conocer los elementos del tipo o prever el resultado, y quererlo o aceptarlo', 2),
   M('Culpa: resultado no previsto siendo previsible, o previsto confiando en que no ocurriría', 2),
   M('La culpa implica violación de un deber de cuidado'), S('Cita art. 18 CPCDMX y/o art. 9o CPF')])

q('¿Qué es la tentativa punible y qué ocurre si el sujeto desiste voluntariamente?',
  'CDMX (art. 20): existe tentativa punible cuando la resolución de cometer un delito se exterioriza realizando en '
  'parte o totalmente los actos ejecutivos que deberían producir el resultado, u omitiendo los que deberían evitarlo, '
  'si por causas ajenas a la voluntad del sujeto no se consuma, pero se pone en peligro el bien jurídico. CPF (art. '
  '12): definición análoga; si el sujeto desiste espontáneamente o impide la consumación, no se le impone pena por la '
  'tentativa, sin perjuicio de sancionar actos que por sí mismos constituyan delito. Estado de México (art. 10) prevé '
  'lo mismo.',
  [M('Exteriorización de actos ejecutivos que no llegan a la consumación por causas ajenas a la voluntad', 2),
   M('Con desistimiento espontáneo no se sanciona la tentativa', 2),
   S('Se sancionan los actos ejecutados que constituyan delito por sí mismos'), S('CDMX exige puesta en peligro del bien jurídico')])

q('¿Qué es la comisión por omisión (omisión impropia) y quién es garante según el Código Penal de la Ciudad de México?',
  'Art. 16 CPCDMX: en los delitos de resultado material, el resultado es atribuible a quien omita impedirlo si tenía '
  'el deber jurídico de evitarlo, si: I. es garante del bien jurídico; II. podía evitarlo; III. su inactividad es '
  'equivalente a la actividad prohibida. Es garante quien: a) aceptó su custodia; b) formaba parte voluntariamente de '
  'una comunidad que afronta peligros; c) con una actividad precedente generó el peligro; d) está en posición de '
  'custodia de la vida o salud de un familiar o pupilo.',
  [M('Sólo en delitos de resultado material'), M('Requiere calidad de garante con deber jurídico de evitar el resultado', 2),
   M('Enumera fuentes de garante (custodia aceptada, actuar precedente, comunidad de peligro, familia/pupilo)'),
   S('Equivalencia de la omisión con la acción')])

q('¿Qué diferencia hay entre delito instantáneo, permanente y continuado?',
  'CDMX (art. 17): instantáneo, cuando la consumación se agota en el mismo momento en que se realizan todos sus '
  'elementos; permanente o continuo, cuando se viola el mismo precepto y la consumación se prolonga en el tiempo; '
  'continuado, cuando con unidad de propósito delictivo, pluralidad de conductas e identidad de sujeto pasivo se '
  'concretan los elementos de un mismo tipo. El CPF (art. 7o) y el CPEM (art. 8) contienen clasificaciones '
  'equivalentes.',
  [M('Instantáneo: la consumación se agota en el mismo momento'), M('Permanente: la consumación se prolonga en el tiempo'),
   M('Continuado: unidad de propósito, pluralidad de conductas e identidad de sujeto pasivo', 2)])

q('¿Cuáles son las formas de autoría y participación en el Código Penal de la Ciudad de México?',
  'Art. 22 CPCDMX: son responsables quienes I. lo realicen por sí (autor material); II. conjuntamente con otros '
  '(coautoría); III. sirviéndose de otro como instrumento (autoría mediata); IV. determinen dolosamente al autor '
  '(instigación); V. dolosamente presten ayuda o auxilio (complicidad); VI. con posterioridad auxilien al autor en '
  'cumplimiento de una promesa anterior. La instigación y la complicidad sólo son admisibles en delitos dolosos, y los '
  'partícipes sólo responden si el hecho alcanza al menos el grado de tentativa.',
  [M('Autoría directa, coautoría y autoría mediata'), M('Instigación y complicidad'),
   M('Instigación y complicidad sólo en delitos dolosos'),
   S('Los partícipes responden si el hecho llega al menos a tentativa'), S('Cita el artículo 22 CPCDMX')])

q('¿Cuáles son los requisitos de la legítima defensa y en qué caso se presume?',
  'CDMX (art. 29, apartado B, fr. I): se repela una agresión real, actual o inminente y sin derecho, en defensa de '
  'bienes jurídicos propios o ajenos, siempre que exista necesidad de la defensa empleada y no medie provocación '
  'dolosa suficiente e inmediata. Se presume, salvo prueba en contrario, cuando se causa daño a quien trate de '
  'penetrar o penetre sin derecho al lugar donde habita el que se defiende o su familia. El CPF (art. 15, fr. IV) '
  'exige además racionalidad de los medios empleados.',
  [M('Agresión real, actual o inminente y sin derecho', 2), M('Necesidad de la defensa (y racionalidad de los medios en CPF/Edomex)'),
   M('Que no medie provocación dolosa suficiente e inmediata'),
   M('Presunción al repeler a quien penetra sin derecho al hogar'), S('Es una causa de justificación')])

q('¿Cuándo excluye el delito el consentimiento del titular del bien jurídico? Compara la Ciudad de México y el Estado '
  'de México.',
  'CDMX (art. 29, A, fr. IV, causa de atipicidad): bien jurídico disponible, titular con capacidad jurídica para '
  'disponer de él, y consentimiento expreso o tácito sin vicio. Estado de México (art. 15, fr. III, a): se exige que '
  'se trate de un delito perseguible por querella, que el titular tenga capacidad de disponer libremente del bien y que '
  'el consentimiento sea expreso o tácito sin vicio de la voluntad. El CPF (art. 15 fr. III) exige bien disponible, '
  'capacidad y consentimiento sin vicio o presunto.',
  [M('Consentimiento expreso o tácito y sin vicio', 2), M('Capacidad jurídica del titular para disponer del bien'),
   M('CDMX: bien jurídico disponible; Estado de México: delito perseguible por querella', 2),
   S('En CDMX se clasifica como causa de atipicidad')])

q('¿Qué es el error de tipo y qué efectos tiene si es vencible o invencible según el Código Penal de la Ciudad de México?',
  'Art. 29, apartado A, fr. III CPCDMX: hay atipicidad por error de tipo cuando el agente obra con error sobre algún '
  'elemento del tipo penal. Si es invencible, se excluye el delito. Si es vencible, se excluye sólo cuando el tipo no '
  'admite realización culposa; si la admite, no se excluye el delito y se sanciona como culposo (art. 83).',
  [M('Error que recae sobre un elemento del tipo penal'), M('Invencible: excluye el delito', 2),
   M('Vencible: excluye sólo si el delito no admite forma culposa; si la admite se sanciona como culposo', 2)])

q('¿Quién es inimputable según el Código Penal del Estado de México?',
  'Art. 16 CPEM: es inimputable quien padezca I. alienación u otro trastorno similar permanente; II. trastorno mental '
  'transitorio producido en forma accidental o involuntaria; III. sordomudez careciendo totalmente de instrucción; '
  'siempre que tengan como consecuencia la ausencia de capacidad de comprender la ilicitud de su acción u omisión. '
  'Art. 17: las excluyentes se hacen valer de oficio.',
  [M('Alienación u otro trastorno similar permanente'), M('Trastorno mental transitorio accidental o involuntario'),
   M('Sordomudez careciendo totalmente de instrucción'),
   M('Debe suprimir la capacidad de comprender la ilicitud'), S('Las excluyentes se hacen valer de oficio (art. 17)')])

# ═══════════════════════ III. Procedimiento penal — CNPP (10) ═══════════════════════

q('¿Cuáles son los supuestos de flagrancia según el Código Nacional de Procedimientos Penales?',
  'Art. 146 CNPP: se puede detener sin orden judicial cuando I. la persona es detenida en el momento de estar '
  'cometiendo un delito, o II. inmediatamente después de cometerlo, porque a) es sorprendida y perseguida material e '
  'ininterrumpidamente, o b) es señalada por la víctima, un testigo o un copartícipe y tiene instrumentos, objetos o '
  'productos del delito o hay indicios de su intervención. En el señalamiento se exige que no se haya interrumpido su '
  'búsqueda. Art. 147: cualquier persona puede detener en flagrancia y debe entregar al detenido de inmediato.',
  [M('Detención en el momento de cometer el delito'), M('Persecución material e ininterrumpida inmediatamente después', 2),
   M('Señalamiento por víctima o testigo con objetos o indicios, sin interrumpir la búsqueda', 2),
   S('Cualquier persona puede detener en flagrancia (art. 147)'), S('Cita el artículo 146 CNPP')])

q('¿Qué requisitos debe cumplir el Ministerio Público para ordenar una detención por caso urgente?',
  'Art. 150 CNPP: I. datos de un hecho señalado como delito grave y probabilidad de que la persona lo cometió (graves: '
  'los de prisión preventiva oficiosa y aquellos cuyo término medio aritmético sea mayor de cinco años); II. riesgo '
  'fundado de que el imputado se sustraiga de la justicia; III. que por razón de hora, lugar u otra circunstancia no '
  'pueda ocurrirse ante la autoridad judicial. El término medio aritmético es la suma de la pena mínima y máxima '
  'dividida entre dos. El juez de control califica la legalidad de la detención.',
  [M('Delito grave y probabilidad de participación'), M('Riesgo fundado de sustracción de la justicia'),
   M('Imposibilidad de acudir ante la autoridad judicial por hora, lugar u otra circunstancia'),
   M('Graves: prisión preventiva oficiosa o término medio aritmético mayor de cinco años', 2),
   S('Explica el cálculo del término medio aritmético')])

q('¿Cuánto tiempo puede durar como máximo la prisión preventiva?',
  'Art. 165 CNPP: no puede exceder del máximo de pena que fije la ley al delito y en ningún caso será superior a dos '
  'años, salvo que su prolongación se deba al ejercicio del derecho de defensa del imputado. Cumplido el término sin '
  'sentencia, el imputado será puesto en libertad de inmediato, sin perjuicio de imponer otras medidas cautelares.',
  [M('Máximo de dos años', 2), M('Salvo que la prolongación se deba al ejercicio del derecho de defensa'),
   M('Cumplido el plazo sin sentencia, libertad inmediata (pudiendo imponerse otras medidas cautelares)'),
   S('No puede exceder la pena máxima del delito'), N('Afirma que el plazo máximo es de un año')])

q('¿Cuál es la finalidad de las medidas cautelares y cuáles prevé el CNPP?',
  'Arts. 153 y 155 CNPP: se imponen por resolución judicial y por el tiempo indispensable para asegurar la presencia '
  'del imputado, garantizar la seguridad de la víctima o testigos o evitar la obstaculización del procedimiento. El '
  'art. 155 enumera catorce: presentación periódica, garantía económica, embargo, inmovilización de cuentas, '
  'prohibición de salir, vigilancia, prohibición de concurrir a lugares, prohibición de acercarse a personas, '
  'separación del domicilio, suspensión del cargo, suspensión de actividad profesional, localizadores electrónicos, '
  'resguardo domiciliario y prisión preventiva. No pueden usarse para obtener un reconocimiento de culpabilidad ni '
  'como sanción anticipada.',
  [M('Finalidad: asegurar la presencia del imputado, proteger a víctima/testigos, evitar obstaculización', 2),
   M('Las impone el juez por resolución judicial'), M('Enumera varias medidas del art. 155 incluyendo la prisión preventiva'),
   S('No pueden ser sanción anticipada ni medio para obtener reconocimiento de culpabilidad')])

q('¿Qué actos se realizan en la audiencia inicial del procedimiento penal acusatorio?',
  'Art. 307 CNPP: se informan al imputado sus derechos, se realiza el control de legalidad de la detención si '
  'corresponde, se formula la imputación, se da oportunidad de declarar al imputado, se resuelve sobre la vinculación a '
  'proceso y las medidas cautelares, y se define el plazo para el cierre de la investigación. Deben concurrir el '
  'Ministerio Público, el imputado y su defensor; la víctima puede asistir pero no es requisito de validez.',
  [M('Control de legalidad de la detención'), M('Formulación de la imputación'), M('Oportunidad de declarar al imputado'),
   M('Resolución sobre vinculación a proceso y medidas cautelares'), M('Plazo para el cierre de la investigación'),
   S('La presencia de la víctima no es requisito de validez')])

q('¿Qué requisitos exige el CNPP para dictar el auto de vinculación a proceso y en qué plazo debe resolverse?',
  'Art. 316 CNPP: I. que se haya formulado la imputación; II. que se haya dado oportunidad de declarar; III. que de '
  'los antecedentes se desprendan datos de prueba que establezcan un hecho que la ley señala como delito y la '
  'probabilidad de que el imputado lo cometió o participó (indicios razonables); IV. que no se actualice una causa de '
  'extinción o excluyente. Art. 313: la audiencia de vinculación debe celebrarse dentro de setenta y dos horas o, si se '
  'duplica el plazo, de ciento cuarenta y cuatro horas.',
  [M('Imputación formulada y oportunidad de declarar'),
   M('Datos de prueba de un hecho que la ley señala como delito y probabilidad de participación', 2),
   M('Que no exista causa de extinción de la acción o excluyente del delito'),
   M('Plazo de 72 horas, ampliable a 144 horas', 2)])

q('¿Cuál es el plazo máximo de la investigación complementaria?',
  'Art. 321 CNPP: lo fija el juez de control antes de terminar la audiencia inicial; no puede ser mayor de dos meses si '
  'la pena máxima del delito no excede de dos años de prisión, ni de seis meses si la excede. Puede prorrogarse '
  'justificadamente dentro de esos límites; vencido, la investigación se da por cerrada.',
  [M('Dos meses si la pena máxima no excede de dos años', 2), M('Seis meses si la pena máxima excede de dos años', 2),
   S('Lo fija el juez de control en la audiencia inicial')])

q('¿Cuándo procede la suspensión condicional del proceso y por cuánto tiempo?',
  'Art. 192 CNPP: a solicitud del imputado o del MP con su acuerdo, cuando I. el auto de vinculación se dictó por un '
  'delito cuya media aritmética de la pena de prisión no exceda de cinco años; II. no haya oposición fundada de la '
  'víctima; III. hayan transcurrido dos años desde el cumplimiento o cinco desde el incumplimiento de una suspensión '
  'anterior. Art. 195: el plazo no puede ser inferior a seis meses ni superior a tres años, con condiciones como residir '
  'en lugar determinado, abstenerse de drogas, tratamiento, etc. Art. 191: incluye un plan de reparación del daño.',
  [M('Media aritmética de la pena de prisión que no exceda de cinco años', 2), M('Sin oposición fundada de la víctima'),
   M('Plazo de seis meses a tres años', 2), S('Requiere plan de reparación del daño'),
   S('Dos años desde cumplimiento o cinco desde incumplimiento de una suspensión anterior')])

q('¿Qué requisitos exige el procedimiento abreviado y qué reducción de pena puede solicitar el Ministerio Público?',
  'Art. 201 CNPP: que el MP lo solicite formulando acusación; que la víctima no presente oposición fundada; que el '
  'imputado reconozca estar informado, renuncie expresamente al juicio oral, consienta el procedimiento, admita su '
  'responsabilidad y acepte ser sentenciado con los medios de convicción del MP. Art. 202: procede tras la vinculación '
  'a proceso y hasta antes del auto de apertura a juicio. Si no hay condena previa por delito doloso y la media '
  'aritmética no excede de cinco años, reducción de hasta la mitad de la mínima (dolosos) o dos terceras partes '
  '(culposos); en cualquier caso, hasta un tercio de la mínima (dolosos) o la mitad (culposos).',
  [M('El imputado admite su responsabilidad y renuncia al juicio oral', 2), M('Sin oposición fundada de la víctima'),
   M('Oportunidad: después de la vinculación a proceso y antes del auto de apertura a juicio'),
   M('Reducción de hasta un tercio de la mínima en dolosos (o hasta la mitad si se cumplen los requisitos)', 2),
   N('Afirma que el procedimiento abreviado procede después de dictado el auto de apertura a juicio')])

q('¿Cuál es la diferencia entre dato de prueba, medio de prueba y prueba, y qué estándar se exige para condenar?',
  'Art. 261 CNPP: dato de prueba es la referencia al contenido de un medio de convicción aún no desahogado ante el '
  'juez, idóneo y pertinente para establecer razonablemente el hecho y la probable participación; medios de prueba son '
  'las fuentes de información que permiten reconstruir los hechos; prueba es el conocimiento cierto o probable que, '
  'desahogado en audiencia bajo inmediación y contradicción, sirve al tribunal para concluir sobre los hechos. Art. '
  '402: sólo se condena si el tribunal adquiere convicción más allá de toda duda razonable; la duda favorece al '
  'acusado y no se puede condenar con el solo mérito de la propia declaración.',
  [M('Dato de prueba: referencia a un medio de convicción aún no desahogado', 2),
   M('Prueba: desahogada en audiencia bajo inmediación y contradicción', 2), M('Medio de prueba: fuente de información para reconstruir los hechos'),
   M('Estándar de condena: más allá de toda duda razonable'), S('La duda favorece al acusado')])

assert len(Q) == 50, len(Q)

OUT = Path(__file__).with_name('penal_mx_50.json')
OUT.write_text(json.dumps({
    'format': 'rag-lab-bench/v1',
    'name': 'Derecho penal mexicano · 50 (sexuales, parte general, CNPP)',
    'topic': 'derecho_penal_mexicano',
    'description': ('30 preguntas de delitos sexuales y cópula (CDMX, Edomex, CPF, Morelos; comparativas y '
                    'procesales), 10 de parte general/dogmática y 10 del CNPP. Respuestas basadas en el texto del '
                    'corpus al 2026-09-30. Querétaro no está en el corpus: esas preguntas miden que no se invente.'),
    'questions': Q,
}, ensure_ascii=False, indent=1))
print(f'{len(Q)} preguntas · {sum(len(x["components"]) for x in Q)} componentes → {OUT}')
