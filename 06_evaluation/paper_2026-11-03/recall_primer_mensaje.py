"""Recall@10 del 1er mensaje en la ronda 2, por prompt, formación y situación, y rasgos del 1er mensaje. Solo agregados."""
import re, sys, json, random
from collections import defaultdict
sys.path.insert(0, '/tmp')
import analisis_ronda2 as A
from study.analisis import grupo_de
d, _ = A.cargar('ronda2_penal')
part = {p['codigo']: p for p in d['participantes']}
t1 = {}
for t in sorted(d['turnos'], key=lambda t: t['n']):
    t1.setdefault(t['intento_id'], t)
EST = re.compile(r'(?i)quer[eé]taro|ciudad de m[eé]xico|cdmx|\bdf\b|morelos|estado de m[eé]xico')
LEY = re.compile(r'(?i)c[oó]digo|\bley\b|art[ií]culo|\bart\.')
DEL = re.compile(r'(?i)hostigamiento|acoso|extorsi[oó]n|sextorsi|lesiones|ri[ñn]a|delito')
filas = []
for i in d['intentos']:
    p, t = part.get(i['codigo']), t1.get(i['id'])
    if not p or not t or t.get('r10') is None:
        continue
    q = t['pregunta'] or ''
    filas.append({'persona': i['codigo'], 'prompt': p['condicion'], 'fo': 'con' if grupo_de(p) in ('derecho', 'estudiante') else 'sin',
                  'esc': i['escenario'], 'r10': t['r10'], 'palabras': len(q.split()), 'estado': float(bool(EST.search(q))),
                  'ley': float(bool(LEY.search(q))), 'delito': float(bool(DEL.search(q)))})
def m(xs): return round(sum(xs) / len(xs), 3) if xs else None
out = {}
for fo in ('con', 'sin'):
    for c in ('original', 'nuevo', 'intermedio'):
        s = [f for f in filas if f['fo'] == fo and f['prompt'] == c]
        out[f'{fo} {c}'] = {'n': len(s), 'personas': len({f['persona'] for f in s}), **{k: m([f[k] for f in s]) for k in ('r10', 'palabras', 'estado', 'ley', 'delito')},
                            'r10_por_situacion': {e: [m([f['r10'] for f in s if f['esc'] == e]), sum(1 for f in s if f['esc'] == e)] for e in ('mensajes_trabajo', 'fotos', 'citatorio')}}
# recall según rasgos, todas las personas
for k in ('estado', 'ley', 'delito'):
    out[f'r10 si el 1er mensaje {k}'] = {'sí': [m([f['r10'] for f in filas if f[k] == 1]), sum(1 for f in filas if f[k] == 1)],
                                          'no': [m([f['r10'] for f in filas if f[k] == 0]), sum(1 for f in filas if f[k] == 0)]}
out['r10 por situación (todos)'] = {e: [m([f['r10'] for f in filas if f['esc'] == e]), sum(1 for f in filas if f['esc'] == e)] for e in ('mensajes_trabajo', 'fotos', 'citatorio')}
# recall por persona, con formación y nuevo: ¿uno o dos que suben el promedio?
out['con nuevo: recall por persona'] = sorted(round(m([f['r10'] for f in filas if f['persona'] == p]), 2) for p in {f['persona'] for f in filas if f['fo'] == 'con' and f['prompt'] == 'nuevo'})
out['con original: recall por persona'] = sorted(round(m([f['r10'] for f in filas if f['persona'] == p]), 2) for p in {f['persona'] for f in filas if f['fo'] == 'con' and f['prompt'] == 'original'})
print(json.dumps(out, ensure_ascii=False, indent=1))
