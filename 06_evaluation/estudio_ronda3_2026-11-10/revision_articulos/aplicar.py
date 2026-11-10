"""
Aplica a una copia del catálogo lo que salió de la revisión de artículos (sugerencias.json de comparar.py):

  · quita de cada regla los artículos en los que el LLM no está de acuerdo (derogados, no son delito, otra regla);
  · agrega a cada regla los artículos que el LLM le asigna (incluye los que movió desde otra regla), solo de la parte
    especial (LIBRO SEGUNDO): los de la parte general (penas, culpa, reparación) valen para todos los delitos;
  · las reglas que cambian y estaban en `borrador` pasan a `sugerida`. Una `confirmada` no se toca.

No aplica las condiciones `cuando` ni las reglas nuevas: eso lo revisa Karen.

    python3 aplicar.py CARPETA [--excluir cdmx:266]  →  CARPETA/catalogo_nuevo.json + resumen en pantalla
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from comparar import norm


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('carpeta', type=Path)
    ap.add_argument('--excluir', nargs='*', default=[], help='artículos que no se tocan: codigo:num')
    args = ap.parse_args()
    cat = json.loads((args.carpeta / 'catalogo.json').read_text())
    sug = json.loads((args.carpeta / 'sugerencias.json').read_text())
    assert sug['catalogo_md5'] == cat['md5'], 'sugerencias.json es de otra versión del catálogo'
    excluir = {(c, norm(n)) for c, n in (x.split(':', 1) for x in args.excluir)}
    ruta = {}
    for l in open(args.carpeta / 'resultados.jsonl'):
        r = json.loads(l)
        ruta[(r['codigo'], r['num'])] = r['ruta']
    doc = json.loads(json.dumps(cat['doc']))
    reglas = {r['id']: r for r in doc['reglas']}
    cuenta, cambiadas = Counter(), set()

    for rid, xs in sug['desacuerdo'].items():
        for x in xs:
            if x['motivo'] == 'no está en el corpus' or (x['codigo'], norm(x['num'])) in excluir:
                continue
            arts = reglas[rid]['articulos'].get(x['codigo'], [])
            antes = len(arts)
            reglas[rid]['articulos'][x['codigo']] = [a for a in arts if norm(a) != norm(x['num'])]
            if len(reglas[rid]['articulos'][x['codigo']]) < antes:
                cuenta['quitados'] += 1
                cambiadas.add(rid)
    for rid, xs in sug['agregar'].items():
        for x in xs:
            if (x['codigo'], norm(x['num'])) in excluir:
                continue
            if not ruta.get((x['codigo'], x['num']), '').startswith('LIBRO SEGUNDO'):
                cuenta['parte general, no se agregan'] += 1
                continue
            arts = reglas[rid].setdefault('articulos', {}).setdefault(x['codigo'], [])
            if norm(x['num']) not in {norm(a) for a in arts}:
                arts.append(x['num'])
                cuenta['agregados'] += 1
                cuenta[f'agregados {x["codigo"]}'] += 1
                cambiadas.add(rid)
    for rid in cambiadas:
        if reglas[rid].get('estado') == 'borrador':
            reglas[rid]['estado'] = 'sugerida'
            cuenta['borrador → sugerida'] += 1
    cuenta['reglas que cambian'] = len(cambiadas)
    (args.carpeta / 'catalogo_nuevo.json').write_text(json.dumps(doc, ensure_ascii=False, indent=1))
    for k, v in sorted(cuenta.items()):
        print(f'{k}: {v}')


if __name__ == '__main__':
    main()
