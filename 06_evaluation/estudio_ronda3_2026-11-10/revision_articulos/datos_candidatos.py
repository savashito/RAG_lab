"""
Datos candidatos para el expediente: qué le falta preguntar a la consulta para saber qué artículos aplican.

Cuando el LLM leyó cada artículo (clasificar.py) dijo `dato_que_falta`: el hecho que hace falta saber para decidir si el
artículo aplica. Son frases libres que casi no se repiten. Este script las junta por tipo de caso y le pide al LLM, una
vez por tipo de caso, que las agrupe en 3 a 6 datos candidatos para la pestaña Datos del expediente (reusando los que ya
existen) y diga qué reglas los usarían en una condición.

    python3 datos_candidatos.py SALIDA [--url … --modelo … --pensar]

Lecturas:
    penal    data/todo_piensa/resultados.jsonl (Gemma 4 31B razonando), por el primer tipo de caso del artículo
    familia  data/todo_familia/resultados.jsonl, por el tipo de caso que le asignó reglas_familia.py
Catálogo: el del repo (apps/rewrite_lab/consulta/catalogo_casos.yaml), para los datos y reglas que ya existen.

Escribe SALIDA/candidatos.json y SALIDA/reporte.md. No cambia el catálogo. Solo texto de ley y del catálogo.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

from clasificar import leer_json, llamar

AQUI = Path(__file__).resolve().parent
CATALOGO = AQUI.parents[2] / 'apps' / 'rewrite_lab' / 'consulta' / 'catalogo_casos.yaml'
MAX_FRASES = 150

SYSTEM = """Eres abogada en México y diseñas el EXPEDIENTE de un asistente que orienta a personas: la lista de datos
que el asistente le pregunta a la persona, uno por uno, antes de orientarla. Cada dato sirve para decidir qué
artículos aplican a su caso (una REGLA del catálogo aplica o no según esos datos).

Recibes un TIPO DE CASO, sus REGLAS, los DATOS que ya existen en el expediente y una lista de FRASES: lo que, según
quien leyó cada artículo de ley de ese tipo de caso, hace falta saber para decidir si el artículo aplica (con cuántos
artículos lo dicen).

Propón entre 3 y 6 datos para este tipo de caso:
- Solo hechos que la persona puede contestar en una conversación («¿tienen hijos menores de edad?»), no conclusiones
  jurídicas («¿es un delito calificado?», «¿cuál es la etapa procesal?» se pregunta como «¿ya hubo una audiencia con
  un juez?»).
- Los que más cambian qué artículos aplican y los que más frases cubren. Junta frases que preguntan lo mismo.
- Si un dato que ya existe sirve, úsalo (pon su id en "existente") en vez de inventar otro.
- Para cada dato di qué reglas de la lista lo usarían y un ejemplo de condición («hijos_menores = si»).

Responde SOLO un JSON:
{"datos": [{"id": "minusculas_con_guion_bajo", "existente": null o "id que ya existe",
  "pregunta": "como se la diría el asistente a la persona", "pregunta_tu": "de tú, si le pasó a ella (o igual)",
  "tipo": "si_no" | "numero" | "opcion", "opciones": ["solo si es opcion"],
  "para_que": "una frase: qué cambia según la respuesta", "reglas": ["ids de reglas"],
  "condicion": "ejemplo de condición", "frases": número aproximado de frases que cubre}]}
No expliques nada fuera del JSON."""


def frases_por_tipo() -> dict[str, Counter]:
    out = defaultdict(Counter)
    md5 = json.loads((AQUI / 'data/todo/catalogo.json').read_text())['md5']
    for l in open(AQUI / 'data/todo_piensa/resultados.jsonl'):
        try:
            r = json.loads(l)
        except ValueError:
            continue
        d = r['respuesta']
        if r.get('catalogo_md5') != md5 or r.get('materia', 'penal') != 'penal' or not (d.get('tipos_caso') or []):
            continue
        f = str(d.get('dato_que_falta') or '').strip()
        if f and f.lower() not in ('null', 'ninguno', 'none'):
            out[d['tipos_caso'][0]][f.lower().rstrip('.')] += 1
    fam = AQUI / 'data/todo_familia'
    tipo = {(x['codigo'], x['ruta']): x['tipo'] for x in map(json.loads, open(fam / 'asignaciones.jsonl'))}
    for l in open(fam / 'resultados.jsonl'):
        r = json.loads(l)
        t = tipo.get((r['codigo'], r['ruta']))
        f = str(r['respuesta'].get('dato_que_falta') or '').strip()
        if t and f and f.lower() not in ('null', 'ninguno', 'none'):
            out[t][f.lower().rstrip('.')] += 1
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('salida', type=Path)
    ap.add_argument('--url', default='http://localhost:8002/v1')
    ap.add_argument('--modelo', default='gemma-4-31b')
    ap.add_argument('--pensar', action='store_true')
    ap.add_argument('--max-tokens', type=int, default=3000)
    args = ap.parse_args()
    args.salida.mkdir(parents=True, exist_ok=True)
    cat = yaml.safe_load(CATALOGO.read_text())
    tipos = {t['id']: t for t in cat['tipos_caso']}
    datos = '\n'.join(f'- {d["id"]} ({d.get("tipo", "si_no")}): {d.get("pregunta", "")}' for d in cat['datos'])
    frases = frases_por_tipo()

    def proponer(t: str) -> dict:
        reglas = [r for r in cat['reglas'] if r['tipo_caso'] == t and r.get('estado') != 'descartada']
        user = (f'TIPO DE CASO: {t}: {tipos[t]["titulo"]} ({tipos[t].get("materia", "penal")})\n\nREGLAS:\n'
                + '\n'.join(f'- {r["id"]}: {r["delito"]}' + (f' · cuando: {", ".join(r["cuando"])}' if r.get('cuando') else '')
                            for r in reglas)
                + f'\n\nDATOS QUE YA EXISTEN EN EL EXPEDIENTE:\n{datos}\n\nFRASES (artículos que lo dicen):\n'
                + '\n'.join(f'- {f} ({n})' for f, n in frases[t].most_common(MAX_FRASES)))
        raw = llamar(args.url, args.modelo, SYSTEM, user, timeout=900, max_tokens=args.max_tokens, pensar=args.pensar)
        return {'tipo': t, 'titulo': tipos[t]['titulo'], 'materia': tipos[t].get('materia', 'penal'),
                'frases': sum(frases[t].values()), 'frases_distintas': len(frases[t]),
                'respuesta': leer_json(raw), 'raw': raw}

    con_frases = [t for t in tipos if frases.get(t)]
    print(f'{len(con_frases)} tipos de caso con frases · {sum(sum(c.values()) for c in frases.values())} frases', flush=True)
    with ThreadPoolExecutor(8) as pool:
        res = list(pool.map(proponer, con_frases))
    (args.salida / 'candidatos.json').write_text(json.dumps(
        {'modelo': args.modelo, 'pensar': args.pensar, 'prompt_md5': hashlib.md5(SYSTEM.encode()).hexdigest(),
         'catalogo': CATALOGO.name, 'tipos': res}, ensure_ascii=False, indent=1))

    out = ['# Datos candidatos para el expediente', '',
           f'Propuestos por {args.modelo}{" (razonando)" if args.pensar else ""} a partir de lo que, al leer cada artículo, '
           'el LLM dijo que hace falta saber para decidir si aplica. Primero familia, luego penal; por tipo de caso, de más '
           'a menos frases. **existente** = un dato que ya está en la pestaña Datos del expediente.', '']
    orden = sorted(res, key=lambda x: (x['materia'] != 'familiar', -x['frases']))
    for x in orden:
        out += [f'## {x["titulo"]} (`{x["tipo"]}`, {x["materia"]}) · {x["frases"]} frases', '']
        ds = (x['respuesta'] or {}).get('datos') or []
        if not ds:
            out += ['_El LLM no dio un JSON válido._', '']
            continue
        out += ['| Dato | Pregunta | Tipo | Reglas | Condición | Para qué | Frases |', '|---|---|---|---|---|---|---|']
        for d in ds:
            tipo = d.get('tipo', '') + (f': {", ".join(d.get("opciones") or [])}' if d.get('opciones') else '')
            nombre = f'**{d.get("id", "")}**' + (f' (existente: `{d["existente"]}`)' if d.get('existente') else '')
            out.append(f'| {nombre} | {d.get("pregunta", "")} | {tipo} | {", ".join(d.get("reglas") or [])} | '
                       f'`{d.get("condicion", "")}` | {d.get("para_que", "")} | {d.get("frases", "")} |')
        out.append('')
    (args.salida / 'reporte.md').write_text('\n'.join(out) + '\n')
    print(f'→ {args.salida}/reporte.md')


if __name__ == '__main__':
    main()
