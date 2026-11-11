"""
Reglas de familia a partir de la segunda lectura (clasificar.py sobre la carpeta que escribió agrupar.py):

  1. Cada artículo va al primer tipo de caso de familia que le dio el LLM (o a violencia_familiar).
  2. Por tipo de caso, el LLM junta sus temas en unas cuantas reglas (una llamada por tipo) → CARPETA/reglas_llm.json
  3. Cada regla cita los artículos de sus temas, por ley. Estado sugerida, materia familiar, sin condiciones `cuando`.
  4. Escribe CARPETA/catalogo_nuevo.json (el catálogo de la base + tipos y reglas de familia) y CARPETA/reporte.md
     (reglas, artículos sin regla y los datos del expediente que el LLM dice que faltan).

    python3 reglas_familia.py CARPETA [--url … --modelo …]

No cambia el catálogo de la base. Solo texto de ley y del catálogo.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from clasificar import leer_json, llamar
from comparar import norm

SYSTEM = """Eres abogada familiarista en México. Un asistente orienta a personas con un catálogo de casos: cada TIPO DE
CASO tiene REGLAS, y cada regla une el tipo de caso con un tema y con los artículos que lo regulan. Recibes un tipo de
caso y los TEMAS de los artículos que le tocan (con cuántos artículos tiene cada tema).

Junta los temas en entre 2 y 8 reglas. Una regla es una pregunta distinta que haría la persona (por ejemplo, en
pensión alimenticia: «cuánto me toca», «no me paga», «quiero dejar de pagar»). Cada tema va a una sola regla.

Responde SOLO un JSON:
{"reglas": [{"tema": "nombre corto de la regla", "condicion": "en palabras: cuándo aplica", "temas": ["tema", ...]}]}
Usa los temas tal cual vienen en la lista. No expliques nada fuera del JSON."""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('carpeta', type=Path)
    ap.add_argument('--url', default='http://localhost:8000/v1')
    ap.add_argument('--modelo', default='gemma-4-31b')
    args = ap.parse_args()
    cat = json.loads((args.carpeta / 'catalogo.json').read_text())
    doc = json.loads(json.dumps(cat['doc']))
    familia = [t['id'] for t in doc['tipos_caso'] if t.get('materia') == 'familiar'] + ['violencia_familiar']
    titulos = {t['id']: t['titulo'] for t in doc['tipos_caso']}

    arts = defaultdict(list)                    # tipo → [(codigo, num, tema)]
    sin_tipo, faltan = [], Counter()
    for l in open(args.carpeta / 'resultados.jsonl'):
        r = json.loads(l)
        if r.get('catalogo_md5') != cat['md5']:
            continue
        d = r['respuesta']
        if not d.get('es_familiar'):
            continue
        if d.get('dato_que_falta'):
            faltan[d['dato_que_falta'].strip().lower()] += 1
        tipo = next((t for t in d.get('tipos_caso') or [] if t in familia), None)
        tema = (d.get('tema') or '').strip().lower()
        if tipo and r['num']:
            arts[tipo].append((r['codigo'], r['num'], tema))
        else:
            sin_tipo.append((r['codigo'], r['num'] or r['ruta'][-50:], tema, d.get('tipos_caso')))

    destino = args.carpeta / 'reglas_llm.json'
    hechas = json.loads(destino.read_text()) if destino.exists() else {}

    def agrupar(tipo: str) -> tuple[str, dict]:
        temas = Counter(t for _, _, t in arts[tipo])
        user = (f'TIPO DE CASO: {tipo}: {titulos[tipo]}\n\nTEMAS (artículos):\n'
                + '\n'.join(f'- {t} ({n})' for t, n in temas.most_common()))
        raw = llamar(args.url, args.modelo, SYSTEM, user, timeout=600, max_tokens=2500)
        return tipo, {'respuesta': leer_json(raw), 'raw': raw, 'prompt_md5': hashlib.md5(SYSTEM.encode()).hexdigest()}

    with ThreadPoolExecutor(8) as pool:
        for tipo, x in pool.map(agrupar, [t for t in arts if t not in hechas or not hechas[t]['respuesta']]):
            hechas[tipo] = x
    destino.write_text(json.dumps(hechas, ensure_ascii=False, indent=1))

    n = max(int(r['id'][1:]) for r in doc['reglas'] if r['id'][1:].isdigit())
    nuevas, sin_regla = [], []
    for tipo in sorted(arts, key=familia.index):
        reglas = (hechas[tipo]['respuesta'] or {}).get('reglas') or []
        de_tema = {t: i for i, rg in enumerate(reglas) for t in rg.get('temas', [])}
        citas = [defaultdict(list) for _ in reglas]
        for codigo, num, tema in arts[tipo]:
            if tema in de_tema:
                lista = citas[de_tema[tema]][codigo]
                if norm(num) not in {norm(a) for a in lista}:
                    lista.append(num)
            else:
                sin_regla.append((tipo, codigo, num, tema))
        for rg, c in zip(reglas, citas):
            if not c:
                continue
            n += 1
            nuevas.append({'id': f'r{n:03d}', 'materia': 'familiar', 'tipo_caso': tipo, 'delito': rg['tema'],
                           'condicion': rg.get('condicion', ''), 'cuando': [], 'articulos': dict(c),
                           'estado': 'sugerida',
                           'nota': 'Propuesta por Gemma 4 31B leyendo los artículos (revisión 2026-11-11).'})
    doc['reglas'] += nuevas
    (args.carpeta / 'catalogo_nuevo.json').write_text(json.dumps(doc, ensure_ascii=False, indent=1))

    out = ['# Reglas de familia propuestas por el LLM', '',
           f'{len(nuevas)} reglas en {len(arts)} tipos de caso · {sum(len(v) for v in arts.values())} artículos con '
           f'tipo de caso · {len(sin_regla)} sin regla (su tema no quedó en ninguna) · {len(sin_tipo)} sin tipo de caso '
           'de familia', '']
    for tipo in sorted(arts, key=familia.index):
        out += [f'## {tipo}: {titulos[tipo]}', '']
        for r in [r for r in nuevas if r['tipo_caso'] == tipo]:
            cit = ' · '.join(f'{k}: {len(v)}' for k, v in r['articulos'].items())
            out.append(f'- **{r["id"]} {r["delito"]}** ({cit}): {r["condicion"]}')
        out.append('')
    out += ['## Datos del expediente que el LLM dice que faltan (los 40 más frecuentes)', '']
    out += [f'- {d} ({k})' for d, k in faltan.most_common(40)]
    out += ['', '## Artículos sin tipo de caso de familia', '']
    out += [f'- {c} {n}: {t} → {tc}' for c, n, t, tc in sin_tipo[:200]]
    (args.carpeta / 'reporte.md').write_text('\n'.join(out) + '\n')
    print('\n'.join(out[:3 + 2 * len(arts) + len(nuevas) + 2]))


if __name__ == '__main__':
    main()
