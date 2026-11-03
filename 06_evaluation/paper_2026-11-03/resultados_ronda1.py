"""Ronda 1 (piloto_penal) en un solo archivo, con la misma carga y calificación que la ronda 2 (analisis_ronda2.cargar:
regla de «fotos», corte común y sin las 2 personas que entraron después de la edición v9). Solo agregados.
Condiciones: «formal» = prompt penal-original-v1 (condición «actual» en la base), «sencillo», «piloto» (fase piloto, sin
condición). Formación jurídica: grupo «estudiante» (enlace de estudiantes de Derecho) o perfil de Derecho (grupo_de).
Bootstrap por participante (4000 réplicas, IC 95 %).
    CORTE='2026-11-02 22:35:00' python resultados_ronda1.py > resultados_ronda1.json"""
import json, random, sys
from collections import Counter, defaultdict
sys.path.insert(0, '/tmp')
import analisis_ronda2 as A                       # noqa: E402
from study.analisis import grupo_de               # noqa: E402

rng = random.Random(1)
NOMBRE = {'actual': 'formal', 'sencillo': 'sencillo', None: 'piloto'}
CONDS = ('formal', 'sencillo', 'piloto')


def media(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


d, _ = A.cargar('piloto_penal')
part = {p['codigo']: p for p in d['participantes']}
cond = {c: NOMBRE.get(p.get('condicion'), p.get('condicion')) for c, p in part.items()}
form = {c: 'con' if grupo_de(p) in ('derecho', 'estudiante') else 'sin' for c, p in part.items()}
turnos = defaultdict(list)
for t in d['turnos']:
    turnos[t['intento_id']].append(t)

sit = []
for i in d['intentos']:
    if i['codigo'] not in part:
        continue
    sc = i.get('comprension') or {}
    ts = sorted(turnos[i['id']], key=lambda t: t['n'])
    t1 = ts[0] if ts else None
    ok = [t for t in ts if t.get('a')]
    fin = bool(i.get('fin'))
    sit.append({
        'persona': i['codigo'], 'cond': cond[i['codigo']], 'fo': form[i['codigo']], 'esc': i['escenario'],
        'comprension': sc['aciertos'] / sc['total'] if fin and sc.get('total') else None,
        'confianza_1a5': i.get('confianza') if fin else None,
        'actuaria': None if not (fin and i.get('actuaria')) else float(i['actuaria'] == 'si'),
        'noto_problema': None if not (fin and i.get('detecto')) else float(i['detecto'] == 'si'),
        '1a_otro_estado': None if not (t1 and t1.get('respuesta')) else float(A.otro_estado(t1['respuesta'], i['escenario'], i['variante'])),
        'alguna_otro_estado': None if not ok else float(any(A.otro_estado(t['respuesta'], i['escenario'], i['variante']) for t in ok)),
        '1a_cita_ley_correcta': None if not (t1 and t1.get('a')) or t1['a']['cita_ley_gold'] is None else float(t1['a']['cita_ley_gold']),
        '1a_cita_articulo_correcto': None if not (t1 and t1.get('a')) or t1['a']['cita_articulo_gold'] is None else float(t1['a']['cita_articulo_gold']),
        'recall10_1er_mensaje': None if not t1 else t1.get('r10'),
        'respuestas_que_piden_el_estado': media([float(t['a']['pide_lugar_estricto']) for t in ok]),
        'palabras_por_respuesta': media([t['a']['palabras'] for t in ok]),
        'mensajes_por_situacion': len(ts) if fin else None,
        # para «actuaría según el error»: situación terminada con alguna respuesta que nombra otro estado
        '_fin': fin, '_actuaria': i.get('actuaria'), '_detecto': i.get('detecto'),
    })
M = [k for k in sit[0] if not k.startswith('_') and k not in ('persona', 'cond', 'fo', 'esc')]


def personas(ss):
    g = defaultdict(list)
    for s in ss:
        g[s['persona']].append(s)
    return list(g.values())


def ic(f, ss):
    v = f(ss)
    if v is None:
        return None
    ps = personas(ss)
    bs = sorted(x for x in (f([s for p in (rng.choice(ps) for _ in ps) for s in p]) for _ in range(4000)) if x is not None)
    return [round(v, 3), round(bs[int(.025 * len(bs))], 3), round(bs[int(.975 * len(bs)) - 1], 3)]


def tabla(ss):
    """{métrica: [media, n situaciones]} + personas."""
    fila = {'personas': len({s['persona'] for s in ss})}
    for m in M:
        xs = [s[m] for s in ss if s[m] is not None]
        fila[m] = [round(media(xs), 3) if xs else None, len(xs)]
    return fila


out = {'fecha_datos': max(t['ts'] for t in d['turnos']),
       'excluidas': 'personas que entraron después de la edición v9 (2026-10-21 19:19:53 UTC)',
       'participantes': {
           'por_condicion': Counter(cond.values()),
           'por_condicion_y_formacion': Counter(f'{cond[c]} · {form[c]}' for c in part),
           'terminaron': sum(1 for p in part.values() if p.get('terminado_at')),
           'situaciones_terminadas': sum(1 for s in sit if s['_fin']),
           'mensajes': len(d['turnos'])}}
grupos = {'todos': lambda s: True, 'sin formación': lambda s: s['fo'] == 'sin', 'con formación': lambda s: s['fo'] == 'con'}
out['por_condicion'] = {g: {c: tabla([s for s in sit if f(s) and s['cond'] == c]) for c in CONDS} | {'todas': tabla([s for s in sit if f(s)])}
                        for g, f in grupos.items()}
out['por_situacion'] = {g: {e: tabla([s for s in sit if f(s) and s['esc'] == e]) for e in ('mensajes_trabajo', 'fotos', 'citatorio')}
                        for g, f in grupos.items()}

# Primeras respuestas que nombran el código penal de otro estado (métrica estricta del paper): [proporción, sí, total]
prim = [s['1a_otro_estado'] for s in sit if s['1a_otro_estado'] is not None]
out['1a_otro_estado_todas'] = [round(media(prim), 3), int(sum(prim)), len(prim)]
out['1a_otro_estado_ic95'] = {g: ic(lambda ss: media([s['1a_otro_estado'] for s in ss]), [s for s in sit if f(s)]) for g, f in grupos.items()}
out['con_menos_sin_formacion_ic95'] = {
    m: ic(lambda ss, m=m: None if media([s[m] for s in ss if s['fo'] == 'con']) is None or media([s[m] for s in ss if s['fo'] == 'sin']) is None
          else media([s[m] for s in ss if s['fo'] == 'con']) - media([s[m] for s in ss if s['fo'] == 'sin']), sit)
    for m in ('comprension', 'confianza_1a5', 'actuaria', 'noto_problema', '1a_otro_estado')}


# ¿Actuaría y notó un problema según si alguna respuesta de la situación nombró otro estado? (situaciones terminadas)
def tasa(ss, error, campo, valor):
    xs = [float(s[campo] == valor) for s in ss if s['_fin'] and s[campo] and s['alguna_otro_estado'] == error]
    return media(xs)


ae = {}
for g, f in grupos.items():
    ss = [s for s in sit if f(s)]
    fila = {'personas': len({s['persona'] for s in ss if s['_fin']}),
            'personas_con_alguna_situacion_con_error': len({s['persona'] for s in ss if s['_fin'] and s['alguna_otro_estado'] == 1.0}),
            'situaciones_con_error': sum(1 for s in ss if s['_fin'] and s['alguna_otro_estado'] == 1.0),
            'situaciones_sin_error': sum(1 for s in ss if s['_fin'] and s['alguna_otro_estado'] == 0.0)}
    for etiqueta, campo, valor in (('actuaria_si', '_actuaria', 'si'), ('actuaria_no', '_actuaria', 'no'), ('actuaria_no_se', '_actuaria', 'no_se'),
                                   ('noto_problema_si', '_detecto', 'si'), ('noto_problema_no_se', '_detecto', 'no_se')):
        con, sin = tasa(ss, 1.0, campo, valor), tasa(ss, 0.0, campo, valor)
        fila[etiqueta] = {'con_error': None if con is None else round(con, 3), 'sin_error': None if sin is None else round(sin, 3),
                          'con_menos_sin_ic95': ic(lambda x, c=campo, v=valor: None if tasa(x, 1.0, c, v) is None or tasa(x, 0.0, c, v) is None
                                                   else tasa(x, 1.0, c, v) - tasa(x, 0.0, c, v), ss)}
    ae[g] = fila
out['actuaria_segun_error_de_estado'] = ae
print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
