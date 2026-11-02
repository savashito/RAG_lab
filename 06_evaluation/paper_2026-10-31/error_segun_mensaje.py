"""Ronda 1 (y repetición en ronda 2): ¿la 1a respuesta nombra el código de otro estado más cuando el 1er mensaje de la
persona no nombra el estado? Por formación jurídica. Bootstrap por participante. Solo agregados.
    python error_segun_mensaje.py > error_segun_mensaje.json"""
import json, random, re, sys
from collections import defaultdict
sys.path.insert(0, '/tmp')
import analisis_ronda2 as A                       # noqa: E402
from study.analisis import grupo_de               # noqa: E402

rng = random.Random(1)
EST = re.compile(r'(?i)quer[eé]taro|ciudad de m[eé]xico|cdmx|\bdf\b|morelos|estado de m[eé]xico')
out = {}
for eid in ('piloto_penal', 'ronda2_penal'):
    d, _ = A.cargar(eid)
    part = {p['codigo']: p for p in d['participantes']}
    t1 = {}
    for t in sorted(d['turnos'], key=lambda t: t['n']):
        t1.setdefault(t['intento_id'], t)
    per = defaultdict(list)
    for i in d['intentos']:
        p, t = part.get(i['codigo']), t1.get(i['id'])
        if not p or not t or not t.get('respuesta'):
            continue
        per[i['codigo']].append({'fo': 'con' if grupo_de(p) in ('derecho', 'estudiante') else 'sin',
                                 'nombra': bool(EST.search(t['pregunta'] or '')),
                                 'mal': float(A.otro_estado(t['respuesta'], i['escenario'], i['variante']))})
    res = {}
    for fo in ('todos', 'sin', 'con'):
        ps = [[s for s in v if fo == 'todos' or s['fo'] == fo] for v in per.values()]
        ps = [p for p in ps if p]
        def r(b, nombra):
            xs = [s['mal'] for p in b for s in p if s['nombra'] == nombra]
            return (sum(xs) / len(xs), len(xs)) if xs else (None, 0)
        bs = []
        for _ in range(4000):
            b = [rng.choice(ps) for _ in ps]
            a, c = r(b, False)[0], r(b, True)[0]
            if a is not None and c is not None:
                bs.append(a - c)
        bs.sort()
        res[fo] = {'no nombra el estado': [round(r(ps, False)[0], 3), r(ps, False)[1]],
                   'nombra el estado': [round(r(ps, True)[0], 3), r(ps, True)[1]],
                   'no − sí': [round(r(ps, False)[0] - r(ps, True)[0], 3), round(bs[100], 3), round(bs[3899], 3)]}
    out[eid] = res
print(json.dumps(out, ensure_ascii=False, indent=1))
