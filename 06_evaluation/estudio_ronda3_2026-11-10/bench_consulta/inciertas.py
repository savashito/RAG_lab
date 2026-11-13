"""
Benchmark de reglas inciertas: ¿el LLM que orienta trata una regla incierta como si aplicara?

Una regla es incierta cuando falta un dato de su condición `cuando` (la persona no sabe). Hoy sus artículos entran al
contexto y el prompt dice «si una regla está marcada como incierta, di qué dato falta para saber si aplica». Este script
mide cuántas veces el LLM no hace caso y presenta el delito como si aplicara.

Cómo:
  1. Simula cada caso de casos.yaml con la máquina de estados y el LLM de la app hasta la primera orientación (igual que
     el benchmark de la consulta) y guarda el expediente y la conversación.
  2. Arma variantes del expediente: la natural (si ya tiene reglas inciertas) y una por cada dato de una condición que
     la persona sí contestó, cambiado a «no sabe» (mi código recalcula las reglas con maquina.salida_orientar). Solo
     quedan las variantes con al menos una regla incierta.
  3. El LLM de la app redacta la orientación (mismo prompt de sistema y contexto 'todos' que Preguntar (Catálogo)).
  4. El mismo LLM califica, por cada regla incierta: «aplica» (presenta el delito o sus penas como si aplicaran, sin
     decir que depende del dato), «condiciona» (dice que depende del dato o lo pregunta) o «no_menciona»; y si la
     conversación ya dice el dato (entonces suponerlo no es un error del LLM).

Corre donde la app alcanza al LLM y a la base (en producción):

    cd ~/apps/RAG_lab && set -a && . apps/rewrite_lab/.env; set +a
    PYTHONPATH=apps/rewrite_lab:. .venv/bin/python 06_evaluation/estudio_ronda3_2026-11-10/bench_consulta/inciertas.py [--reps 2]

Escribe resultados/inciertas_<fecha>_<md5 del catálogo>.jsonl y .md. Los casos son inventados: se pueden commitear.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import yaml

from consulta import bench as B
from consulta import expediente as E
from consulta import maquina as M
from consulta import orientar as O
from consulta.catalogo import md5_de
from consulta.ia import ConsultaIA, _json
from shared.db import connect
from shared.llm_client import LlamaClient

AQUI = Path(__file__).resolve().parent
APP = AQUI.parents[2] / 'apps' / 'rewrite_lab'
PROMPT = 'intermedio'          # el prompt de sistema por omisión de Preguntar (Catálogo): ronda2:intermedio
TABLE = os.environ.get('LEGAL_TABLE', 'sistema_penal__qwen06__legal')
GENERALES = {'lugar_hechos', 'papel'}

JUEZ = """Calificas la respuesta de un asistente jurídico. Recibes la CONVERSACIÓN con la persona, la RESPUESTA del
asistente y unas REGLAS: delitos que aplican solo si se cumple una condición que todavía no se sabe (el DATO que falta).

Para cada regla, di cómo la trata la respuesta:
  "aplica": presenta el delito, sus artículos o sus penas como si aplicaran al caso, sin decir que depende del dato.
  "condiciona": la menciona y dice que depende del dato (o lo pregunta), o la presenta como posibilidad.
  "no_menciona": no habla de ese delito.
Y si la CONVERSACIÓN ya dice el dato (aunque el expediente diga que no se sabe): "dato_en_conversacion": true/false.

Responde SOLO un JSON: {"reglas": [{"id": "r014", "trato": "aplica|condiciona|no_menciona",
"dato_en_conversacion": true|false, "cita": "frase corta de la respuesta que lo muestra, o vacío"}]}"""


def system_prompt() -> str:
    doc = yaml.safe_load((APP / 'study' / 'estudios' / 'ronda2_penal.yaml').read_text())
    c = next(c for c in doc['condiciones'] if c['id'] == PROMPT)
    return (c.get('asistente') or {}).get('sistema') or c['sistema']


def variantes(exp: dict, catalogo: dict) -> list[dict]:
    """[{nombre, expediente, salida, faltan: {regla: [datos]}}] con al menos una regla incierta."""
    out = []
    base, _ = M.salida_orientar(exp, catalogo)
    if base['inciertas']:
        out.append({'nombre': 'natural', 'expediente': exp, 'salida': base})
    reglas = {r['id']: r for r in catalogo['reglas']}
    usados = []
    for rid in base['reglas']:
        for c in reglas[rid].get('cuando') or []:
            d = E._dato_de(c)
            if d and d not in GENERALES and d in exp['datos'] and d not in usados:
                usados.append(d)
    for d in usados:
        x = {**exp, 'datos': {k: v for k, v in exp['datos'].items() if k != d},
             'no_sabe': list(exp.get('no_sabe', [])) + [d]}
        s, _ = M.salida_orientar(x, catalogo)
        if s['inciertas']:
            out.append({'nombre': f'{d} = no sabe', 'expediente': x, 'salida': s})
    for v in out:
        datos = {**v['expediente']['datos'], **{k: E.NO_SABE for k in v['expediente'].get('no_sabe', [])}}
        v['faltan'] = {rid: [E._dato_de(c) for c in reglas[rid].get('cuando') or [] if E.evaluar(c, datos) is None]
                       for rid in v['salida']['inciertas']}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--caso', nargs='*')
    ap.add_argument('--reps', type=int, default=2, help='orientaciones por variante')
    ap.add_argument('--hilos', type=int, default=4)
    args = ap.parse_args()
    casos = yaml.safe_load((AQUI / 'casos.yaml').read_text())['casos']
    if args.caso:
        casos = [c for c in casos if c['id'] in args.caso]
    with connect() as c, c.cursor() as cur:
        cur.execute('SELECT doc FROM consulta_catalogo WHERE id = 1')
        catalogo = cur.fetchone()[0]
    md5 = md5_de(catalogo)[:8]
    llm = LlamaClient()
    ia, system = ConsultaIA(llm), system_prompt()
    reglas = {r['id']: r for r in catalogo['reglas']}
    datos_cat = {d['id']: d for d in catalogo['datos']}

    def simular(caso):
        r = B.simular(caso, catalogo, ia)
        print(f'simulado {caso["id"]}', flush=True)
        return caso, r

    with ThreadPoolExecutor(args.hilos) as pool:
        simulados = list(pool.map(simular, casos))
    trabajos = []
    for caso, r in simulados:
        if r['salida'].get('tipo') != 'orientar':
            continue
        # la conversación hasta la primera orientación (sin los complementarios que vienen después)
        conv = []
        for m in r['conversacion']:
            if m['role'] == 'assistant' and m['content'].startswith('[orientación]'):
                break
            conv.append(m)
        conversacion = '\n'.join(f'{"Persona" if m["role"] == "user" else "Asistente"}: {m["content"]}' for m in conv)
        for v in variantes(r['expediente'], catalogo):
            for rep in range(1, args.reps + 1):
                trabajos.append((caso['id'], conversacion, v, rep))
    print(f'{len(trabajos)} orientaciones', flush=True)

    def correr(t):
        cid, conversacion, v, rep = t
        with connect() as c, c.cursor() as cur:
            prep = O.preparar(cur=cur, table=TABLE, salida=v['salida'], expediente=v['expediente'], catalogo=catalogo,
                              conversacion=conversacion, contexto='todos', embed=None, valores={})
        try:
            respuesta = llm.chat(system, prep['user'], max_tokens=4096, timeout=300)
        except Exception as e:               # un error del LLM (p. ej. 500) no tumba la corrida: queda anotado
            cuerpo = getattr(e, 'read', lambda: b'')()[:300].decode(errors='replace')
            print(f'{cid:24} {v["nombre"]:32} rep {rep}: ERROR {e} {cuerpo} · ~{prep["tokens_contexto"]} tokens', flush=True)
            return {'filas': [], 'error': f'{e} {cuerpo}', 'tokens_contexto': prep['tokens_contexto']}
        lista = '\n'.join(f'- {rid}: {reglas[rid]["delito"]}' + (f' ({reglas[rid]["condicion"]})' if reglas[rid].get('condicion') else '')
                          + ' · DATO que falta: ' + '; '.join(f'{d} («{datos_cat.get(d, {}).get("pregunta", d)}»)' for d in ds)
                          for rid, ds in v['faltan'].items())
        raw = llm.chat(JUEZ, f'CONVERSACIÓN:\n{conversacion}\n\nRESPUESTA:\n{respuesta}\n\nREGLAS:\n{lista}',
                       max_tokens=1500, timeout=180)
        juicio = {x.get('id'): x for x in ((_json(raw) or {}).get('reglas') or []) if isinstance(x, dict)}
        filas = [{'caso': cid, 'variante': v['nombre'], 'rep': rep, 'regla': rid, 'delito': reglas[rid]['delito'],
                  'falta': ds, 'trato': (juicio.get(rid) or {}).get('trato', 'sin_juicio'),
                  'dato_en_conversacion': bool((juicio.get(rid) or {}).get('dato_en_conversacion')),
                  'cita': (juicio.get(rid) or {}).get('cita', '')} for rid, ds in v['faltan'].items()]
        print(f'{cid:24} {v["nombre"]:32} rep {rep}: ' + ', '.join(f'{f["regla"]} {f["trato"]}' for f in filas), flush=True)
        return {'filas': filas, 'respuesta': respuesta, 'juez': raw, 'tokens_contexto': prep['tokens_contexto']}

    with ThreadPoolExecutor(args.hilos) as pool:
        res = list(pool.map(correr, trabajos))

    salida = AQUI / 'resultados' / f'inciertas_{datetime.now():%Y-%m-%d_%H%M}_{md5}'
    salida.parent.mkdir(exist_ok=True)
    with open(salida.with_suffix('.jsonl'), 'w') as f:
        for t, x in zip(trabajos, res):
            f.write(json.dumps({'caso': t[0], 'variante': t[2]['nombre'], 'rep': t[3], **x}, ensure_ascii=False) + '\n')
    filas = [f for x in res for f in x['filas']]
    limpias = [f for f in filas if not f['dato_en_conversacion']]
    cuenta = Counter(f['trato'] for f in limpias)
    mencionadas = cuenta['aplica'] + cuenta['condiciona']
    out = [f'# Reglas inciertas · catálogo {md5} · {datetime.now():%Y-%m-%d %H:%M}', '',
           f'{len(trabajos)} orientaciones ({args.reps} por variante), {len(filas)} reglas inciertas calificadas. '
           f'El LLM que orienta y el que califica es el de la app ({llm.model}). '
           f'Orientaciones con error del LLM: {sum(bool(x.get("error")) for x in res)}.', '',
           f'Sin contar las {len(filas) - len(limpias)} en que la conversación ya dice el dato:', '',
           '| Trato | Reglas |', '|---|---|'] + [f'| {k} | {v} |' for k, v in cuenta.most_common()] + [
           '', f'**Trata la regla como si aplicara: {cuenta["aplica"]}/{mencionadas} de las que menciona '
           f'({100 * cuenta["aplica"] / max(mencionadas, 1):.0f} %).**', '', '## Por regla', '',
           '| Caso | Variante | Regla | Dato que falta | Trato | ¿Dato en la conversación? | Cita |', '|---|---|---|---|---|---|---|']
    for f in filas:
        out.append(f'| {f["caso"]} | {f["variante"]} | {f["regla"]} {f["delito"][:40]} | {", ".join(f["falta"])} | '
                   f'{f["trato"]} | {"sí" if f["dato_en_conversacion"] else "no"} | {f["cita"][:120].replace("|", "/")} |')
    salida.with_suffix('.md').write_text('\n'.join(out) + '\n')
    print(f'→ {salida}.md')


if __name__ == '__main__':
    main()
