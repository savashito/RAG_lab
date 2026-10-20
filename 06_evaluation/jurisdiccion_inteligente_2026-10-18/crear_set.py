"""Set «Jurisdicción inteligente»: ¿el asistente sabe CUÁNDO pedir el estado y cuándo no?

Hallazgo del estudio de usuarios: si la persona no dice el estado y el asistente responde con el código de algún estado,
la persona asume que ese código le aplica. El comportamiento correcto depende de lo que dio la persona:

  A sin_lugar        no dice dónde              → pide el estado; NO cita ningún código estatal
  B un_estado        dice un estado             → responde solo con ese código (+ leyes nacionales); no vuelve a preguntar
  C lugar_indirecto  dice solo ciudad/municipio → deduce el estado y responde con su código
  D comparacion      pide comparar estados      → responde CADA estado pedido, y solo esos; no pide elegir uno
  E nacional         pregunta de ley nacional   → responde (CNPP, ley general) sin pedir el estado
  F fuera_corpus     estado que no está en la base → dice que no tiene ese código; no lo sustituye por otro estado

Artículos estatales verificados en el corpus el 2026-10-17 (set 13); los nacionales se verifican antes de importar
(resolve_gold). Las notas de cada pregunta («jur2 · cat=… · estados=…») permiten el análisis sin LLM por categoría.
Genera set_jurisdiccion_inteligente.json."""
import json
CODIGO = {'CDMX': 'Código Penal de la Ciudad de México', 'QRO': 'Código Penal del Estado de Querétaro',
          'EDOMEX': 'Código Penal del Estado de México', 'MOR': 'Código Penal para el Estado de Morelos'}
NOMBRE = {'CDMX': 'la Ciudad de México', 'QRO': 'Querétaro', 'EDOMEX': 'el Estado de México', 'MOR': 'Morelos'}
ETIQUETA = {'CDMX': 'CDMX', 'QRO': 'Querétaro', 'EDOMEX': 'CPEM', 'MOR': 'Morelos'}   # etiquetas de codes_in
ART = {   # (estado, delito) → artículo verificado
 ('CDMX', 'robo'): '220', ('CDMX', 'fraude'): '230', ('CDMX', 'amenazas'): '209', ('CDMX', 'violencia familiar'): '200',
 ('CDMX', 'hostigamiento'): '179', ('CDMX', 'imágenes íntimas'): '181 Quintus', ('CDMX', 'allanamiento'): '210', ('CDMX', 'despojo'): '237',
 ('QRO', 'robo'): '182', ('QRO', 'fraude'): '193', ('QRO', 'violencia familiar'): '217 Bis', ('QRO', 'acoso'): '167 Bis',
 ('QRO', 'hostigamiento'): '167 Ter', ('QRO', 'imágenes íntimas'): '167 Quinquies', ('QRO', 'allanamiento'): '158', ('QRO', 'despojo'): '199',
 ('EDOMEX', 'robo'): '287', ('EDOMEX', 'fraude'): '305', ('EDOMEX', 'violencia familiar'): '218', ('EDOMEX', 'hostigamiento'): '269',
 ('EDOMEX', 'imágenes íntimas'): '211 Ter', ('EDOMEX', 'allanamiento'): '268', ('EDOMEX', 'despojo'): '308',
 ('MOR', 'robo'): '174', ('MOR', 'fraude'): '188', ('MOR', 'amenazas'): '147', ('MOR', 'violencia familiar'): '202 Bis',
 ('MOR', 'hostigamiento'): '158', ('MOR', 'imágenes íntimas'): '150 Bis', ('MOR', 'allanamiento'): '149', ('MOR', 'despojo'): '184',
}
ESTATALES = 'Ciudad de México, Querétaro, Estado de México, Morelos u otro estado'
qs = []
def Q(cat, pregunta, comps, estados=(), expected='', extra=''):
    notas = f"jur2 · cat={cat}" + (f" · estados={','.join(ETIQUETA[e] for e in estados)}" if estados else '') + (f' · {extra}' if extra else '')
    qs.append(dict(question=pregunta, difficulty='mediano' if cat in ('comparacion', 'lugar_indirecto', 'fuera_corpus') else 'facil',
                   expected_answer=expected, notes=notas, components=comps))
must = lambda t: dict(kind='must', weight=1, text=t)
should = lambda t: dict(kind='should', weight=1, text=t)
error = lambda t: dict(kind='must_not', weight=1, text=t)

# ── A. sin lugar: debe pedir el estado y no citar ningún código estatal ─────────────────────────────────────────
for delito, p in [
    ('robo', 'Me robaron el celular en la calle, sin golpes ni armas. ¿Es delito y cuánta cárcel le pueden dar?'),
    ('fraude', 'Le pagué por internet a alguien una computadora que nunca me entregó. ¿Qué delito es?'),
    ('amenazas', 'Un vecino me dijo que me va a golpear si vuelvo a estacionarme frente a su casa. ¿Eso es delito?'),
    ('violencia familiar', 'Mi pareja me insulta y me empuja seguido en la casa. ¿Qué dice la ley penal?'),
    ('hostigamiento', 'La persona que me supervisa en el trabajo me manda mensajes con insinuaciones sexuales. ¿Es delito?'),
    ('imágenes íntimas', 'Mi expareja subió a redes sociales fotos íntimas mías sin mi permiso. ¿Qué puedo hacer?'),
    ('allanamiento', 'Alguien se metió a mi casa sin permiso mientras no estaba, aunque no se llevó nada. ¿Es delito?'),
    ('despojo', 'Una persona se metió a vivir a mi terreno y no se quiere salir. ¿Qué delito comete?'),
    ('robo', 'Me quitaron la bicicleta afuera de una tienda. ¿Qué pena tiene el que se la llevó?'),
    ('violencia familiar', 'Mi hermano me grita, me amenaza y me ha empujado varias veces en la casa donde vivimos. ¿Lo puedo denunciar?'),
    ('imágenes íntimas', 'Alguien con quien salí me amenaza con publicar unas fotos íntimas que yo le mandé. ¿Eso es delito?'),
    ('fraude', 'Di un anticipo para rentar un departamento y resultó que el que me lo rentó no era el dueño. ¿Qué puedo hacer?'),
]:
    Q('sin_lugar', p, [
        must('Pregunta en qué estado (entidad federativa) ocurrieron los hechos'),
        should('Explica brevemente que la respuesta depende del estado porque cada estado tiene su propio código penal'),
        error(f'Cita artículos del código penal de algún estado ({ESTATALES})'),
    ], expected='La persona no dijo dónde ocurrió: lo correcto es preguntar en qué estado ocurrió antes de citar artículos de un código penal estatal.',
      extra=f'delito={delito}')

# ── B. un estado: responde solo con ese código ─────────────────────────────────────────────────────────────────
for est, delito, p in [
    ('CDMX', 'fraude', 'En la Ciudad de México me vendieron un celular por internet y nunca me llegó. ¿Qué delito es?'),
    ('CDMX', 'allanamiento', 'Vivo en la Ciudad de México y mi exroomie entró a mi departamento sin permiso. ¿Es delito?'),
    ('QRO', 'robo', 'En Querétaro me robaron la mochila en el transporte público. ¿Qué pena tiene?'),
    ('QRO', 'despojo', 'Tengo una casa en Querétaro y unas personas se metieron a vivir sin mi permiso. ¿Qué delito cometen?'),
    ('EDOMEX', 'violencia familiar', 'En el Estado de México mi papá me pega y me insulta. ¿Qué dice la ley penal?'),
    ('EDOMEX', 'imágenes íntimas', 'En el Estado de México alguien está pasando por WhatsApp un video íntimo mío. ¿Qué delito es?'),
    ('MOR', 'amenazas', 'En Morelos un cobrador me dijo que me va a lastimar si no le pago. ¿Es delito?'),
    ('MOR', 'hostigamiento', 'Trabajo en Morelos y mi jefa me presiona para salir con ella a cambio de un aumento. ¿Es delito?'),
]:
    a = ART[(est, delito)]
    Q('un_estado', p, [
        must(f'Cita el art. {a} del {CODIGO[est]}'),
        error('Presenta como aplicable al caso un artículo del código penal de otra entidad'),
        error('Pide a la persona que diga en qué estado ocurrieron los hechos, aunque ya lo dijo'),
    ], estados=[est], expected=f'Ocurrió en {NOMBRE[est]}: se rige por el {CODIGO[est]}, art. {a} ({delito}).', extra=f'delito={delito}')

# ── C. solo ciudad o municipio: debe deducir el estado ─────────────────────────────────────────────────────────
for est, lugar, delito, p in [
    ('CDMX', 'Coyoacán', 'robo', 'En Coyoacán me robaron la cartera en el mercado. ¿Qué pena tiene eso?'),
    ('CDMX', 'Iztapalapa', 'amenazas', 'En Iztapalapa un vecino me amenazó con lastimarme. ¿Es delito?'),
    ('EDOMEX', 'Ecatepec', 'fraude', 'En Ecatepec me vendieron un coche con papeles falsos. ¿Qué delito es?'),
    ('EDOMEX', 'Toluca', 'allanamiento', 'En Toluca mi casero entró a mi casa sin avisar. ¿Eso es delito?'),
    ('MOR', 'Cuernavaca', 'despojo', 'En Cuernavaca alguien ocupó un terreno de mi familia y dice que ahora es suyo. ¿Qué delito comete?'),
    ('MOR', 'Cuautla', 'imágenes íntimas', 'En Cuautla alguien publicó fotos íntimas mías en Facebook. ¿Qué delito es?'),
    ('QRO', 'San Juan del Río', 'violencia familiar', 'En San Juan del Río mi pareja me golpea y me controla el dinero. ¿Qué dice la ley penal?'),
    ('QRO', 'Corregidora', 'hostigamiento', 'Trabajo en Corregidora y mi supervisor me dijo que me sube de puesto si salgo con él. ¿Es delito?'),
]:
    a = ART[(est, delito)]
    Q('lugar_indirecto', p, [
        must(f'Cita el art. {a} del {CODIGO[est]}'),
        should(f'Identifica que {lugar} está en {NOMBRE[est]}'),
        error('Presenta como aplicable al caso un artículo del código penal de otra entidad'),
    ], estados=[est], expected=f'{lugar} está en {NOMBRE[est]}: se rige por el {CODIGO[est]}, art. {a} ({delito}).',
      extra=f'delito={delito} · lugar={lugar}')

# ── D. comparación explícita: debe responder cada estado pedido, y solo esos ──────────────────────────────────
for ests, delito, p in [
    (['CDMX', 'QRO'], 'robo', '¿Cómo se castiga el robo en la Ciudad de México y en Querétaro?'),
    (['CDMX', 'EDOMEX'], 'fraude', '¿Qué diferencias hay entre el delito de fraude en la Ciudad de México y en el Estado de México?'),
    (['QRO', 'MOR'], 'violencia familiar', 'Compara cómo regulan la violencia familiar Querétaro y Morelos.'),
    (['EDOMEX', 'MOR'], 'hostigamiento', '¿El hostigamiento sexual en el trabajo se castiga igual en el Estado de México que en Morelos?'),
    (['CDMX', 'MOR'], 'imágenes íntimas', '¿Qué dice la ley de la Ciudad de México y la de Morelos sobre publicar fotos íntimas de alguien sin su permiso?'),
    (['QRO', 'EDOMEX'], 'despojo', 'Si alguien invade un terreno, ¿qué delito comete en Querétaro y cuál en el Estado de México?'),
    (['CDMX', 'QRO'], 'allanamiento', '¿Meterse a una casa sin permiso es delito en la Ciudad de México y en Querétaro? ¿Con qué pena?'),
    (['CDMX', 'EDOMEX', 'MOR'], 'robo', 'Compara la pena del robo simple en la Ciudad de México, el Estado de México y Morelos.'),
]:
    comps = [must(f'Cita el art. {ART[(e, delito)]} del {CODIGO[e]}') for e in ests]
    comps += [error('Pide a la persona que elija un solo estado en lugar de responder la comparación'),
              error('Presenta artículos del código penal de un estado que la pregunta no menciona')]
    Q('comparacion', p, comps, estados=ests,
      expected='Comparación pedida: ' + '; '.join(f'{CODIGO[e]}, art. {ART[(e, delito)]}' for e in ests) + '.', extra=f'delito={delito}')

# ── E. ley nacional o general: no hace falta el estado ────────────────────────────────────────────────────────
for ley, a, p in [
    ('Código Nacional de Procedimientos Penales', '146', 'Detuvieron a mi primo justo en el momento en que estaba robando. ¿Eso es flagrancia? ¿Qué dice la ley?'),
    ('Código Nacional de Procedimientos Penales', '148', 'Si detienen a alguien en flagrancia por un delito que se persigue por querella y la víctima no ha presentado la querella, ¿cuánto tiempo lo pueden tener detenido?'),
    ('Código Nacional de Procedimientos Penales', '187', '¿En qué delitos se puede llegar a un acuerdo con la víctima para terminar el proceso penal?'),
    ('Código Nacional de Procedimientos Penales', '256', '¿Qué es un criterio de oportunidad y en qué casos no se puede aplicar?'),
    ('Ley General para Prevenir, Investigar y Sancionar Delitos en Materia de Extorsión', '15', 'Alguien me exige dinero por teléfono amenazando con hacerle daño a mi familia. ¿Qué delito es y qué pena tiene?'),
    # 2026-10-19: 10 más (con 5 la categoría era muy ruidosa). Artículos verificados en el corpus ese día.
    ('Código Nacional de Procedimientos Penales', '113', 'Si me detiene la policía, ¿qué derechos tengo?'),
    ('Código Nacional de Procedimientos Penales', '109', 'Soy víctima de un delito y ya puse la denuncia. ¿Qué derechos tengo durante el proceso?'),
    ('Código Nacional de Procedimientos Penales', '155', '¿Qué medidas cautelares le puede poner el juez a la persona que me agredió mientras dura el juicio?'),
    ('Código Nacional de Procedimientos Penales', '167', '¿Para qué delitos procede la prisión preventiva oficiosa?'),
    ('Código Nacional de Procedimientos Penales', '191', '¿Qué es la suspensión condicional del proceso?'),
    ('Código Nacional de Procedimientos Penales', '201', 'Le ofrecieron a mi hermano un procedimiento abreviado. ¿Qué requisitos tiene?'),
    ('Código Nacional de Procedimientos Penales', '313', 'Detuvieron a mi papá y ya tuvo su primera audiencia. ¿En cuánto tiempo el juez decide si lo vinculan a proceso?'),
    ('Ley General para Prevenir y Sancionar los Delitos en Materia de Secuestro', '9', 'Se llevaron a mi hermano y nos piden dinero para soltarlo. ¿Qué delito es y qué pena tiene?'),
    ('Ley Federal Contra la Delincuencia Organizada', '2o', '¿Cuándo se considera que un grupo de personas es delincuencia organizada?'),
    ('Código Penal Federal', '400 Bis', '¿Qué es el lavado de dinero y qué pena tiene?'),
]:
    Q('nacional', p, [
        must(f'Cita el art. {a} de la {ley}' if ley.startswith('Ley') else f'Cita el art. {a} del {ley}'),
        error('Se niega a responder o exige saber el estado antes de responder, aunque la ley que aplica es nacional o general'),
        error(f'Presenta como aplicable el código penal de algún estado ({ESTATALES})'),
    ], expected=f'Es materia de una ley que aplica en todo el país: {ley}, art. {a}. No hace falta saber el estado.')

# ── F. estado que no está en la base: no debe sustituirlo por otro ───────────────────────────────────────────
for estado, p in [
    ('Puebla', 'En Puebla me robaron el celular en la calle. ¿Qué pena tiene ese delito?'),
    ('Jalisco', 'En Guadalajara le pagué a alguien un servicio que nunca hizo y desapareció con el dinero. ¿Qué delito es?'),
    ('Nuevo León', 'En Monterrey mi pareja me golpea seguido. ¿Qué dice la ley penal de Nuevo León?'),
    ('Oaxaca', 'En Oaxaca un vecino me amenazó con quemar mi casa. ¿Es delito?'),
    ('Yucatán', 'En Mérida alguien se metió a mi casa sin permiso. ¿Qué delito es?'),
    ('Veracruz', 'En Veracruz invadieron un terreno de mi familia. ¿Qué delito cometen?'),
]:
    Q('fuera_corpus', p, [
        must(f'Indica que no cuenta con el código penal de {estado} (no está en la información disponible)'),
        should(f'Recomienda consultar el código penal de {estado} o a una persona abogada de ese estado'),
        error('Presenta como aplicable un artículo del código penal de la Ciudad de México, Querétaro, Estado de México o Morelos'),
    ], expected=f'Ocurrió en {estado}, cuyo código penal no está en la base: lo correcto es decirlo y no usar el código de otro estado.',
      extra=f'estado_fuera={estado}')

s = dict(name='Jurisdicción inteligente · ¿cuándo pedir el estado? (57)', topic='derecho_penal_mexicano',
         description=('57 preguntas en 6 categorías: sin lugar (12, debe pedir el estado y no citar códigos estatales), un estado (8), '
                      'solo ciudad o municipio (8, debe deducir el estado), comparación (8, debe responder cada estado pedido), '
                      'ley nacional (15, no debe pedir el estado) y estado fuera de la base (6, no debe sustituirlo por otro). '
                      'Nace del estudio de usuarios: si el asistente responde con un estado que la persona no dijo, la persona '
                      'asume que le aplica. La categoría va en las notas de cada pregunta.'),
         judge_notes=('Mencionar un estado solo para explicar que la respuesta depende del estado, para preguntar cuál es, o para decir '
                      'que no aplica, NO cuenta como «citar» ni «presentar como aplicable» su código. Citar el Código Nacional de '
                      'Procedimientos Penales, el Código Penal Federal o una ley general NO es citar el código de un estado. '
                      '«Pregunta en qué estado…» cuenta como presente si la respuesta pide de cualquier forma la entidad, el estado o '
                      'el lugar donde ocurrieron los hechos. Un artículo cuenta como presente aunque se escriba «artículo», «art.» o en '
                      'mayúsculas.'),
         questions=qs)
json.dump(s, open('set_jurisdiccion_inteligente.json', 'w'), ensure_ascii=False, indent=1)
from collections import Counter
print(len(qs), dict(Counter(q['notes'].split('cat=')[1].split(' ')[0] for q in qs)))
