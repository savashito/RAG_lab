"""
Tipos de caso de familia: el LLM los propone a partir de los temas que salieron de la primera lectura de las leyes de
familia (clasificar.py con el prompt de familia), y prepara la segunda lectura.

    python3 agrupar.py CARPETA SALIDA      CARPETA = la de la primera lectura (data/leyes)

  1. Junta los temas de los artículos con es_familiar = true (con cuántos artículos tiene cada uno).
  2. El LLM propone los tipos de caso de familia, con unos temas de ejemplo → SALIDA/tipos_familia.json (a qué tipo
     va cada artículo lo dice la segunda lectura: listar los 378 temas no cabe en los 8192 tokens del modelo)
  3. Escribe SALIDA/catalogo.json (el catálogo + esos tipos, materia familiar, estado sugerida) y SALIDA/articulos.jsonl
     (solo los artículos de familia), para correr otra vez clasificar.py sobre SALIDA.

No cambia el catálogo de la base. Solo texto de ley y del catálogo.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from clasificar import leer_json, llamar

SYSTEM = """Eres abogada familiarista en México. Diseñas los TIPOS DE CASO de familia de un asistente que orienta a
personas. Un tipo de caso es lo que le pasó o lo que quiere la persona, dicho como lo diría ella; el asistente lo usa
para saber qué preguntarle y qué artículos citarle. Recibes los TEMAS que salieron de leer, artículo por artículo, un
código civil y dos de procedimientos (con cuántos artículos tiene cada tema).

Propón entre 10 y 16 tipos de caso que cubran todos los temas, sin que dos tipos se encimen. Los temas de
procedimiento que sirven para cualquier juicio familiar (pruebas, audiencias, notificaciones, recursos) van a un tipo de
caso propio.

Responde SOLO un JSON:
{"tipos_caso": [{"id": "minusculas_con_guion_bajo", "titulo": "en palabras de la persona",
  "descripcion": "una frase: qué casos entran", "temas": ["hasta 5 temas de ejemplo de la lista"]}]}
No expliques nada fuera del JSON."""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('carpeta', type=Path)
    ap.add_argument('salida', type=Path)
    ap.add_argument('--url', default='http://localhost:8000/v1')
    ap.add_argument('--modelo', default='gemma-4-31b')
    args = ap.parse_args()
    args.salida.mkdir(parents=True, exist_ok=True)

    res = [json.loads(l) for l in open(args.carpeta / 'resultados.jsonl')]
    fam = {(r['codigo'], r['ruta']) for r in res if r['materia'] == 'familiar' and r['respuesta'].get('es_familiar')}
    temas = Counter((r['respuesta'].get('tema') or '').strip().lower() for r in res
                    if (r['codigo'], r['ruta']) in fam)
    temas.pop('', None)

    destino = args.salida / 'tipos_familia.json'
    if not destino.exists():                     # la llamada se hace una vez; para repetirla, borra el archivo
        user = 'TEMAS (artículos):\n' + '\n'.join(f'- {t} ({n})' for t, n in temas.most_common())
        raw = llamar(args.url, args.modelo, SYSTEM, user, timeout=600, max_tokens=2500)
        d = leer_json(raw)
        assert d and d.get('tipos_caso'), f'El LLM no dio un JSON con tipos_caso:\n{raw[:2000]}'
        destino.write_text(json.dumps({'prompt_md5': hashlib.md5(SYSTEM.encode()).hexdigest(), 'respuesta': d, 'raw': raw},
                                      ensure_ascii=False, indent=1))
    d = json.loads(destino.read_text())['respuesta']

    for tc in d['tipos_caso']:
        print(f'{tc["id"]:32} {tc["titulo"]}\n{"":32} {tc["descripcion"]} · ej.: {", ".join(tc.get("temas", []))}')

    cat = json.loads((args.carpeta / 'catalogo.json').read_text())
    doc = json.loads(json.dumps(cat['doc']))
    ids = {t['id'] for t in doc['tipos_caso']}
    doc['tipos_caso'] += [{'id': tc['id'], 'materia': 'familiar', 'titulo': tc['titulo'], 'descripcion': tc['descripcion'],
                           'datos': ['lugar_hechos'], 'estado': 'sugerida'} for tc in d['tipos_caso'] if tc['id'] not in ids]
    md5 = hashlib.md5(json.dumps(doc, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    (args.salida / 'catalogo.json').write_text(json.dumps({'md5': md5, 'doc': doc}, ensure_ascii=False, indent=1))
    n = 0
    with open(args.salida / 'articulos.jsonl', 'w') as f:
        for l in open(args.carpeta / 'articulos.jsonl'):
            a = json.loads(l)
            if (a['codigo'], a['ruta']) in fam:
                f.write(l)
                n += 1
    print(f'{n} artículos de familia y catálogo {md5[:8]} → {args.salida}')


if __name__ == '__main__':
    main()
