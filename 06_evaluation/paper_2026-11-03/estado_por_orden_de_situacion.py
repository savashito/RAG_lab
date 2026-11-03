import re, sys, json
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
por = defaultdict(list)
for i in d['intentos']:
    if i['codigo'] in part and i['id'] in t1:
        por[i['codigo']].append(i)
agg = defaultdict(lambda: defaultdict(list))
for c, its in por.items():
    p = part[c]; fo = 'con' if grupo_de(p) in ('derecho', 'estudiante') else 'sin'
    for k, i in enumerate(sorted(its, key=lambda i: str(i['inicio']))):
        t = t1[i['id']]
        lugar = 'primera' if k == 0 else 'segunda o tercera'
        for g in (f'{fo} {p["condicion"]}', f'todos {p["condicion"]}', 'todos'):
            agg[g][lugar + ' · estado'].append(float(bool(EST.search(t['pregunta'] or ''))))
            if t.get('r10') is not None:
                agg[g][lugar + ' · r10'].append(t['r10'])
print('ORDEN', json.dumps({g: {k: [round(sum(v)/len(v), 2), len(v)] for k, v in m.items()} for g, m in sorted(agg.items())}, ensure_ascii=False, indent=0))
