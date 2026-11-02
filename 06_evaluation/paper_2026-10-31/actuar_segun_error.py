import sys, random
from collections import defaultdict
sys.path.insert(0, '/tmp')
import analisis_ronda2 as A
from study.analisis import grupo_de
rng = random.Random(1)
d, _ = A.cargar('piloto_penal')
part = {p['codigo']: p for p in d['participantes']}
turnos = defaultdict(list)
for t in d['turnos']:
    turnos[t['intento_id']].append(t)
per = defaultdict(lambda: defaultdict(list))
for i in d['intentos']:
    p = part.get(i['codigo'])
    if not p or not i.get('fin'):
        continue
    fo = 'con' if grupo_de(p) in ('derecho', 'estudiante') else 'sin'
    ok = [t for t in turnos[i['id']] if t.get('respuesta')]
    mal = any(A.otro_estado(t['respuesta'], i['escenario'], i['variante']) for t in ok)
    per[fo][i['codigo']].append((mal, i.get('actuaria') == 'si', i.get('detecto') == 'si', i.get('detecto') == 'no_se'))
def rate(ps, mal, k):
    xs = [s[k] for p in ps for s in p if s[0] == mal]
    return sum(xs) / len(xs) if xs else None
for fo, g in per.items():
    ps = list(g.values())
    for k, nom in ((1, 'actuaria'), (2, 'noto'), (3, 'no_seguro')):
        obs = rate(ps, True, k) - rate(ps, False, k)
        bs = []
        for _ in range(4000):
            b = [rng.choice(ps) for _ in ps]
            a, c = rate(b, True, k), rate(b, False, k)
            if a is not None and c is not None:
                bs.append(a - c)
        bs.sort()
        print('IC', fo, nom, 'con error', round(rate(ps, True, k), 3), 'sin error', round(rate(ps, False, k), 3),
              'dif', round(obs, 3), [round(bs[int(.025 * len(bs))], 3), round(bs[int(.975 * len(bs))], 3)],
              'personas', len(ps), 'personas con alguna situacion con error', sum(1 for p in ps if any(s[0] for s in p)))
