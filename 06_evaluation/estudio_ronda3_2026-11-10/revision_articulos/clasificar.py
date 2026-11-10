"""
El LLM lee cada artículo de los 5 códigos penales y dice a qué tipo de caso y a qué regla del catálogo pertenece, con
qué condiciones aplica y qué parte del artículo lo justifica. Es la revisión «artículo por artículo» del catálogo: lo
que salga son sugerencias para Karen, no cambia el catálogo (eso lo hace comparar.py como reporte).

Entrada (de exportar.py):   CARPETA/articulos.jsonl, CARPETA/catalogo.json
Salida (se va agregando):   CARPETA/resultados.jsonl, una línea por artículo terminado

Se puede cortar y volver a correr con el mismo comando: salta los artículos que ya están en resultados.jsonl con el
mismo prompt y el mismo catálogo. Un artículo que falla no se escribe, así que la siguiente corrida lo reintenta.

Solo usa la biblioteca estándar de Python (corre en el clúster sin instalar nada):
    python3 clasificar.py CARPETA --url http://localhost:8000/v1 --modelo gemma-4-31b --hilos 8
    python3 clasificar.py CARPETA --limite 20          # prueba corta
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SYSTEM = """Eres abogada penalista en México. Lees UN artículo de un código penal y lo relacionas con un catálogo de casos
que usa un asistente para orientar a personas. El catálogo tiene:
- TIPOS DE CASO: lo que le pasó a la persona, en sus palabras.
- REGLAS: cada regla une un tipo de caso con un delito y con los artículos de cada código que lo regulan.
- DATOS DEL EXPEDIENTE: lo que el asistente le pregunta a la persona para saber qué regla aplica.

Responde SOLO un JSON:
{"es_delito": true, "delito": "", "tipos_caso": [], "reglas": [], "regla_nueva": null, "cuando": [],
 "dato_que_falta": "", "cita": ""}

- "es_delito": true si el artículo define un delito o su pena, o una agravante o atenuante de un delito. false si es
  parte general (reglas de aplicación, penas en general, prescripción, etc.) o está derogado.
- "delito": nombre corto del delito que regula. Vacío si es_delito es false.
- "tipos_caso": ids de los tipos de caso en los que una persona llegaría a este delito. ["otro"] si es delito pero
  no cabe en ninguno. [] si es_delito es false.
- "reglas": ids de las reglas existentes a las que pertenece este artículo (aunque la regla todavía no lo cite).
- "regla_nueva": si el delito cabe en un tipo de caso pero ninguna regla lo cubre:
  {"tipo_caso": "id", "delito": "nombre", "condicion": "en palabras: cuándo aplica"}. Si no, null.
- "cuando": condiciones con los DATOS DEL EXPEDIENTE que deben cumplirse para que este artículo aplique. Solo ids de
  la lista. Formas: «dato» (= sí), «NO dato» (= no), «dato = valor», «dato != valor», «dato < 18» (también <=, >, >=),
  «dato en [a, b]». Vacío si aplica a todo el tipo de caso.
- "dato_que_falta": si para saber si aplica hace falta un dato del caso que NO está en la lista, cuál. Si no, "".
- "cita": el fragmento del artículo (máximo 40 palabras, copiado tal cual) que justifica tu respuesta.
- Usa solo ids de las listas. No expliques nada fuera del JSON."""

MAX_TEXTO = 7000          # caracteres del artículo; el modelo tiene 8192 tokens de contexto en total


def md5(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()


def contexto(doc: dict, codigo: str) -> str:
    """Catálogo en texto: tipos de caso, reglas (con los artículos que ya cita para este código) y datos."""
    tipos = '\n'.join(f'- {t["id"]}: {t["titulo"]}'
                      + (f' — {t["descripcion"]}' if t.get('descripcion') and t['descripcion'] != t['titulo'] else '')
                      for t in doc.get('tipos_caso', []) if t.get('estado') != 'descartada')
    reglas = '\n'.join(f'- {r["id"]} · {r["tipo_caso"]} · {r["delito"]}'
                       + (f' · cuando: {r["condicion"]}' if r.get('condicion') else '')
                       + (f' · arts.: {", ".join(r["articulos"][codigo])}' if r.get('articulos', {}).get(codigo) else '')
                       for r in doc.get('reglas', []) if r.get('estado') != 'descartada')
    datos = '\n'.join(f'- {d["id"]} ({d.get("tipo", "si_no")}'
                      + (f': {", ".join(d["opciones"])}' if d.get('opciones') else '') + f'): {d.get("pregunta", "")}'
                      for d in doc.get('datos', []))
    return f'TIPOS DE CASO:\n{tipos}\n- otro: ninguno de los anteriores\n\nREGLAS:\n{reglas}\n\nDATOS DEL EXPEDIENTE:\n{datos}'


def llamar(url: str, modelo: str, system: str, user: str, timeout: int = 180) -> str:
    cuerpo = json.dumps({'model': modelo, 'temperature': 0, 'max_tokens': 700,
                         'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]}).encode()
    req = urllib.request.Request(url.rstrip('/') + '/chat/completions', data=cuerpo,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)['choices'][0]['message']['content']


def leer_json(raw: str) -> dict | None:
    m = re.search(r'\{.*\}', raw or '', re.S)
    try:
        d = json.loads(m.group(0)) if m else None
    except ValueError:
        return None
    return d if isinstance(d, dict) else None


def clasificar(art: dict, ctx: str, args) -> dict:
    texto, err = art['texto'], 'no cupo en el contexto'
    for intento in range(4):
        user = (f'{ctx}\n\nARTÍCULO ({art["codigo"]}):\n{art["ruta"]}\n\n{texto[:MAX_TEXTO]}'
                + ('\n[…artículo recortado…]' if len(texto) > MAX_TEXTO else ''))
        t0 = time.time()
        try:
            raw = llamar(args.url, args.modelo, SYSTEM, user)
        except urllib.error.HTTPError as e:
            if e.code == 400 and len(texto) > 1500:     # casi siempre: no cabe en el contexto → se recorta y reintenta
                texto = texto[:len(texto) // 2]
                continue
            raw, err = None, f'HTTP {e.code}'
        except Exception as e:                          # red, vLLM reiniciando: se espera y se reintenta
            raw, err = None, repr(e)
        if raw is not None:
            d = leer_json(raw)
            if d is not None:
                return {'respuesta': d, 'raw': raw, 'segundos': round(time.time() - t0, 1),
                        'recortado': len(art['texto']) > min(len(texto), MAX_TEXTO)}
            err = 'JSON inválido'
        time.sleep(5 * (intento + 1))
    raise RuntimeError(err)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('carpeta', type=Path)
    ap.add_argument('--url', default='http://localhost:8000/v1')
    ap.add_argument('--modelo', default='gemma-4-31b')
    ap.add_argument('--hilos', type=int, default=8)
    ap.add_argument('--limite', type=int, default=0, help='solo los primeros N pendientes (prueba)')
    ap.add_argument('--codigo', help='solo un código: cdmx, queretaro, edomex, morelos, federal')
    args = ap.parse_args()

    cat = json.loads((args.carpeta / 'catalogo.json').read_text())
    articulos = [json.loads(l) for l in open(args.carpeta / 'articulos.jsonl')]
    if args.codigo:
        articulos = [a for a in articulos if a['codigo'] == args.codigo]
    firma = {'prompt_md5': md5(SYSTEM), 'catalogo_md5': cat['md5'], 'modelo': args.modelo}
    salida = args.carpeta / 'resultados.jsonl'
    hechos = set()
    if salida.exists():
        for l in open(salida):
            try:
                r = json.loads(l)
            except ValueError:
                continue                                # línea cortada a la mitad por un corte: se rehace
            if r.get('prompt_md5') == firma['prompt_md5'] and r.get('catalogo_md5') == firma['catalogo_md5']:
                hechos.add((r['codigo'], r['ruta']))
    pendientes = [a for a in articulos if (a['codigo'], a['ruta']) not in hechos]
    if args.limite:
        pendientes = pendientes[:args.limite]
    print(f'{len(articulos)} artículos · {len(hechos)} ya hechos · {len(pendientes)} pendientes · '
          f'prompt {firma["prompt_md5"][:8]} · catálogo {cat["md5"][:8]}', flush=True)

    contextos = {c: contexto(cat['doc'], c) for c in {a['codigo'] for a in pendientes}}
    lock, t0, listos, fallidos = threading.Lock(), time.time(), 0, 0
    with open(salida, 'a') as f, ThreadPoolExecutor(args.hilos) as pool:
        futuros = {pool.submit(clasificar, a, contextos[a['codigo']], args): a for a in pendientes}
        for fut in as_completed(futuros):
            a = futuros[fut]
            try:
                r = fut.result()
            except Exception as e:
                fallidos += 1
                print(f'  falló {a["codigo"]} {a["num"] or a["ruta"][-40:]}: {e}', file=sys.stderr, flush=True)
                continue
            with lock:
                f.write(json.dumps({'codigo': a['codigo'], 'ruta': a['ruta'], 'num': a['num'], **firma, **r},
                                   ensure_ascii=False) + '\n')
                f.flush()
                listos += 1
            if listos % 25 == 0:
                vel = listos / (time.time() - t0)
                print(f'  {listos}/{len(pendientes)} · {vel * 60:.0f}/min · faltan ~'
                      f'{(len(pendientes) - listos) / vel / 60:.0f} min', flush=True)
    print(f'listo: {listos} nuevos, {fallidos} fallidos (vuelve a correr el comando para reintentarlos)')


if __name__ == '__main__':
    main()
