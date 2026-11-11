"""
Compara dos lecturas de los mismos artículos con dos LLM distintos (clasificar.py sobre dos carpetas con el mismo
articulos.jsonl y el mismo catálogo) y escribe los artículos en los que no coinciden, para revisarlos a mano.

    python3 comparar_modelos.py CARPETA_A CARPETA_B SALIDA.jsonl

Coinciden si dan lo mismo en: es delito / es de familia, tipos de caso y reglas (como conjuntos). `cuando`, `cita` y
el nombre del delito o tema no cuentan. Cada línea de SALIDA trae el texto del artículo y las dos respuestas.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def leer(carpeta: Path) -> dict:
    cat = json.loads((carpeta / 'catalogo.json').read_text())
    out = {}
    for l in open(carpeta / 'resultados.jsonl'):
        try:
            r = json.loads(l)
        except ValueError:
            continue
        if r.get('catalogo_md5') == cat['md5']:
            out[(r['codigo'], r['ruta'])] = r
    return out


def clave(d: dict) -> dict:
    return {'es': bool(d.get('es_delito', d.get('es_familiar'))), 'tipos_caso': sorted(set(d.get('tipos_caso') or [])),
            'reglas': sorted(set(d.get('reglas') or []))}


def main(a: Path, b: Path, salida: Path) -> None:
    ra, rb = leer(a), leer(b)
    textos = {(x['codigo'], x['ruta']): x['texto'] for x in map(json.loads, open(a / 'articulos.jsonl'))}
    comunes = ra.keys() & rb.keys()
    cuenta, por_ley = Counter(), Counter()
    with open(salida, 'w') as f:
        for k in sorted(comunes):
            ka, kb = clave(ra[k]['respuesta']), clave(rb[k]['respuesta'])
            difiere = [c for c in ka if ka[c] != kb[c]]
            for c in difiere:
                cuenta[c] += 1
            if difiere:
                por_ley[k[0]] += 1
                f.write(json.dumps({'codigo': k[0], 'ruta': k[1], 'num': ra[k]['num'], 'difiere': difiere,
                                    'texto': textos.get(k, ''), a.name: ra[k]['respuesta'], b.name: rb[k]['respuesta']},
                                   ensure_ascii=False) + '\n')
    n = sum(por_ley.values())
    print(f'{len(comunes)} artículos en las dos · no coinciden {n} ({n / max(len(comunes), 1):.0%})')
    print('en qué:', dict(cuenta))
    print('por ley:', dict(por_ley.most_common()))


if __name__ == '__main__':
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
