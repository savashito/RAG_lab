"""Carga en la página 🔁 Ronda 1 real (tablas rep_*) las repeticiones hechas con repetir_ronda1.py (/tmp/replay_ronda1/).
Cada respuesta se vuelve a medir con las métricas corregidas. No toca lo ya cargado (se salta los nombres+repetición que
ya existen) ni carga corridas incompletas.   python importar_a_la_pagina.py"""
import json, sys, os
from pathlib import Path
RAIZ = Path('/home/tlacua/apps/RAG_lab')
sys.path[:0] = [str(RAIZ / 'apps' / 'rewrite_lab'), str(RAIZ)]
os.chdir(RAIZ / 'apps' / 'rewrite_lab')
from dotenv import load_dotenv; load_dotenv('.env')
from shared.db import connect                       # noqa: E402
from study.store import StudyStore                  # noqa: E402
import repeticiones as rp                           # noqa: E402

store = StudyStore(connect, Path('/nonexistent'))
def gold_refs(t):
    from bench import gold_refs as g
    return g('', [{'kind': 'must', 'text': t}])
def resolver(grupos):
    from bench import resolve_gold
    with connect() as c, c.cursor() as cur:
        return resolve_gold(cur, os.environ.get('LEGAL_TABLE', 'sistema_penal__qwen06__legal'), grupos)
# Sin constructor (no corre SCHEMA/_STALE_SQL: la app ya creó las tablas y podría tener una repetición en curso).
R = rp.Repeticiones.__new__(rp.Repeticiones)
R.connect, R.store, R.resolver, R.gold_refs = connect, store, resolver, gold_refs
base = dict(store.spec('piloto_penal')['asistente'])
CFG = {'A_ronda1': ('penal-original-v1', dict(base, filtro_estado=False), False, 'Como la ronda 1, con el sistema de hoy'),
       'B_filtro': ('penal-original-v1', dict(base, filtro_estado=True), False, 'A + filtro por estado v3'),
       'C_nuevo': ('ultimo-promt-v2', dict(base, filtro_estado=True), False, 'La condición «nuevo» de la ronda 2'),
       'B_condensa_v2': ('penal-original-v1', dict(base, filtro_estado=True, condensa='v2'), True, 'B + búsqueda reescrita v2'),
       'C_condensa_v2': ('ultimo-promt-v2', dict(base, filtro_estado=True, condensa='v2'), True, 'C + búsqueda reescrita v2')}
r1 = R._ronda1()
completa = {False: len(r1['intentos']), True: sum(1 for i in r1['intentos'] if len(r1['turnos'][i['id']]) >= 2)}
with connect() as c, c.cursor() as cur:
    cur.execute('SELECT nombre, repeticion FROM rep_corridas')
    ya = set(cur.fetchall())
for f in sorted(Path('/tmp/replay_ronda1').glob('*_rep*.jsonl')):
    nombre, rep = f.stem.rsplit('_rep', 1)
    if nombre not in CFG or (nombre, int(rep)) in ya:
        continue
    tag, cfg, multi, nota = CFG[nombre]
    filas = [json.loads(l) for l in f.open()]
    if len(filas) < completa[multi]:   # todavía corriendo (o se cortó): no se carga a medias
        print(nombre, rep, f'incompleta ({len(filas)} de {completa[multi]}): no se carga', flush=True)
        continue
    print(nombre, rep, len(filas), '→ corrida', R.importar(nombre, cfg, tag, int(rep), multi, filas, nota), flush=True)
