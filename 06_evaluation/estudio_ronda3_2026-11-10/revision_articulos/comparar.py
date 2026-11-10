"""
Compara lo que dijo el LLM en resultados.jsonl (clasificar.py) con las reglas del catálogo y escribe:

    CARPETA/reporte.md          por regla: artículos que el LLM confirma, que sugiere agregar y en los que no está de
                                acuerdo; reglas nuevas que propone; datos que dice que faltan
    CARPETA/sugerencias.json    lo mismo en datos, para cargarlo después al catálogo como `sugerida` (no lo carga)

    python3 comparar.py CARPETA

No cambia el catálogo. Solo texto de ley y del catálogo: el reporte se puede commitear.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

COND = re.compile(r'^\s*(?:NO\s+(?P<solo>\w+)|(?P<id>\w+)\s*(?:(?:<=|>=|!=|=|<|>|\ben\b)\s*.+?)?)\s*$')


def norm(num: str) -> str:
    s = ''.join(c for c in unicodedata.normalize('NFD', str(num)) if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+', ' ', s).strip().lower()


def main(carpeta: Path) -> None:
    cat = json.loads((carpeta / 'catalogo.json').read_text())
    doc = cat['doc']
    reglas = {r['id']: r for r in doc.get('reglas', [])}
    datos = {d['id'] for d in doc.get('datos', [])}
    res = {}
    for l in open(carpeta / 'resultados.jsonl'):
        try:
            r = json.loads(l)
        except ValueError:
            continue
        if r.get('catalogo_md5') == cat['md5']:
            res[(r['codigo'], r['ruta'])] = r          # la última línea de cada artículo gana
    por_num = {(c, norm(r['num'])): r for (c, _), r in res.items() if r['num']}

    confirma, sugiere, desacuerdo = defaultdict(list), defaultdict(list), defaultdict(list)
    for (codigo, _), r in res.items():
        d = r['respuesta']
        for rid in d.get('reglas') or []:
            if rid not in reglas:
                continue
            citados = {norm(a) for a in reglas[rid].get('articulos', {}).get(codigo, [])}
            item = {'codigo': codigo, 'num': r['num'], 'cuando': d.get('cuando') or [], 'cita': d.get('cita', '')}
            (confirma if norm(r['num']) in citados else sugiere)[rid].append(item)
    revisados = {c for c, _ in res}                  # solo los códigos que ya corrió clasificar.py
    for rid, regla in reglas.items():
        for codigo, arts in (regla.get('articulos') or {}).items():
            for a in (arts or []) if codigo in revisados else []:
                r = por_num.get((codigo, norm(a)))
                if r is None:
                    desacuerdo[rid].append({'codigo': codigo, 'num': a, 'motivo': 'no está en el corpus'})
                elif rid not in (r['respuesta'].get('reglas') or []):
                    d = r['respuesta']
                    desacuerdo[rid].append({'codigo': codigo, 'num': a, 'motivo':
                                            'no es delito' if not d.get('es_delito') else
                                            f'el LLM lo pone en {", ".join(d.get("reglas") or []) or "ninguna regla"}'
                                            f' ({", ".join(d.get("tipos_caso") or [])})', 'cita': d.get('cita', '')})

    nuevas = defaultdict(list)
    faltan, malas, tipos = Counter(), Counter(), Counter()
    for (codigo, _), r in res.items():
        d = r['respuesta']
        if d.get('es_delito'):
            for t in d.get('tipos_caso') or ['(ninguno)']:
                tipos[t] += 1
        n = d.get('regla_nueva')
        if isinstance(n, dict) and n.get('tipo_caso'):
            nuevas[(n['tipo_caso'], norm(n.get('delito', '')))].append({'codigo': codigo, 'num': r['num'], **n})
        if d.get('dato_que_falta'):
            faltan[d['dato_que_falta'].strip().lower()] += 1
        for c in d.get('cuando') or []:
            m = COND.match(str(c))
            if not m or (m.group('solo') or m.group('id')) not in datos:
                malas[str(c)] += 1

    L = [f'# Revisión de artículos por el LLM', '',
         f'Catálogo `{cat["md5"][:8]}` · {len(res)} artículos · '
         f'{sum(1 for r in res.values() if r["respuesta"].get("es_delito"))} son delito según el LLM.', '',
         '## Artículos por tipo de caso', '', '| tipo de caso | artículos |', '|---|---|']
    L += [f'| {t} | {n} |' for t, n in tipos.most_common()]
    L += ['', '## Por regla', '']
    for rid, regla in reglas.items():
        if not (confirma[rid] or sugiere[rid] or desacuerdo[rid]):
            continue
        L += [f'### {rid} · {regla["tipo_caso"]} · {regla["delito"]}', '']
        if confirma[rid]:
            L.append('**Confirma:** ' + ', '.join(f'{x["codigo"]} {x["num"]}' for x in confirma[rid]))
        for x in sugiere[rid]:
            L.append(f'- **Agregar** {x["codigo"]} {x["num"]}'
                     + (f' · cuando {x["cuando"]}' if x['cuando'] else '') + f' — «{x["cita"]}»')
        for x in desacuerdo[rid]:
            L.append(f'- **Desacuerdo** {x["codigo"]} {x["num"]}: {x["motivo"]}')
        L.append('')
    L += ['## Reglas nuevas que propone', '']
    for (tipo, _), xs in sorted(nuevas.items(), key=lambda kv: -len(kv[1])):
        L.append(f'- **{tipo} · {xs[0].get("delito", "")}** ({len(xs)} arts.): '
                 + ', '.join(f'{x["codigo"]} {x["num"]}' for x in xs) + f' — {xs[0].get("condicion", "")}')
    L += ['', '## Datos que dice que faltan en el expediente', '']
    L += [f'- {k} ({n})' for k, n in faltan.most_common(40)]
    if malas:
        L += ['', '## Condiciones que no se pueden evaluar (ids que no existen)', '']
        L += [f'- `{k}` ({n})' for k, n in malas.most_common(30)]
    (carpeta / 'reporte.md').write_text('\n'.join(L) + '\n')
    (carpeta / 'sugerencias.json').write_text(json.dumps(
        {'catalogo_md5': cat['md5'], 'agregar': sugiere, 'desacuerdo': desacuerdo,
         'reglas_nuevas': [{'tipo_caso': t, 'articulos': xs} for (t, _), xs in nuevas.items()]},
        ensure_ascii=False, indent=1))
    print(f'{len(res)} artículos · {sum(map(len, sugiere.values()))} por agregar · '
          f'{sum(map(len, desacuerdo.values()))} desacuerdos · {len(nuevas)} reglas nuevas → {carpeta / "reporte.md"}')


if __name__ == '__main__':
    main(Path(sys.argv[1] if len(sys.argv) > 1 else 'data'))
