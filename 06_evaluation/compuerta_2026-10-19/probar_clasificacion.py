"""¿Depende del estado? ¿Es delito federal? Mide esas dos decisiones del filtro de jurisdicción contra el LLM real,
con 25 frases escritas para esta prueba (NO están en el set 14 ni en las instrucciones del filtro). Se corre en el
servidor:  python probar_clasificacion.py"""
import json, os, sys
from pathlib import Path
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parents[1])); sys.path.insert(0, str(AQUI.parents[1] / 'apps' / 'rewrite_lab'))
from shared.llm_client import LlamaClient  # noqa: E402
import jurisdiction_gate as jg  # noqa: E402

CASOS = [  # (frase, depende_del_estado, delito_federal, tipo)
    ('Me vendieron un coche por Facebook y nunca me lo entregaron, ¿qué hago?', True, False, 'común'),
    ('Mi exsocio se quedó con el dinero del negocio que le confié.', True, False, 'común'),
    ('Me clonaron la tarjeta y sacaron dinero de mi cuenta.', True, False, 'común'),
    ('Un compañero de la escuela me pegó y me rompió la nariz.', True, False, 'común'),
    ('Mi vecino envenenó a mi perro.', True, False, 'común'),
    ('Mi ex se llevó a mis hijos y no me deja verlos.', True, False, 'común'),
    ('Un señor me tocó sin mi permiso en el camión.', True, False, 'común'),
    ('Me grafitearon la fachada de la casa.', True, False, 'común'),
    ('Mi jefe me manda mensajes sexuales y me presiona.', True, False, 'común'),
    ('Atropellaron a mi hermano y el conductor huyó.', True, False, 'común'),
    ('¿Cuánto tiempo puede estar detenida una persona antes de que la vea un juez?', False, False, 'procedimiento'),
    ('¿Puedo pedirle al Ministerio Público copia de la carpeta de investigación?', False, False, 'procedimiento'),
    ('¿Qué es una audiencia de vinculación a proceso?', False, False, 'procedimiento'),
    ('Si me acusan de un delito, ¿tengo derecho a un abogado gratis?', False, False, 'procedimiento'),
    ('¿Qué es la reparación del daño para la víctima?', False, False, 'procedimiento'),
    ('Me agarraron con una pistola de uso exclusivo del Ejército, ¿qué pena es?', False, True, 'federal'),
    ('Mi tío metió mercancía de contrabando por la aduana.', False, True, 'federal'),
    ('Un funcionario del SAT me pidió dinero para no multarme.', False, True, 'federal'),
    ('Creo que en un negocio de mi colonia están lavando dinero.', False, True, 'federal'),
    ('Me ofrecieron dinero por mi voto en las elecciones federales.', False, True, 'federal'),
    ('Detuvieron a mi primo con varios kilos de cocaína en la frontera.', False, True, 'federal'),
    ('Me hablan diciendo que tienen a mi hijo y piden un depósito para soltarlo.', False, False, 'ley general'),
    ('Unos tipos le cobran cuota a mi negocio cada semana.', False, False, 'ley general'),
    ('Desaparecieron a mi hermano y la policía no hace nada.', False, False, 'ley general'),
    ('Torturaron a mi hijo en la delegación para que confesara.', False, False, 'ley general'),
]

# Ronda 2 (2026-10-19): las 25 de arriba ya NO son una prueba limpia: al pasar de «sí/no» a «tipo», las categorías
# de las instrucciones se escribieron mirando sus fallas. Estas 19 se escribieron DESPUÉS y no aparecen en las
# instrucciones (ninguna de sus conductas se nombra ahí).
NUEVAS = [
    ('Mi cuñado me pidió prestado el coche y lo vendió sin decirme.', True, False, 'común'),
    ('Mi expareja publicó en Facebook que soy ladrona y es mentira.', True, False, 'común'),
    ('El perro de mi vecino mordió a mi hijo.', True, False, 'común'),
    ('Me quitaron la bicicleta a punta de cuchillo.', True, False, 'común'),
    ('Mi hija de 15 años anda con un hombre de 25.', True, False, 'común'),
    ('Un trabajador se cayó en la obra y murió porque no le dieron equipo de seguridad.', True, False, 'común'),
    ('¿Me pueden detener sin una orden de un juez?', False, False, 'procedimiento'),
    ('¿Qué significa que a alguien lo vinculen a proceso?', False, False, 'procedimiento'),
    ('¿Cuánto tarda normalmente un juicio oral?', False, False, 'procedimiento'),
    ('¿Puedo grabar mi declaración ante el Ministerio Público?', False, False, 'procedimiento'),
    ('Una señora me dio un billete falso en el mercado.', False, True, 'federal'),
    ('Mi vecino tiene un taller clandestino de cohetes y pólvora.', False, True, 'federal'),
    ('Están talando árboles dentro de una reserva natural protegida.', False, True, 'federal'),
    ('Un elemento de la Guardia Nacional me golpeó en un retén.', False, True, 'federal'),
    ('Encontraron a mi prima trabajando contra su voluntad, la tenían encerrada.', False, False, 'ley general'),
    ('Unos hombres armados se llevaron a mi papá y no sabemos nada de él.', False, False, 'ley general'),
    ('Me llamaron diciendo que eran de un cártel y que si no pago lastiman a mi familia.', False, False, 'ley general'),
    ('Golpearon a mi hijo en la patrulla para que firmara una declaración.', False, False, 'ley general'),
    ('Me quieren obligar a vender droga en mi colonia o me matan.', False, False, 'ley general'),
]

def main():
    llm = LlamaClient(url=os.environ.get('LLM_URL', 'http://127.0.0.1:1237'))
    res, por_tipo = [], {}
    for frase, dep, fed, tipo in [(f, d, x, t) for f, d, x, t in CASOS] + [(f, d, x, t + ' (nueva)') for f, d, x, t in NUEVAS]:
        ex = jg.extraer_lugares(frase, llm)
        ok_dep, ok_fed = ex['depende_del_estado'] == dep, ex['delito_federal'] == fed
        por_tipo.setdefault(tipo, []).append((ok_dep, ok_fed))
        res.append({'frase': frase, 'tipo': tipo, 'esperado': {'depende': dep, 'federal': fed},
                    'obtenido': {'depende': ex['depende_del_estado'], 'federal': ex['delito_federal']}, 'raw': ex['raw']})
        if not (ok_dep and ok_fed):
            print(f'✗ [{tipo}] {frase}\n    esperado depende={dep} federal={fed} · obtuvo depende={ex["depende_del_estado"]} federal={ex["delito_federal"]}')
    print()
    for tipo, v in por_tipo.items():
        print(f'{tipo:14s} depende {sum(a for a, _ in v)}/{len(v)} · federal {sum(b for _, b in v)}/{len(v)}')
    todos = [x for v in por_tipo.values() for x in v]
    print(f'TOTAL          depende {sum(a for a, _ in todos)}/{len(todos)} · federal {sum(b for _, b in todos)}/{len(todos)} · ambas {sum(a and b for a, b in todos)}/{len(todos)}')
    (AQUI / 'clasificacion_resultados.json').write_text(json.dumps(res, ensure_ascii=False, indent=1))

if __name__ == '__main__':
    main()
