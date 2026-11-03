"""Dos pruebas para el paper. Solo agregados.
1. ¿La persona acierta más «¿qué delito y qué ley?» cuando el asistente citó el artículo correcto en esa situación?
   (mensajes_trabajo y fotos, las dos situaciones con esa pregunta; ronda 1 con el gold de la v7 archivada).
2. Ronda 2 solo con quienes aceptaron el consentimiento desde que existe el prompt intermedio (v16, 28-oct): los tres
   prompts reclutados en la misma época.
Bootstrap por participante (4000 réplicas, IC 95 %).
    python pruebas_aprendizaje_y_fecha.py > pruebas.json"""
import json, random, sys
from collections import Counter, defaultdict
sys.path.insert(0, '/tmp')
import analisis_ronda2 as A                       # noqa: E402  (carga main y las métricas)
from study.analisis import grupo_de               # noqa: E402

rng = random.Random(1)


def media(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def boot(grupos_a, grupos_b, f):
    """f(lista de situaciones) → valor; grupos = {persona: [situaciones]}. Devuelve [B − A, IC 2.5 %, IC 97.5 %]."""
    A_, B_ = list(grupos_a.values()), list(grupos_b.values())
    mu = lambda ps: f([s for p in ps for s in p])
    if not A_ or not B_ or mu(A_) is None or mu(B_) is None:
        return None
    bs = sorted((mu([rng.choice(B_) for _ in B_]) or 0) - (mu([rng.choice(A_) for _ in A_]) or 0) for _ in range(4000))
    return [round(mu(B_) - mu(A_), 3), round(bs[100], 3), round(bs[3899], 3)]


def situaciones(eid, ronda):
    d, _ = A.cargar(eid)
    part = {p['codigo']: p for p in d['participantes']}
    turnos = defaultdict(list)
    for t in d['turnos']:
        turnos[t['intento_id']].append(t)
    out = []
    for i in d['intentos']:
        p = part.get(i['codigo'])
        if not p or not i.get('fin'):
            continue
        ts = sorted(turnos[i['id']], key=lambda t: t['n'])
        ok = [t for t in ts if t.get('a')]
        det = (i.get('comprension') or {}).get('detalle') or {}
        r = i.get('respuestas') or {}
        out.append({
            'ronda': ronda, 'persona': i['codigo'], 'prompt': p['condicion'] or 'piloto', 'version': i.get('version'),
            'consentimiento_at': str(p.get('consentimiento_at') or ''),
            'formacion': 'con' if grupo_de(p) in ('derecho', 'estudiante') else 'sin', 'escenario': i['escenario'],
            'acierta_ley': float(bool(det['ley'])) if 'ley' in det else None,
            'articulo_1a': None if not ok or ok[0]['n'] != ts[0]['n'] or ok[0]['a']['cita_articulo_gold'] is None else float(ok[0]['a']['cita_articulo_gold']),
            'articulo_alguna': None if not ok else float(any(t['a']['cita_articulo_gold'] for t in ok)),
            'comprension': media([float(bool(v)) for v in det.values()]) if det else None,
            'escala_confianza_asistente': r.get('escala_confianza_asistente') if isinstance(r.get('escala_confianza_asistente'), int) else None,
            'confianza_1a5': i.get('confianza'),
            'actuaria': None if not i.get('actuaria') else float(i['actuaria'] == 'si'),
            'noto_problema': None if not i.get('detecto') else float(i['detecto'] == 'si'),
        })
    return out


r1, r2 = situaciones('piloto_penal', 'r1'), situaciones('ronda2_penal', 'r2')
out = {'versiones_ronda1': Counter(s['version'] for s in r1)}

# ── Prueba 1
def por_persona(ss):
    g = defaultdict(list)
    for s in ss:
        g[s['persona']].append(s)
    return g


p1 = {}
for nombre, ss in (('ronda 1', r1), ('ronda 2', r2), ('las dos rondas', r1 + r2)):
    for fo in ('todos', 'sin', 'con'):
        for esc in ('las dos situaciones', 'mensajes_trabajo', 'fotos'):
            base = [s for s in ss if s['acierta_ley'] is not None and (fo == 'todos' or s['formacion'] == fo)
                    and (esc == 'las dos situaciones' or s['escenario'] == esc)]
            fila = {}
            for cual in ('articulo_1a', 'articulo_alguna'):
                si = [s for s in base if s[cual] == 1.0]
                no = [s for s in base if s[cual] == 0.0]
                f = lambda xs: media([x['acierta_ley'] for x in xs])
                fila[cual] = {'asistente_si_lo_cito': [round(f(si), 3) if si else None, len(si)],
                              'asistente_no_lo_cito': [round(f(no), 3) if no else None, len(no)],
                              'si_menos_no': boot(por_persona(no), por_persona(si), f)}
            p1[f'{nombre} · {fo} · {esc}'] = fila
out['prueba1_acierta_ley_segun_articulo'] = p1

# ── Prueba 2
inicio = min(s['consentimiento_at'] for s in r2 if s['prompt'] == 'intermedio')
out['prueba2_desde'] = inicio
M = ('comprension', 'escala_confianza_asistente', 'confianza_1a5', 'actuaria', 'noto_problema')
p2 = {}
for epoca, ss in (('desde que existe intermedio', [s for s in r2 if s['consentimiento_at'] >= inicio]),
                  ('antes (solo original y nuevo)', [s for s in r2 if s['consentimiento_at'] < inicio]),
                  ('toda la ronda 2', r2)):
    for fo in ('todos', 'sin', 'con'):
        sel = [s for s in ss if fo == 'todos' or s['formacion'] == fo]
        g = {c: [s for s in sel if s['prompt'] == c] for c in ('original', 'nuevo', 'intermedio')}
        tabla = {c: {'personas': len({s['persona'] for s in v}),
                     **{m: [round(media([s[m] for s in v]), 3) if media([s[m] for s in v]) is not None else None,
                            sum(1 for s in v if s[m] is not None)] for m in M}} for c, v in g.items()}
        difs = {m: {f'{b} − {a}': boot(por_persona(g[a]), por_persona(g[b]), lambda xs, m=m: media([x[m] for x in xs]))
                    for a, b in (('original', 'intermedio'), ('nuevo', 'intermedio'), ('original', 'nuevo'))} for m in M}
        p2[f'{epoca} · {fo}'] = {'tabla': tabla, 'diferencias': difs}
out['prueba2_misma_epoca'] = p2
print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
