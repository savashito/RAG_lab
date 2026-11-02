"""Cómo pregunta la gente según su formación jurídica, y si el asistente la guía. Por situación: rasgos del 1er
mensaje (estado, delito, ley o artículo, palabras), recall@10 del buscador, y — cuando el 1er mensaje no nombra el
estado — si el asistente lo pidió, si la persona lo dio después y el recall@10 del mensaje en que lo dio.
Rondas 1 y 2. Bootstrap por participante (4000 réplicas, IC 95 %). Solo agregados.
    python como_preguntan.py > como_preguntan.json"""
import json, random, re, sys
from collections import defaultdict
sys.path.insert(0, '/tmp')
import analisis_ronda2 as A                       # noqa: E402
from study.analisis import grupo_de               # noqa: E402

rng = random.Random(1)
EST = re.compile(r'(?i)quer[eé]taro|ciudad de m[eé]xico|cdmx|\bdf\b|morelos|estado de m[eé]xico')
LEY = re.compile(r'(?i)c[oó]digo|\bley\b|art[ií]culo|\bart\.')
DEL = re.compile(r'(?i)hostigamiento|acoso|extorsi[oó]n|sextorsi|lesiones|ri[ñn]a|delito')


def media(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def situaciones(eid, ronda):
    d, _ = A.cargar(eid)
    part = {p['codigo']: p for p in d['participantes']}
    turnos = defaultdict(list)
    for t in d['turnos']:
        turnos[t['intento_id']].append(t)
    out = []
    for i in d['intentos']:
        p = part.get(i['codigo'])
        ts = sorted(turnos[i['id']], key=lambda t: t['n'])
        if not p or not ts:
            continue
        t1, q1 = ts[0], ts[0]['pregunta'] or ''
        sin_estado = not EST.search(q1)
        pidio = bool(t1.get('a') and t1['a']['pide_lugar_estricto'])
        luego = next((t for t in ts[1:] if EST.search(t['pregunta'] or '')), None)
        out.append({
            'ronda': ronda, 'persona': i['codigo'], 'fo': 'con' if grupo_de(p) in ('derecho', 'estudiante') else 'sin',
            'r10_1er': t1.get('r10'), 'estado_1er': float(not sin_estado), 'delito_1er': float(bool(DEL.search(q1))),
            'ley_1er': float(bool(LEY.search(q1))), 'palabras_1er': len(q1.split()), 'mensajes': len(ts),
            'r10_mejor': max([t['r10'] for t in ts if t.get('r10') is not None], default=None),
            # Solo situaciones cuyo 1er mensaje no nombra el estado:
            'asistente_pidio_estado': float(pidio) if sin_estado else None,
            'persona_dio_estado_despues': float(bool(luego)) if sin_estado else None,
            'dio_estado_si_se_lo_pidieron': float(bool(luego)) if sin_estado and pidio else None,
            'r10_al_dar_estado': luego.get('r10') if sin_estado and luego else None,
            'r10_1er_sin_estado': t1.get('r10') if sin_estado else None,
        })
    return out


M = ['r10_1er', 'estado_1er', 'delito_1er', 'ley_1er', 'palabras_1er', 'mensajes', 'r10_mejor', 'r10_1er_sin_estado',
     'asistente_pidio_estado', 'persona_dio_estado_despues', 'dio_estado_si_se_lo_pidieron', 'r10_al_dar_estado']


def dif(sa, sb, m):
    pa, pb = defaultdict(list), defaultdict(list)
    for s in sa:
        pa[s['persona']].append(s)
    for s in sb:
        pb[s['persona']].append(s)
    A_, B_ = list(pa.values()), list(pb.values())
    mu = lambda ps: media([s[m] for p in ps for s in p])
    if not A_ or not B_ or mu(A_) is None or mu(B_) is None:
        return None
    bs = sorted((mu([rng.choice(B_) for _ in B_]) or 0) - (mu([rng.choice(A_) for _ in A_]) or 0) for _ in range(4000))
    return [round(mu(B_) - mu(A_), 3), round(bs[100], 3), round(bs[3899], 3)]


out = {}
for eid, ronda in (('piloto_penal', 'ronda 1'), ('ronda2_penal', 'ronda 2')):
    ss = situaciones(eid, ronda)
    g = {fo: [s for s in ss if s['fo'] == fo] for fo in ('sin', 'con')}
    out[ronda] = {fo: {'personas': len({s['persona'] for s in v}), 'situaciones': len(v),
                       **{m: [round(media([s[m] for s in v]), 3) if media([s[m] for s in v]) is not None else None,
                              sum(1 for s in v if s[m] is not None)] for m in M}} for fo, v in g.items()}
    out[ronda]['con − sin'] = {m: dif(g['sin'], g['con'], m) for m in M}
print(json.dumps(out, ensure_ascii=False, indent=1))
