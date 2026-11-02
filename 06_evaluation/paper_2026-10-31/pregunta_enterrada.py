"""¿Por qué solo 4 de cada 10 dan el estado cuando el asistente lo pide? Ronda 2, situaciones cuyo 1er mensaje no nombra
el estado y cuya 1a respuesta lo pide. Separa dos pasos: (a) ¿la persona mandó otro mensaje? (b) si lo mandó, ¿dio el
estado? Y los relaciona con la respuesta: palabras, dónde queda la pregunta del estado (posición relativa y palabras
después de ella), si va en negritas o en su propio párrafo, cuántas preguntas hace, si ya citaba la ley correcta.
Bootstrap por participante (4000 réplicas, IC 95 %). Solo agregados.
    python pregunta_enterrada.py > pregunta_enterrada.json"""
import json, random, re, statistics as st, sys
from collections import Counter, defaultdict
sys.path.insert(0, '/tmp')
import analisis_ronda2 as A                       # noqa: E402
from study.analisis import grupo_de, _PIDE_ESTRICTO, _PIDE_DIRECTO, _sin_acentos, fold   # noqa: E402

rng = random.Random(1)
EST = re.compile(r'(?i)quer[eé]taro|ciudad de m[eé]xico|cdmx|\bdf\b|morelos|estado de m[eé]xico')


def media(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def donde_pide(resp):
    """Posición (0–1) y palabras después de la primera petición del estado; si va en negritas / en su propio párrafo."""
    sa = _sin_acentos(resp)            # misma longitud que resp salvo acentos combinados: se mide sobre sa
    m = _PIDE_ESTRICTO.search(sa) or _PIDE_DIRECTO.search(fold(resp))
    if not m:
        return None
    base = sa if _PIDE_ESTRICTO.search(sa) else fold(resp)
    i = m.start()
    ini = base.rfind('\n', 0, i) + 1
    fin = base.find('\n', m.end()); fin = len(base) if fin < 0 else fin
    linea = base[ini:fin]
    return {'posicion': i / max(len(base), 1), 'palabras_despues': len(base[m.end():].split()),
            'negritas': float('**' in linea), 'parrafo_propio': float(len(linea.split()) <= 45),
            'preguntas_en_respuesta': resp.count('¿')}


d, _ = A.cargar('ronda2_penal')
part = {p['codigo']: p for p in d['participantes']}
turnos = defaultdict(list)
for t in d['turnos']:
    turnos[t['intento_id']].append(t)
filas = []
for i in d['intentos']:
    p = part.get(i['codigo'])
    ts = sorted(turnos[i['id']], key=lambda t: t['n'])
    if not p or not ts or not i.get('fin') or EST.search(ts[0]['pregunta'] or ''):
        continue
    t1 = ts[0]
    if not (t1.get('a') and t1['a']['pide_lugar_estricto'] and t1.get('respuesta')):
        continue
    w = donde_pide(t1['respuesta'])
    if not w:
        continue
    otro = len(ts) > 1
    filas.append({'persona': i['codigo'], 'prompt': p['condicion'], 'fo': 'con' if grupo_de(p) in ('derecho', 'estudiante') else 'sin',
                  'palabras': t1['a']['palabras'], 'ya_cita_ley': float(bool(t1['a']['cita_ley_gold'])), **w,
                  'mando_otro': float(otro), 'dio_estado': float(any(EST.search(t['pregunta'] or '') for t in ts[1:])),
                  'dio_estado_si_mando_otro': float(any(EST.search(t['pregunta'] or '') for t in ts[1:])) if otro else None,
                  'mensajes': len(ts)})


def boot(a, b, m):
    pa, pb = defaultdict(list), defaultdict(list)
    for f in a:
        pa[f['persona']].append(f)
    for f in b:
        pb[f['persona']].append(f)
    A_, B_ = list(pa.values()), list(pb.values())
    mu = lambda ps: media([f[m] for p in ps for f in p])
    if not A_ or not B_ or mu(A_) is None or mu(B_) is None:
        return None
    bs = sorted((mu([rng.choice(B_) for _ in B_]) or 0) - (mu([rng.choice(A_) for _ in A_]) or 0) for _ in range(4000))
    return [round(mu(B_) - mu(A_), 3), round(bs[100], 3), round(bs[3899], 3)]


R = ('mando_otro', 'dio_estado', 'dio_estado_si_mando_otro')
def resumen(fs):
    return {'situaciones': len(fs), 'personas': len({f['persona'] for f in fs}),
            **{m: [round(media([f[m] for f in fs]), 3) if media([f[m] for f in fs]) is not None else None,
                   sum(1 for f in fs if f[m] is not None)] for m in R}}


out = {'todas': resumen(filas), 'sin formación': resumen([f for f in filas if f['fo'] == 'sin']),
       'con formación': resumen([f for f in filas if f['fo'] == 'con'])}
out['rasgos_de_la_respuesta'] = {k: {'mediana': round(st.median([f[k] for f in filas]), 3), 'media': round(st.mean([f[k] for f in filas]), 3)}
                                 for k in ('palabras', 'posicion', 'palabras_despues', 'negritas', 'parrafo_propio', 'preguntas_en_respuesta', 'ya_cita_ley')}
# Cortes: mitad baja vs mitad alta (mediana) de cada rasgo continuo; sí/no para los binarios.
cortes = {}
for k in ('palabras', 'posicion', 'palabras_despues', 'preguntas_en_respuesta'):
    med = st.median([f[k] for f in filas])
    bajo, alto = [f for f in filas if f[k] <= med], [f for f in filas if f[k] > med]
    cortes[f'{k} (≤ {round(med, 2)} vs > {round(med, 2)})'] = {'bajo': resumen(bajo), 'alto': resumen(alto),
                                                               'alto − bajo': {m: boot(bajo, alto, m) for m in R}}
for k in ('negritas', 'parrafo_propio', 'ya_cita_ley'):
    no, si = [f for f in filas if f[k] == 0], [f for f in filas if f[k] == 1]
    cortes[k] = {'no': resumen(no), 'sí': resumen(si), 'sí − no': {m: boot(no, si, m) for m in R}}
out['cortes'] = cortes
out['por_prompt'] = {c: {**resumen([f for f in filas if f['prompt'] == c]),
                         'palabras_mediana': st.median([f['palabras'] for f in filas if f['prompt'] == c]),
                         'posicion_mediana': round(st.median([f['posicion'] for f in filas if f['prompt'] == c]), 2)}
                     for c in ('original', 'nuevo', 'intermedio')}
print(json.dumps(out, ensure_ascii=False, indent=1))
