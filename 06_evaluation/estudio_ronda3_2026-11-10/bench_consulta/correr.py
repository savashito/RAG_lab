"""
Benchmark de la consulta (ronda 3): simula cada caso de casos.yaml con la máquina de estados (consulta/maquina.py), el
LLM de la app (clasificar y extraer) y el catálogo de la base, hasta llegar a la orientación, y mide:

  · tipos      los tipos de caso esperados quedaron en el expediente
  · datos      cada dato esperado tiene el valor esperado (por dato: acierta, falta o equivocado)
  · reglas     las reglas esperadas aplican y las de `reglas_no` no
  · preguntas  cuántas preguntas hizo antes de orientar (y si pasó de max_preguntas)
  · orienta    llegó a la orientación en a lo más 10 mensajes de la persona

No redacta la orientación ni las preguntas con el LLM (eso no cambia el expediente). Corre donde la app alcanza al LLM
y a la base (en producción):

    cd ~/apps/RAG_lab && set -a && . apps/rewrite_lab/.env; set +a
    PYTHONPATH=apps/rewrite_lab:. .venv/bin/python 06_evaluation/estudio_ronda3_2026-11-10/bench_consulta/correr.py [--caso ID]

Escribe resultados/<fecha>_<md5 del catálogo>.jsonl (un caso por línea) y .md (resumen). Los casos son inventados:
los resultados se pueden commitear.
"""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import yaml

from consulta import expediente as E
from consulta import maquina as M
from consulta.catalogo import md5_de
from consulta.ia import ConsultaIA
from shared.db import connect
from shared.llm_client import LlamaClient

AQUI = Path(__file__).resolve().parent
MAX_MENSAJES = 10
NO_SE = 'no sé'


def respuesta(caso: dict, dato: str, veces: Counter) -> str:
    """Lo que contesta la persona cuando le piden `dato` (una lista: una respuesta por cada vez)."""
    r = (caso.get('respuestas') or {}).get(dato)
    if isinstance(r, list):
        r = r[min(veces[dato], len(r) - 1)] if r else None
    veces[dato] += 1
    return str(r) if r is not None else NO_SE


def simular(caso: dict, catalogo: dict, ia) -> dict:
    estado = exp = None
    historial, preguntas, veces = [], [], Counter()
    evento = {'tipo': 'mensaje', 'texto': caso['relato']}
    salida, t0 = {}, time.time()
    for n in range(MAX_MENSAJES):
        estado, exp, salida, _ = M.turno(estado, exp, {**evento, 'historial': list(historial)}, catalogo, ia)
        if evento['tipo'] == 'mensaje':
            historial.append({'role': 'user', 'content': evento['texto']})
        if salida['tipo'] == 'orientar':
            break
        if salida['tipo'] == 'elegir_tipo':                  # elige el primer tipo esperado que esté entre las opciones
            ids = [o['id'] for o in salida['opciones']]
            valor = next((t for t in caso['esperado'].get('tipos', []) if t in ids), M.OTRO)
            historial.append({'role': 'assistant', 'content': salida['texto']})
            preguntas.append('(elegir tipo)')
            evento = {'tipo': 'elegir_tipo', 'valor': valor}
            continue
        historial.append({'role': 'assistant', 'content': salida['texto']})
        preguntas.append(salida['dato'])
        evento = {'tipo': 'mensaje', 'texto': respuesta(caso, salida['dato'], veces)}
    return {'estado': estado, 'expediente': exp, 'salida': salida, 'preguntas': preguntas,
            'conversacion': historial, 'segundos': round(time.time() - t0, 1)}


def calificar(caso: dict, r: dict) -> dict:
    esp, exp, s = caso['esperado'], r['expediente'] or {}, r['salida']
    reglas = set(s.get('reglas') or []) if s.get('tipo') == 'orientar' else set()
    datos = {}
    for k, v in (esp.get('datos') or {}).items():
        got = exp.get('datos', {}).get(k)
        datos[k] = 'acierta' if got is not None and str(got) == str(v) else 'falta' if got is None else f'equivocado ({got})'
    preguntas = [p for p in r['preguntas'] if p != '(elegir tipo)']
    return {'orienta': s.get('tipo') == 'orientar',
            'tipos': set(esp.get('tipos', [])) <= set(exp.get('tipos_caso', [])),
            'datos': datos,
            'reglas_faltan': sorted(set(esp.get('reglas', [])) - reglas),
            'reglas_de_mas': sorted(set(esp.get('reglas_no', [])) & reglas),
            'n_preguntas': len(preguntas),
            'preguntas_de_mas': max(0, len(preguntas) - esp['max_preguntas']) if 'max_preguntas' in esp else 0}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--caso', nargs='*', help='solo estos ids')
    args = ap.parse_args()
    casos = yaml.safe_load((AQUI / 'casos.yaml').read_text())['casos']
    if args.caso:
        casos = [c for c in casos if c['id'] in args.caso]
    with connect() as c, c.cursor() as cur:
        cur.execute('SELECT doc FROM consulta_catalogo WHERE id = 1')
        catalogo = cur.fetchone()[0]
    md5 = md5_de(catalogo)[:8]
    ia = ConsultaIA(LlamaClient())
    salida = AQUI / 'resultados' / f'{datetime.now():%Y-%m-%d_%H%M}_{md5}'
    salida.parent.mkdir(exist_ok=True)
    filas = []
    with open(salida.with_suffix('.jsonl'), 'w') as f:
        for caso in casos:
            r = simular(caso, catalogo, ia)
            cal = calificar(caso, r)
            fila = {'id': caso['id'], **cal, 'tipos_caso': r['expediente'].get('tipos_caso'),
                    'expediente': r['expediente'].get('datos'), 'reglas': r['salida'].get('reglas'),
                    'preguntas': r['preguntas'], 'conversacion': r['conversacion'], 'segundos': r['segundos']}
            f.write(json.dumps(fila, ensure_ascii=False) + '\n')
            filas.append(fila)
            print(f"{caso['id']:28} tipos {'✓' if cal['tipos'] else '✗'} · datos "
                  f"{sum(v == 'acierta' for v in cal['datos'].values())}/{len(cal['datos'])} · reglas "
                  f"{'✓' if not cal['reglas_faltan'] and not cal['reglas_de_mas'] else '✗'} · {cal['n_preguntas']} preguntas"
                  f"{' (+' + str(cal['preguntas_de_mas']) + ')' if cal['preguntas_de_mas'] else ''} · {r['segundos']} s", flush=True)

    n = len(filas)
    datos = Counter(v.split(' ')[0] for x in filas for v in x['datos'].values())
    por_dato = Counter()
    for x in filas:
        for k, v in x['datos'].items():
            if v != 'acierta':
                por_dato[k] += 1
    out = [f'# Benchmark de la consulta · catálogo {md5} · {datetime.now():%Y-%m-%d %H:%M}', '',
           f'{n} casos (casos.yaml).', '',
           '| Medida | Resultado |', '|---|---|',
           f'| Llega a orientar | {sum(x["orienta"] for x in filas)}/{n} |',
           f'| Tipo de caso correcto | {sum(x["tipos"] for x in filas)}/{n} |',
           f'| Datos del expediente correctos | {datos["acierta"]}/{sum(datos.values())} '
           f'(faltan {datos["falta"]}, equivocados {datos["equivocado"]}) |',
           f'| Reglas correctas | {sum(not x["reglas_faltan"] and not x["reglas_de_mas"] for x in filas)}/{n} |',
           f'| Preguntas antes de orientar (promedio) | {sum(x["n_preguntas"] for x in filas) / max(n, 1):.1f} |',
           f'| Casos con más preguntas de las esperadas | {sum(bool(x["preguntas_de_mas"]) for x in filas)}/{n} |', '',
           '## Datos con error', ''] + [f'- {k}: {v}' for k, v in por_dato.most_common()] + ['', '## Por caso', '',
           '| Caso | Tipos | Datos | Reglas | Preguntas |', '|---|---|---|---|---|']
    for x in filas:
        mal = [f'{k}: {v}' for k, v in x['datos'].items() if v != 'acierta']
        reglas = ([f'faltan {", ".join(x["reglas_faltan"])}'] if x['reglas_faltan'] else []) + \
                 ([f'de más {", ".join(x["reglas_de_mas"])}'] if x['reglas_de_mas'] else [])
        out.append(f'| {x["id"]} | {"✓" if x["tipos"] else "✗ " + ", ".join(x["tipos_caso"] or [])} | '
                   f'{"✓" if not mal else "; ".join(mal)} | {"✓" if not reglas else "; ".join(reglas)} | '
                   f'{x["n_preguntas"]}: {", ".join(x["preguntas"])} |')
    salida.with_suffix('.md').write_text('\n'.join(out) + '\n')
    print('\n'.join(out[:12]))
    print(f'→ {salida}.jsonl y .md')


if __name__ == '__main__':
    main()
