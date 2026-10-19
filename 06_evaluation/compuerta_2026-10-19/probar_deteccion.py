"""Detección de lugar de la compuerta (jurisdiction_gate.extraer_lugares) contra el LLM real.

Casos: las 47 preguntas del set 14 (estado esperado según sus notas) + 20 frases de prueba que NO se
usaron al escribir el prompt de extracción. Mide si el conjunto de estados detectado es exactamente el
esperado. Se corre en el servidor (necesita el LLM en LLM_URL):

    cd ~/apps/RAG_lab/apps/rewrite_lab && ~/.local/bin/uv run python ../../06_evaluation/compuerta_2026-10-19/probar_deteccion.py
"""
import json
import os
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parents[1])); sys.path.insert(0, str(AQUI.parents[1] / 'apps' / 'rewrite_lab'))
from shared.llm_client import LlamaClient  # noqa: E402
import jurisdiction_gate as jg  # noqa: E402

ETIQ = {'CDMX': 'Ciudad de México', 'CPEM': 'Estado de México', 'Morelos': 'Morelos', 'Querétaro': 'Querétaro'}

def esperado_set14(notas):
    campos = dict(p.split('=', 1) for p in notas.split(' · ') if '=' in p)
    if 'estados' in campos:
        return {ETIQ[e] for e in campos['estados'].split(',')}
    if 'estado_fuera' in campos:
        return {jg.normalizar_estado(campos['estado_fuera'])}
    return set()

EXTRA = [   # (frase, estados esperados) — escritas para esta prueba, no vistas al diseñar el prompt
    ('Me asaltaron saliendo del metro Pantitlán, ¿qué hago?', {'Ciudad de México'}),
    ('Estoy en Neza y un vecino me rompió la ventana a pedradas.', {'Estado de México'}),
    ('En Xochimilco me cobraron de más en una trajinera y me amenazaron.', {'Ciudad de México'}),
    ('En Polanco me clonaron la tarjeta en un restaurante.', {'Ciudad de México'}),
    ('Vivo en Tlalnepantla y mi expareja publicó fotos mías sin permiso.', {'Estado de México'}),
    ('En Valle de Chalco me robaron la moto.', {'Estado de México'}),
    ('En Tepoztlán un guía de turistas me estafó.', {'Morelos'}),
    ('En Jiutepec me golpearon afuera de un bar.', {'Morelos'}),
    ('En Tequisquiapan me vendieron un terreno que no era del vendedor.', {'Querétaro'}),
    ('Me robaron la cartera en Pachuca.', {'Hidalgo'}),
    ('En Cancún me cobraron un tour que nunca existió.', {'Quintana Roo'}),
    ('Me extorsionaron por teléfono desde Monterrey.', {'Nuevo León'}),
    ('En Mérida me chocaron y el otro conductor huyó.', {'Yucatán'}),
    ('Me robaron en Los Cabos, en el hotel.', {'Baja California Sur'}),
    ('Me robaron el celular en Texas, ¿puedo denunciar en México?', set()),
    ('Aquí en mi colonia hay un señor que amenaza a todos.', set()),
    ('En la central de abastos me vendieron mercancía robada.', set()),
    ('¿Qué pena tiene el homicidio culposo según el Código Penal Federal?', set()),
    ('¿Es igual de grave el robo en Iztacalco que en Ecatepec?', {'Ciudad de México', 'Estado de México'}),
    ('Trabajo en Querétaro pero el fraude me lo hicieron en Celaya.', {'Querétaro', 'Guanajuato'}),
    # siglas y apodos (agregados tras la pregunta del usuario por «GLD»; «GLD» no es una sigla real)
    ('Me robaron el celular en GDL, ¿qué pena tiene?', {'Jalisco'}),
    ('Me robaron el celular en GLD, ¿qué pena tiene?', set()),
    ('Me asaltaron en Mty', {'Nuevo León'}),
    ('Me robaron en Cuerna', {'Morelos'}),
]

def main():
    llm = LlamaClient(url=os.environ.get('LLM_URL', 'http://127.0.0.1:1237'))
    s14 = json.loads((AQUI.parent / 'jurisdiccion_inteligente_2026-10-18' / 'set_jurisdiccion_inteligente.json').read_text())
    casos = [('set14', q['notes'].split('cat=')[1].split(' ')[0], q['question'], esperado_set14(q['notes']))
             for q in s14['questions']] + [('extra', 'extra', f, e) for f, e in EXTRA]
    res, ok = [], {}
    for fuente, cat, texto, esp in casos:
        ex = jg.extraer_lugares(texto, llm)
        got = {x['estado'] for x in ex['lugares'] if x['estado']}
        bien = got == esp
        ok.setdefault(cat, []).append(bien)
        res.append({'fuente': fuente, 'cat': cat, 'texto': texto, 'esperado': sorted(esp), 'detectado': sorted(got),
                    'bien': bien, 'via': ex['fuente'], 'lugares': ex['lugares'], 'raw': ex['raw']})
        sin_estado = [x['texto'] for x in ex['lugares'] if not x['estado']]
        res_extra = f' · sin estado: {sin_estado}' if sin_estado else ''
        if not bien or sin_estado:
            print(f'{"✓" if bien else "✗"} [{cat}] {texto[:90]}\n    esperado {sorted(esp)} · detectado {sorted(got)}{res_extra}')
    print()
    for cat, v in ok.items():
        print(f'{cat:16s} {sum(v)}/{len(v)}')
    tot = [b for v in ok.values() for b in v]
    print(f'TOTAL            {sum(tot)}/{len(tot)}')
    (AQUI / 'deteccion_resultados.json').write_text(json.dumps(res, ensure_ascii=False, indent=1))

if __name__ == '__main__':
    main()
