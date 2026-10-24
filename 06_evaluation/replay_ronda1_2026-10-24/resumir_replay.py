"""Resumen agregado de repetir_ronda1.py (no imprime mensajes de participantes). Para cada configuración: % de respuestas
que citan otro estado, cuya primera ley es de otro estado, que citan la ley correcta y que piden el estado; en el primer
mensaje de cada situación (métrica principal, no depende de respuestas anteriores) y en todos. Diferencias A→B y A→C
pareadas por conversación (bootstrap, IC 95 %). Incluye la línea base: las respuestas que se guardaron en la ronda 1.
    python resumir_replay.py"""
import json, random, statistics as st, sys
from collections import Counter, defaultdict
from pathlib import Path
RAIZ = Path('/home/tlacua/apps/RAG_lab')
sys.path[:0] = [str(RAIZ / 'apps' / 'rewrite_lab'), str(RAIZ)]
import os; os.chdir(RAIZ / 'apps' / 'rewrite_lab')
import main                                          # noqa: E402
from study.analisis import analizar_respuesta         # noqa: E402
from study.validar import escenario_efectivo          # noqa: E402

SAL = Path('/tmp/replay_ronda1')
# «otros_estados» del análisis de la ronda 1 incluye el CPF (federal) cuando no era el esperado; «otro código estatal» no.
MET = {'cita otro código o el CPF': lambda a: bool(a['otros_estados']),
       'cita otro código estatal': lambda a: any(l != 'CPF' for l in a['otros_estados']),
       'primera ley de otro estado o CPF': lambda a: bool(a['primera_ley_es_otra']),
       'primera ley de otro estado': lambda a: bool(a['primera_ley_es_otra']) and a['primera_ley'] != 'CPF',
       'cita la ley correcta': lambda a: bool(a['cita_ley_gold']), 'pide el estado': lambda a: bool(a['pide_lugar'])}
def pct(xs): return f'{100 * st.mean(xs):.1f} %' if xs else '—'

# Línea base: lo que respondió el asistente en la ronda 1 (guardado), por condición.
datos = main.study_store.export('piloto_penal'); spec = main.study_store.spec('piloto_penal')
por_id = {e['id']: e for e in spec['escenarios']}; cond = {p['codigo']: p['condicion'] or 'piloto' for p in datos['participantes']}
gold = {}
for i in datos['intentos']:
    k = (i['escenario'], i['variante'])
    if k not in gold and i['escenario'] in por_id:
        ef = escenario_efectivo(por_id[i['escenario']], i['variante'])
        gold[k] = main._study_resolver([g for x in ef.get('gold') or [] for g in main._study_gold_refs(x)])
intento = {i['id']: i for i in datos['intentos']}
base = defaultdict(lambda: defaultdict(list)); md5s = Counter()
for t in datos['turnos']:
    if not t['respuesta']:
        continue
    i = intento[t['intento_id']]; c = cond.get(i['codigo'], '?'); md5s[(c, (t['sistema_md5'] or '')[:8])] += 1
    a = analizar_respuesta(t['respuesta'], gold.get((i['escenario'], i['variante'])) or [])
    for alcance in (['primer mensaje'] if t['n'] == 1 else []) + ['todos']:
        for m, f in MET.items():
            base[(c, alcance)][m].append(f(a))
print('== Ronda 1 tal como pasó (respuestas guardadas) · prompt por condición:', dict(md5s))
for (c, alcance), ms in sorted(base.items()):
    print(f'  {c:9} · {alcance:14} · n={len(ms["pide el estado"]):3} · ' + ' · '.join(f'{m} {pct(v)}' for m, v in ms.items()))

# Repetición.
filas = defaultdict(dict)   # (config, rep) → intento_id → fila
for f in sorted(SAL.glob('*_rep*.jsonl')):
    cfg, rep = f.stem.rsplit('_rep', 1)
    for l in f.open():
        x = json.loads(l); filas[(cfg, int(rep))][x['intento_id']] = x
configs = sorted({c for c, _ in filas})
print('\n== Repetición con los mensajes reales (promedio de las repeticiones)')
def valores(cfg, alcance, m):
    """Por conversación: promedio entre repeticiones de la métrica (primer mensaje, o proporción en todos sus mensajes)."""
    out = defaultdict(list)
    for (c, rep), xs in filas.items():
        if c != cfg:
            continue
        for iid, x in xs.items():
            ts = x['turnos'][:1] if alcance == 'primer mensaje' else x['turnos']
            out[iid].append(st.mean(MET[m](t['analisis']) for t in ts))
    return {iid: st.mean(v) for iid, v in out.items()}
for alcance in ('primer mensaje', 'todos'):
    for cfg in configs:
        reps = sorted(r for c, r in filas if c == cfg)
        print(f'  {cfg:9} · {alcance:14} · reps {reps} · ' + ' · '.join(
            f'{m} {100 * st.mean(valores(cfg, alcance, m).values()):.1f} %' for m in MET))
random.seed(1)
print('\n== Diferencias pareadas por conversación (puntos porcentuales, IC 95 %)')
for a, b in (('A_ronda1', 'B_filtro'), ('A_ronda1', 'C_nuevo'), ('B_filtro', 'C_nuevo')):
    if a not in configs or b not in configs:
        continue
    for alcance in ('primer mensaje', 'todos'):
        partes = []
        for m in MET:
            va, vb = valores(a, alcance, m), valores(b, alcance, m)
            d = [vb[i] - va[i] for i in va if i in vb]
            bs = sorted(st.mean(random.choices(d, k=len(d))) for _ in range(5000))
            partes.append(f'{m} {100 * st.mean(d):+.1f} [{100 * bs[125]:+.1f}, {100 * bs[4875]:+.1f}]')
        print(f'  {a} → {b} · {alcance} (n={len(d)}): ' + ' · '.join(partes))

print('\n== Qué decidió el filtro en el primer mensaje, por situación (B_filtro, todas las repeticiones)')
dec = defaultdict(Counter)
for (c, rep), xs in filas.items():
    if c != 'B_filtro':
        continue
    for x in xs.values():
        fl = x['turnos'][0].get('filtro') or {}
        dec[(x['escenario'], x['variante'])][', '.join(fl.get('estados') or []) or f'ninguno ({fl.get("tipo")})'] += 1
for k, cnt in sorted(dec.items(), key=str):
    print(f'  {k[0]} {k[1] or ""}: ' + ' · '.join(f'{e}: {n}' for e, n in cnt.most_common()))
seg = defaultdict(list)
for (c, rep), xs in filas.items():
    seg[c] += [t['segundos'] for x in xs.values() for t in x['turnos']]
print('\nSegundos por mensaje:', {c: f'{st.mean(v):.1f} ± {st.stdev(v):.1f}' for c, v in seg.items() if len(v) > 1})
