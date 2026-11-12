"""
Condiciones propuestas para las reglas: con qué datos del expediente se decide si cada regla aplica.

Hoy casi ninguna regla tiene condición `cuando`, así que la consulta solo pregunta el lugar y el papel y orienta con
todas las reglas del tipo de caso. Este script le pide al LLM, una vez por tipo de caso, una condición para cada regla
(o ninguna, si aplica siempre), usando los datos que ya existen en la pestaña Datos del expediente y, si hace falta, los
candidatos de datos_candidatos.py.

    python3 condiciones_propuestas.py SALIDA [--materia penal|familiar] [--tipo ID …] [--url … --modelo … --pensar]

Valida cada condición con la misma gramática que usa la consulta (consulta/expediente.py) y que use datos que existen o
que el LLM propone. Escribe SALIDA/condiciones.json y SALIDA/reporte.md. No cambia el catálogo.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

from clasificar import leer_json, llamar

AQUI = Path(__file__).resolve().parent
APP = AQUI.parents[2] / 'apps' / 'rewrite_lab'
sys.path.insert(0, str(APP))
from consulta.expediente import _COND  # noqa: E402

CATALOGO = APP / 'consulta' / 'catalogo_casos.yaml'
CANDIDATOS = AQUI / 'data' / 'datos_candidatos' / 'candidatos.json'

SYSTEM = """Eres abogada penalista en México. Un asistente orienta a personas: les pregunta unos DATOS (uno por uno) y,
según las respuestas, decide qué REGLAS de su tipo de caso aplican; cada regla cita los artículos de un delito. Una
regla aplica si todas sus condiciones se cumplen; sin condiciones, aplica siempre en su tipo de caso.

Recibes un TIPO DE CASO, sus REGLAS (delito y cuándo aplica, en palabras) y los DATOS disponibles: los que ya existen y
algunos candidatos. Para cada regla, escribe las condiciones que distinguen cuándo aplica, usando esos datos.

Gramática de una condición (exactamente así):
  dato = valor        dato != valor        dato < número   (también <=, >, >=)
  dato en valor1, valor2        NO dato  (el dato es «no»)        dato  (el dato es «sí»)
Los valores de un dato «opcion» son exactamente sus opciones; los de «si_no» son si / no.

Reglas para proponer:
- Solo condiciones que la persona puede contestar con un hecho de su caso. Si la regla aplica a cualquier caso del tipo
  (o la diferencia no se puede preguntar), déjala sin condiciones.
- Usa primero los datos que ya existen. Un dato nuevo solo si ninguno sirve; descríbelo en "datos_nuevos".
- No pongas una condición que deje fuera a la persona por no saber un dato: si no lo sabe, la regla queda «incierta» y
  el asistente lo explica.
- Si dos reglas son el mismo delito con y sin agravante, la del agravante lleva la condición y la básica no.

Responde SOLO un JSON:
{"reglas": [{"id": "r001", "cuando": ["condición", …], "por_que": "una frase"}],
 "datos_nuevos": [{"id": "minusculas_con_guion_bajo", "pregunta": "de tú", "tipo": "si_no" | "numero" | "opcion",
   "opciones": ["solo si es opcion, en minúsculas_con_guion_bajo"], "para_que": "una frase"}]}
Incluye todas las reglas de la lista. No expliques nada fuera del JSON."""


def validar(cuando: list, datos: dict) -> list[str]:
    """Errores de las condiciones: gramática y datos o valores que no existen."""
    errores = []
    for c in cuando:
        m = _COND.match(str(c))
        if not m:
            errores.append(f'«{c}»: no sigue la gramática')
            continue
        d = m.group('id') or m.group('solo')
        if d not in datos:
            errores.append(f'«{c}»: el dato {d} no existe')
            continue
        val, op, tipo = m.group('val'), m.group('op'), datos[d].get('tipo', 'si_no')
        vals = [v.strip() for v in val.split(',')] if val and op == 'en' else [val.strip()] if val else []
        if tipo == 'opcion' and any(v not in (datos[d].get('opciones') or []) for v in vals):
            errores.append(f'«{c}»: valor que no es opción de {d}')
        if tipo == 'si_no' and any(v not in ('si', 'no') for v in vals):
            errores.append(f'«{c}»: {d} es sí/no')
    return errores


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('salida', type=Path)
    ap.add_argument('--materia', default='penal')
    ap.add_argument('--tipo', nargs='*')
    ap.add_argument('--url', default='http://localhost:8002/v1')
    ap.add_argument('--modelo', default='gemma-4-31b')
    ap.add_argument('--pensar', action='store_true')
    ap.add_argument('--max-tokens', type=int, default=8000)
    args = ap.parse_args()
    args.salida.mkdir(parents=True, exist_ok=True)
    cat = yaml.safe_load(CATALOGO.read_text())
    existentes = {d['id']: d for d in cat['datos']}
    candidatos = {x['tipo']: (x['respuesta'] or {}).get('datos') or [] for x in json.loads(CANDIDATOS.read_text())['tipos']}
    tipos = [t for t in cat['tipos_caso'] if t.get('materia', 'penal') == args.materia and (not args.tipo or t['id'] in args.tipo)
             and t['estado'] != 'descartada' and any(r['tipo_caso'] == t['id'] for r in cat['reglas'])]

    def dato_txt(d: dict) -> str:
        return (f'- {d["id"]} ({d.get("tipo", "si_no")}' + (f': {", ".join(d.get("opciones") or [])}' if d.get('opciones') else '')
                + f'): {d.get("pregunta", "")}')

    def proponer(t: dict) -> dict:
        reglas = [r for r in cat['reglas'] if r['tipo_caso'] == t['id'] and r.get('estado') != 'descartada']
        user = (f'TIPO DE CASO: {t["id"]}: {t["titulo"]}\n\nREGLAS:\n'
                + '\n'.join(f'- {r["id"]}: {r["delito"]}' + (f' — {r["condicion"]}' if r.get('condicion') else '')
                            + (f' · condición actual: {", ".join(r["cuando"])}' if r.get('cuando') else '') for r in reglas)
                + '\n\nDATOS QUE YA EXISTEN:\n' + '\n'.join(dato_txt(d) for d in existentes.values() if d.get('preguntar', True))
                + '\n\nDATOS CANDIDATOS (nuevos, para este tipo de caso):\n'
                + ('\n'.join(dato_txt(d) for d in candidatos.get(t['id'], []) if not d.get('existente')) or '(ninguno)'))
        raw = llamar(args.url, args.modelo, SYSTEM, user, timeout=900, max_tokens=args.max_tokens, pensar=args.pensar)
        d = leer_json(raw) or {}
        nuevos = {x['id']: x for x in d.get('datos_nuevos') or [] if isinstance(x, dict) and x.get('id')}
        disponibles = {**existentes, **nuevos}
        props = []
        for r in reglas:
            p = next((x for x in d.get('reglas') or [] if isinstance(x, dict) and x.get('id') == r['id']), None)
            cuando = (p or {}).get('cuando') or []
            props.append({'id': r['id'], 'delito': r['delito'], 'actual': r.get('cuando') or [], 'cuando': cuando,
                          'por_que': (p or {}).get('por_que', ''), 'falta': p is None, 'errores': validar(cuando, disponibles)})
        return {'tipo': t['id'], 'titulo': t['titulo'], 'reglas': props, 'datos_nuevos': list(nuevos.values()), 'raw': raw}

    print(f'{len(tipos)} tipos de caso ({args.materia})', flush=True)
    with ThreadPoolExecutor(8) as pool:
        res = list(pool.map(proponer, tipos))
    (args.salida / 'condiciones.json').write_text(json.dumps(
        {'modelo': args.modelo, 'pensar': args.pensar, 'prompt_md5': hashlib.md5(SYSTEM.encode()).hexdigest(), 'tipos': res},
        ensure_ascii=False, indent=1))

    usados = lambda x: sorted({(_COND.match(c).group('id') or _COND.match(c).group('solo'))   # noqa: E731
                               for r in x['reglas'] for c in r['cuando'] if _COND.match(str(c))})
    out = ['# Condiciones propuestas para las reglas', '',
           f'Propuestas por {args.modelo}{" (razonando)" if args.pensar else ""}, materia {args.materia}. Por tipo de caso: '
           'qué datos se preguntarían (además del lugar y el papel) y la condición de cada regla. «—» = sin condición '
           '(aplica siempre en su tipo). ⚠ = la condición no es válida (gramática, dato o valor que no existe).', '',
           '| Tipo de caso | Reglas | Con condición | Datos que se preguntarían | Datos nuevos |', '|---|---|---|---|---|']
    for x in res:
        out.append(f'| {x["titulo"]} | {len(x["reglas"])} | {sum(bool(r["cuando"]) for r in x["reglas"])} | '
                   f'{", ".join(usados(x)) or "—"} | {", ".join(d["id"] for d in x["datos_nuevos"]) or "—"} |')
    for x in res:
        out += ['', f'## {x["titulo"]} (`{x["tipo"]}`)', '', '| Regla | Delito | Condición propuesta | Por qué |', '|---|---|---|---|']
        for r in x['reglas']:
            c = ' y '.join(f'`{c}`' for c in r['cuando']) or '—'
            if r['errores']:
                c += ' ⚠ ' + '; '.join(r['errores'])
            if r['falta']:
                c = '⚠ el LLM no la incluyó'
            out.append(f'| {r["id"]} | {r["delito"][:60]} | {c} | {r["por_que"]} |')
        if x['datos_nuevos']:
            out += ['', 'Datos nuevos:', '']
            out += [f'- **{d["id"]}** ({d.get("tipo", "")}{": " + ", ".join(d.get("opciones") or []) if d.get("opciones") else ""}): '
                    f'{d.get("pregunta", "")} — {d.get("para_que", "")}' for d in x['datos_nuevos']]
    (args.salida / 'reporte.md').write_text('\n'.join(out) + '\n')
    print(f'→ {args.salida}/reporte.md')


if __name__ == '__main__':
    main()
