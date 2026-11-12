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
from datetime import datetime
from pathlib import Path

import yaml

from consulta.bench import fila as correr_caso, resumen
from consulta.catalogo import md5_de
from consulta.ia import ConsultaIA
from shared.db import connect
from shared.llm_client import LlamaClient

AQUI = Path(__file__).resolve().parent


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
            x = correr_caso(caso, catalogo, ia)
            f.write(json.dumps(x, ensure_ascii=False) + '\n')
            filas.append(x)
            print(f"{caso['id']:28} tipos {'✓' if x['tipos'] else '✗'} · datos "
                  f"{sum(v == 'acierta' for v in x['datos'].values())}/{len(x['datos'])} · reglas "
                  f"{'✓' if not x['reglas_faltan'] and not x['reglas_de_mas'] else '✗'} · {x['n_preguntas']} preguntas"
                  f"{' (+' + str(x['preguntas_de_mas']) + ')' if x['preguntas_de_mas'] else ''} · {x['segundos']} s", flush=True)

    n, r = len(filas), resumen(filas)
    out = [f'# Benchmark de la consulta · catálogo {md5} · {datetime.now():%Y-%m-%d %H:%M}', '',
           f'{n} casos (casos.yaml).', '',
           '| Medida | Resultado |', '|---|---|',
           f'| Llega a orientar | {r["orienta"]}/{n} |',
           f'| Tipo de caso correcto | {r["tipos"]}/{n} |',
           f'| Datos del expediente correctos | {r["datos_acierta"]}/{r["datos_total"]} '
           f'(faltan {r["datos_falta"]}, equivocados {r["datos_equivocado"]}) |',
           f'| Reglas correctas | {r["reglas"]}/{n} |',
           f'| Preguntas antes de orientar (promedio) | {r["preguntas_promedio"]:.1f} |',
           f'| Casos con más preguntas de las esperadas | {r["preguntas_de_mas"]}/{n} |', '',
           '## Datos con error', ''] + [f'- {k}: {v}' for k, v in r['datos_con_error'].items()] + ['', '## Por caso', '',
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
