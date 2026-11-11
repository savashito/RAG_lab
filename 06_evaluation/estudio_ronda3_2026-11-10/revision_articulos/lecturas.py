"""
Qué dijo cada LLM sobre cada artículo de cada regla, para mostrarlo en /catalogo y revisar a mano donde no coinciden.

    python3 lecturas.py CATALOGO_JSON SALIDA_JSON

Junta tres lecturas de los mismos artículos con el mismo catálogo (clasificar.py) y las decisiones a mano de Claude:

    data/todo           Gemma 4 31B sin razonar
    data/todo_piensa    Gemma 4 31B razonando (--pensar)
    data/todo_oss       gpt-oss-120b
    decisiones de Claude: data/todo_piensa/revision_efectiva.json (Gemma con y sin razonar),
                          data/todo_oss/citas_solo_oss.json + aceptadas_a_mano.json (gpt-oss),
                          data/todo_piensa/pendientes_gemma.json + pendientes_aceptadas.json (Gemma razonando)

Por regla, cada artículo que el catálogo cita o que algún LLM le asigna, con 1/0 por modelo. Con el mismo filtro que
aplicar.py: de los 5 códigos penales solo la parte especial (LIBRO SEGUNDO) y solo reglas de la misma materia que la ley.
Solo números de artículo y votos: no lleva texto de ley ni datos de participantes.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from comparar import norm

CODIGOS_PENALES = {'cdmx', 'queretaro', 'edomex', 'morelos', 'federal'}
LEYES_FAMILIA = {'cc_cdmx', 'cpc_cdmx', 'cnpcf'}
MODELOS = {'gemma': ('data/todo', 'Gemma 4 31B'), 'gemma_razona': ('data/todo_piensa', 'Gemma 4 31B razonando'),
           'oss': ('data/todo_oss', 'gpt-oss-120b')}


def leer(carpeta: Path, md5: str) -> dict:
    out = {}
    for l in open(carpeta / 'resultados.jsonl'):
        try:
            r = json.loads(l)
        except ValueError:
            continue
        if r.get('catalogo_md5') == md5:
            out[(r['codigo'], r['ruta'])] = r
    return out


def main(catalogo: Path, salida: Path) -> None:
    md5 = json.loads(Path('data/todo/catalogo.json').read_text())['md5']
    doc = json.loads(catalogo.read_text())
    doc = doc.get('doc', doc)
    materia = {r['id']: r.get('materia', 'penal') for r in doc['reglas']}
    # Las reglas que no estaban en el catálogo que leyeron los LLM (las de familia, r117 en adelante) no tienen votos:
    # que un LLM no las pusiera no quiere decir que no.
    leidas = {r['id'] for r in json.loads(Path('data/todo/catalogo.json').read_text())['doc']['reglas']}
    votos = defaultdict(dict)                  # (regla, codigo, norm(num)) → {modelo: 1}
    num = {}                                   # (codigo, norm(num)) → num como lo escribe la ley
    leidos = defaultdict(set)                  # modelo → {(codigo, norm(num))}
    for m, (carpeta, _) in MODELOS.items():
        for (codigo, ruta), r in leer(Path(carpeta), md5).items():
            if not r['num']:
                continue
            k = (codigo, norm(r['num']))
            num.setdefault(k, r['num'])
            leidos[m].add(k)
            if codigo in CODIGOS_PENALES and not ruta.startswith('LIBRO SEGUNDO'):
                continue
            ley_materia = 'familiar' if codigo in LEYES_FAMILIA else 'penal'
            for rid in r['respuesta'].get('reglas') or []:
                if materia.get(rid) == ley_materia:
                    votos[(rid, *k)][m] = 1

    claude = {}                                # (regla, codigo, norm(num)) → 1/0
    for x in json.loads(Path('data/todo_piensa/revision_efectiva.json').read_text()):
        for rid in set(x['sin']) | set(x['con']):
            claude[(rid, x['codigo'], norm(x['num']))] = int(rid in x['reglas'])
    for propuestas, aceptadas in (('data/todo_oss/citas_solo_oss.json', 'data/todo_oss/aceptadas_a_mano.json'),
                                  ('data/todo_piensa/pendientes_gemma.json', 'data/todo_piensa/pendientes_aceptadas.json')):
        si = {(r, c, norm(n)) for c, n, r in json.loads(Path(aceptadas).read_text())}
        for c, n, r in json.loads(Path(propuestas).read_text()):
            claude.setdefault((r, c, norm(n)), int((r, c, norm(n)) in si))
        for k in si:                           # aceptadas que ya estaban en el catálogo escrito
            claude[k] = 1

    reglas = defaultdict(list)
    for rg in doc['reglas']:                   # también los artículos que cita el catálogo sin que ningún LLM los proponga
        for codigo, arts in (rg.get('articulos') or {}).items():
            for a in arts:
                votos.setdefault((rg['id'], codigo, norm(a)), {})
                num.setdefault((codigo, norm(a)), a)
    for (rid, codigo, n), v in sorted(votos.items()):
        fila = {'ley': codigo, 'art': num[(codigo, n)]}
        for m in MODELOS:                      # sin lectura del modelo (artículo que no está en el corpus): no se pone
            if (codigo, n) in leidos[m] and rid in leidas:
                fila[m] = v.get(m, 0)
        if (rid, codigo, n) in claude:
            fila['claude'] = claude[(rid, codigo, n)]
        reglas[rid].append(fila)
    nombres = {m: n for m, (_, n) in MODELOS.items()} | {'claude': 'Claude (revisión a mano)'}
    salida.write_text(json.dumps({'modelos': nombres, 'reglas': reglas}, ensure_ascii=False, separators=(',', ':')))
    print(f'{sum(len(v) for v in reglas.values())} filas en {len(reglas)} reglas → {salida}')


if __name__ == '__main__':
    main(Path(sys.argv[1]), Path(sys.argv[2]))
