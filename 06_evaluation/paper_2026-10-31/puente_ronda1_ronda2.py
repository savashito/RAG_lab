"""Puente entre la ronda 1 (piloto_penal) y la ronda 2 (ronda2_penal): el prompt formal legal (penal-original-v1, md5
f68239bf) se usó en las dos. Lo que cambia entre rondas es el sistema (filtro por estado, rerank, 9 documentos
apagados) y las personas. Compara por situación, con bootstrap por participante (4000 réplicas, IC 95 %), en total y
por formación jurídica. Solo agregados.
    python puente_ronda1_ronda2.py > puente.json"""
import json, random, statistics as st, sys
from collections import Counter, defaultdict
sys.path.insert(0, '/tmp')
import analisis_ronda2 as A                       # noqa: E402  (carga main y las métricas)
from study.analisis import grupo_de               # noqa: E402

rng = random.Random(1)


def media(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def situaciones(eid):
    d, _ = A.cargar(eid)
    part = {p['codigo']: p for p in d['participantes']}
    turnos = defaultdict(list)
    for t in d['turnos']:
        turnos[t['intento_id']].append(t)
    filas = []
    for i in d['intentos']:
        p = part.get(i['codigo'])
        if not p:
            continue
        sc = i.get('comprension') or {}
        ts = sorted(turnos[i['id']], key=lambda t: t['n'])
        t1 = ts[0] if ts else None
        ok = [t for t in ts if t.get('a')]
        filas.append({
            'persona': i['codigo'], 'condicion': p['condicion'] or 'piloto',
            # Misma regla que la ronda 1: el enlace de estudiantes de Derecho (grupo «estudiante») cuenta como con
            # formación jurídica; los códigos «general» se clasifican por perfil (grupo_de).
            'formacion': 'con' if grupo_de(p) in ('derecho', 'estudiante') else 'sin',
            'md5': (t1 or {}).get('sistema_md5'),
            'comprension': sc['aciertos'] / sc['total'] if sc.get('total') else None,
            'confianza_1a5': i.get('confianza'),
            'actuaria': None if not i.get('actuaria') else float(i['actuaria'] == 'si'),
            'noto_problema': None if not i.get('detecto') else float(i['detecto'] == 'si'),
            '1a_otro_estado': None if not (t1 and t1.get('respuesta')) else float(A.otro_estado(t1['respuesta'], i['escenario'], i['variante'])),
            '1a_cita_ley_correcta': None if not (t1 and t1.get('a')) or t1['a']['cita_ley_gold'] is None else float(t1['a']['cita_ley_gold']),
            '1a_cita_articulo_correcto': None if not (t1 and t1.get('a')) or t1['a']['cita_articulo_gold'] is None else float(t1['a']['cita_articulo_gold']),
            'respuestas_que_piden_el_estado': media([float(t['a']['pide_lugar_estricto']) for t in ok]),
            'recall10_1er_mensaje': None if not t1 else t1.get('r10'),
        })
    return filas


M = ['comprension', 'confianza_1a5', 'actuaria', 'noto_problema', '1a_otro_estado', '1a_cita_ley_correcta',
     '1a_cita_articulo_correcto', 'respuestas_que_piden_el_estado', 'recall10_1er_mensaje']


def resumen(filas):
    personas = defaultdict(list)
    for f in filas:
        personas[f['persona']].append(f)
    out = {'personas': len(personas)}
    for m in M:
        xs = [f[m] for f in filas if f[m] is not None]
        out[m] = (round(media(xs), 3) if xs else None, len(xs))
    return out, personas


def dif(fa, fb, m):
    _, pa = resumen(fa); _, pb = resumen(fb)
    A_, B_ = list(pa.values()), list(pb.values())
    mu = lambda ps: media([f[m] for p in ps for f in p])
    if not A_ or not B_ or mu(A_) is None or mu(B_) is None:
        return None
    bs = sorted(x for x in ((mu([rng.choice(B_) for _ in B_]) or 0) - (mu([rng.choice(A_) for _ in A_]) or 0) for _ in range(4000)))
    return [round(mu(B_) - mu(A_), 3), round(bs[100], 3), round(bs[3899], 3)]


r1, r2 = situaciones('piloto_penal'), situaciones('ronda2_penal')
out = {'md5_ronda1_actual': Counter(f['md5'][:8] for f in r1 if f['condicion'] == 'actual' and f['md5']),
       'md5_ronda2_original': Counter(f['md5'][:8] for f in r2 if f['condicion'] == 'original' and f['md5'])}
grupos = {'ronda1 formal (actual)': [f for f in r1 if f['condicion'] == 'actual'],
          'ronda1 sencillo': [f for f in r1 if f['condicion'] == 'sencillo'],
          'ronda1 piloto': [f for f in r1 if f['condicion'] == 'piloto'],
          'ronda2 formal (original)': [f for f in r2 if f['condicion'] == 'original'],
          'ronda2 nuevo': [f for f in r2 if f['condicion'] == 'nuevo'],
          'ronda2 intermedio': [f for f in r2 if f['condicion'] == 'intermedio']}
for fo in ('todos', 'sin', 'con'):
    sel = {k: [f for f in v if fo == 'todos' or f['formacion'] == fo] for k, v in grupos.items()}
    out[f'tabla_{fo}'] = {k: resumen(v)[0] for k, v in sel.items()}
    out[f'puente_formal_r2_menos_r1_{fo}'] = {m: dif(sel['ronda1 formal (actual)'], sel['ronda2 formal (original)'], m) for m in M}
print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
