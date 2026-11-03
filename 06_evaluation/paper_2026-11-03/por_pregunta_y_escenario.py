"""Ronda 1 (piloto_penal) y ronda 2 (ronda2_penal): aciertos por pregunta del cuestionario y métricas por situación
(escenario), por prompt y por formación jurídica. Las 2 preguntas «¿qué delito y qué ley?» dependen de que el
asistente nombre la ley correcta; las otras 4 se pueden contestar sin eso. «No sé» cuenta como error (igual que
puntuar_comprension). Ojo: en «fotos», la respuesta correcta de «ley» fue «ambas» en la ronda 1 y lg_15 en la ronda 2.
Bootstrap por participante (4000 réplicas, IC 95 %). Solo agregados.
    python por_pregunta_y_escenario.py > por_pregunta.json"""
import json, random, sys
from collections import defaultdict
sys.path.insert(0, '/tmp')
import analisis_ronda2 as A                       # noqa: E402  (carga main y las métricas)
from study.analisis import grupo_de               # noqa: E402

rng = random.Random(1)
NOMBRE = {'actual': 'formal', 'original': 'formal', 'sencillo': 'sencillo', 'piloto': 'piloto', 'nuevo': 'nuevo',
          'intermedio': 'intermedio'}


def media(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def filas(eid, ronda):
    d, _ = A.cargar(eid)
    part = {p['codigo']: p for p in d['participantes']}
    turnos = defaultdict(list)
    for t in d['turnos']:
        turnos[t['intento_id']].append(t)
    out = []
    for i in d['intentos']:
        p = part.get(i['codigo'])
        if not p:
            continue
        det = (i.get('comprension') or {}).get('detalle') or {}
        t1 = (sorted(turnos[i['id']], key=lambda t: t['n']) or [None])[0]
        out.append({
            'ronda': ronda, 'persona': i['codigo'], 'prompt': NOMBRE[p['condicion'] or 'piloto'],
            'formacion': 'con' if grupo_de(p) in ('derecho', 'estudiante') else 'sin', 'escenario': i['escenario'],
            'preguntas': {q: float(bool(v)) for q, v in det.items()},
            'comprension': media([float(bool(v)) for v in det.values()]) if det else None,
            'actuaria': None if not i.get('actuaria') else float(i['actuaria'] == 'si'),
            '1a_otro_estado': None if not (t1 and t1.get('respuesta')) else float(A.otro_estado(t1['respuesta'], i['escenario'], i['variante'])),
            '1a_cita_articulo_correcto': None if not (t1 and t1.get('a')) or t1['a']['cita_articulo_gold'] is None else float(t1['a']['cita_articulo_gold']),
        })
    return out


def valor(f, m):
    if m.startswith('p:'):
        _, esc, q = m.split(':')
        return f['preguntas'].get(q) if f['escenario'] == esc else None
    if m == 'ley':                                # las 2 preguntas «¿qué delito y qué ley?»
        return f['preguntas'].get('ley') if f['escenario'] in ('mensajes_trabajo', 'fotos') else None
    if m == 'otras':                              # las 4 que no dependen de la ley citada
        xs = [v for q, v in f['preguntas'].items() if not (q == 'ley' and f['escenario'] in ('mensajes_trabajo', 'fotos'))]
        return media(xs)
    return f[m]


def celda(fs, m):
    xs = [valor(f, m) for f in fs]
    xs = [x for x in xs if x is not None]
    return [round(media(xs), 3) if xs else None, len(xs), len({f['persona'] for f in fs if valor(f, m) is not None})]


def dif(fa, fb, m):
    pa, pb = defaultdict(list), defaultdict(list)
    for f in fa:
        pa[f['persona']].append(f)
    for f in fb:
        pb[f['persona']].append(f)
    A_, B_ = list(pa.values()), list(pb.values())
    mu = lambda ps: media([valor(f, m) for p in ps for f in p])
    if not A_ or not B_ or mu(A_) is None or mu(B_) is None:
        return None
    bs = sorted((mu([rng.choice(B_) for _ in B_]) or 0) - (mu([rng.choice(A_) for _ in A_]) or 0) for _ in range(4000))
    return [round(mu(B_) - mu(A_), 3), round(bs[100], 3), round(bs[3899], 3)]


F = filas('piloto_penal', 'r1') + filas('ronda2_penal', 'r2')
PREG = ['ley', 'otras', 'p:mensajes_trabajo:ley', 'p:mensajes_trabajo:superior', 'p:fotos:consentimiento', 'p:fotos:ley',
        'p:citatorio:codigo', 'p:citatorio:lugar']
GRUPOS = [('r1', 'formal'), ('r1', 'sencillo'), ('r1', 'piloto'), ('r2', 'formal'), ('r2', 'nuevo'), ('r2', 'intermedio')]
out = {}
for fo in ('sin', 'con', 'todos'):
    sel = [f for f in F if fo == 'todos' or f['formacion'] == fo]
    g = {f'{r} {c}': [f for f in sel if f['ronda'] == r and f['prompt'] == c] for r, c in GRUPOS}
    g['r1 todos'] = [f for f in sel if f['ronda'] == 'r1']
    g['r2 todos'] = [f for f in sel if f['ronda'] == 'r2']
    out[f'preguntas_{fo}'] = {m: {k: celda(v, m) for k, v in g.items()} for m in PREG}
    out[f'preguntas_r2_menos_r1_{fo}'] = {m: {'formal': dif(g['r1 formal'], g['r2 formal'], m),
                                              'todos los prompts': dif(g['r1 todos'], g['r2 todos'], m)} for m in PREG}
    out[f'escenarios_{fo}'] = {e: {m: {k: celda([f for f in v if f['escenario'] == e], m) for k, v in g.items()}
                                   for m in ('comprension', 'actuaria', '1a_otro_estado', '1a_cita_articulo_correcto')}
                               for e in ('mensajes_trabajo', 'fotos', 'citatorio')}
    out[f'escenarios_r2_menos_r1_{fo}'] = {e: {m: dif([f for f in g['r1 todos'] if f['escenario'] == e],
                                                      [f for f in g['r2 todos'] if f['escenario'] == e], m)
                                               for m in ('comprension', 'actuaria', '1a_otro_estado', '1a_cita_articulo_correcto')}
                                           for e in ('mensajes_trabajo', 'fotos', 'citatorio')}
print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
