"""Set «Jurisdicción · un solo estado»: preguntas en lenguaje cotidiano que dicen UN estado. Mide si la respuesta
fundamenta SOLO con el código de ese estado (+ leyes federales/generales/CNPP), aunque la búsqueda traiga otros.
Artículos verificados en el corpus el 2026-10-17 (capítulo del delito en cada código). Genera set_jurisdiccion.json."""
import json
CODIGO = {'CDMX': 'Código Penal de la Ciudad de México', 'QRO': 'Código Penal del Estado de Querétaro',
          'EDOMEX': 'Código Penal del Estado de México', 'MOR': 'Código Penal para el Estado de Morelos'}
LUGAR = {'CDMX': 'la Ciudad de México', 'QRO': 'Querétaro', 'EDOMEX': 'el Estado de México', 'MOR': 'Morelos'}
OTROS = {k: ', '.join(LUGAR[o].replace('la ', '').replace('el ', '') for o in LUGAR if o != k) for k in LUGAR}
# (estado, delito, artículo, pregunta)
P = [
 ('CDMX', 'robo', '220', 'Me robaron el celular en la calle en la Ciudad de México, sin golpes ni armas. Valía como 8 mil pesos. ¿Es delito y cuánta cárcel le pueden dar?'),
 ('CDMX', 'fraude', '230', 'En la Ciudad de México le pagué a alguien por internet una computadora que nunca me entregó y ya no me contesta. ¿Qué delito es?'),
 ('CDMX', 'amenazas', '209', 'Vivo en la Ciudad de México y un vecino me dijo que me va a golpear si vuelvo a estacionarme frente a su casa. ¿Eso es delito?'),
 ('CDMX', 'violencia familiar', '200', 'Mi pareja y yo vivimos en la Ciudad de México; me insulta y me empuja seguido. ¿Qué dice la ley penal?'),
 ('CDMX', 'acoso con jerarquía', '179', 'Trabajo en la Ciudad de México y quien me supervisa me manda mensajes con insinuaciones sexuales. ¿Es delito?'),
 ('CDMX', 'imágenes íntimas', '181 Quintus', 'En la Ciudad de México mi expareja subió a redes sociales fotos íntimas mías sin mi permiso. ¿Qué puedo hacer?'),
 ('CDMX', 'allanamiento', '210', 'Alguien se metió a mi casa en la Ciudad de México sin permiso mientras no estaba, aunque no se llevó nada. ¿Es delito?'),
 ('CDMX', 'despojo', '237', 'En la Ciudad de México una persona se metió a vivir a mi terreno y no se quiere salir. ¿Qué delito comete?'),
 ('QRO', 'robo', '182', 'En Querétaro me sacaron la cartera en el camión sin que me diera cuenta; traía 3 mil pesos. ¿Qué pena tiene eso?'),
 ('QRO', 'fraude', '193', 'Vivo en Querétaro y le di un anticipo a alguien para rentarme un departamento que resultó no ser suyo. ¿Qué delito es?'),
 ('QRO', 'violencia familiar', '217 Bis', 'En Querétaro mi hermano me grita, me amenaza y me ha empujado varias veces en la casa donde vivimos. ¿Qué dice la ley penal?'),
 ('QRO', 'acoso sexual', '167 Bis', 'En Querétaro un compañero de la escuela me pide insistentemente favores sexuales aunque le digo que no. ¿Es delito?'),
 ('QRO', 'acoso con jerarquía', '167 Ter', 'Trabajo en Querétaro y quien me supervisa me dijo que me ayudaría a subir de puesto si salgo con esa persona. ¿Es delito?'),
 ('QRO', 'imágenes íntimas', '167 Quinquies', 'En Querétaro alguien con quien salí me amenaza con publicar unas fotos íntimas que yo le mandé. ¿Eso es delito?'),
 ('QRO', 'allanamiento', '158', 'En Querétaro un conocido entró a mi casa sin mi permiso cuando yo no estaba. ¿Qué delito es?'),
 ('QRO', 'despojo', '199', 'Tengo un terreno en Querétaro y unas personas lo ocuparon y pusieron una cerca. ¿Qué delito cometen?'),
 ('EDOMEX', 'robo', '287', 'En el Estado de México me quitaron la bicicleta afuera de la tienda. ¿Qué delito es y qué pena tiene?'),
 ('EDOMEX', 'fraude', '305', 'Vivo en el Estado de México y me vendieron un coche con papeles falsos. ¿Qué delito es?'),
 ('EDOMEX', 'violencia familiar', '218', 'En el Estado de México mi pareja me controla el dinero, me insulta y a veces me pega. ¿Qué dice la ley penal?'),
 ('EDOMEX', 'acoso con jerarquía', '269', 'Trabajo en el Estado de México y mi jefe me presiona para tener una relación sexual a cambio de no despedirme. ¿Es delito?'),
 ('EDOMEX', 'imágenes íntimas', '269 Bis', 'En el Estado de México alguien compartió en un grupo de WhatsApp un video íntimo mío sin mi consentimiento. ¿Qué delito es?'),
 ('EDOMEX', 'allanamiento', '268', 'En el Estado de México mi casero entró a mi departamento sin avisar ni pedir permiso. ¿Es delito?'),
 ('EDOMEX', 'despojo', '308', 'En el Estado de México un familiar cambió la chapa de mi casa y ya no me deja entrar. ¿Qué delito es?'),
 ('MOR', 'robo', '174', 'En Morelos me robaron una bocina de mi coche estacionado. ¿Qué pena tiene ese delito?'),
 ('MOR', 'fraude', '188', 'En Morelos pagué un curso que nunca se dio y la persona desapareció con el dinero. ¿Qué delito es?'),
 ('MOR', 'amenazas', '147', 'En Morelos una persona me dijo por mensaje que me va a hacer daño si no le pago lo que dice que le debo. ¿Es delito?'),
 ('MOR', 'violencia familiar', '202 Bis', 'En Morelos mi padrastro me insulta y me golpea seguido en la casa. ¿Qué dice la ley penal?'),
 ('MOR', 'acoso con jerarquía', '158', 'Trabajo en Morelos y la persona que me supervisa me hace comentarios sexuales y me presiona para salir. ¿Es delito?'),
 ('MOR', 'imágenes íntimas', '150 Bis', 'En Morelos alguien publicó en Facebook fotos íntimas mías sin mi permiso. ¿Qué delito es?'),
 ('MOR', 'allanamiento', '149', 'En Morelos un vecino se metió a mi patio y a mi casa sin permiso. ¿Qué delito es?'),
 ('MOR', 'despojo', '184', 'En Morelos alguien ocupó un terreno de mi familia y dice que ahora es suyo. ¿Qué delito comete?'),
]
qs = []
for est, delito, art, pregunta in P:
    qs.append(dict(
        question=pregunta, difficulty='facil',
        expected_answer=f'Los hechos ocurrieron en {LUGAR[est]}, así que se rige por el {CODIGO[est]}: {delito}, art. {art}.',
        notes=f'jurisdiccion · estado={est} · delito={delito}',
        components=[
            dict(kind='must', weight=1, text=f'Cita el art. {art} del {CODIGO[est]}'),
            dict(kind='should', weight=1, text=f'Explica que se aplica la ley de {LUGAR[est]} porque ahí ocurrieron los hechos'),
            dict(kind='must_not', weight=1, text=f'Presenta como aplicable al caso un artículo del código penal de otra entidad ({OTROS[est]})'),
        ]))
s = dict(name='Jurisdicción · un solo estado (31)', topic='derecho_penal_mexicano',
         description=('31 preguntas en lenguaje cotidiano que dicen UN estado (CDMX 8, Querétaro 8, Edomex 7, Morelos 8; '
                      '8 delitos). Mide si la respuesta fundamenta solo con el código de ese estado. Artículos '
                      'verificados en el corpus el 17-oct-2026. Creado a partir de los hallazgos del estudio de usuarios.'),
         judge_notes=('Mencionar otra entidad solo para decir que NO aplica, o para comparar explícitamente, NO cuenta como '
                      '«presentar como aplicable». Citar el Código Penal Federal, el CNPP o una ley general NO es otra '
                      'entidad. El artículo correcto cuenta como presente aunque se escriba «artículo», «art.» o en '
                      'mayúsculas (p. ej. «167 QUINQUIES»).'),
         questions=qs)
json.dump(s, open('set_jurisdiccion.json', 'w'), ensure_ascii=False, indent=1)
print(len(qs), 'preguntas')
