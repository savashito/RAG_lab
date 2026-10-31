"""Ronda 2 (ronda2_penal) por prompt, para el paper preliminar del 31-oct. Solo agregados: no imprime textos ni códigos.

Unidad de remuestreo = participante (bootstrap por persona, 4000 réplicas, IC 95 %). Las métricas de respuesta usan
study.analisis.analizar_respuesta, la misma que la página (otro_codigo_estatal = nombra el CÓDIGO PENAL de un estado
que no es el de la situación). También repite la ronda 1 (piloto_penal) con esa métrica, para la comparación.
    python analisis_ronda2.py > resultados_ronda2.json"""
import json, math, random, re, statistics as st, sys
from collections import Counter, defaultdict
from pathlib import Path
RAIZ = Path('/home/tlacua/apps/RAG_lab')
sys.path[:0] = [str(RAIZ / 'apps' / 'rewrite_lab'), str(RAIZ)]
import os; os.chdir(RAIZ / 'apps' / 'rewrite_lab')
import main                                                                    # noqa: E402
from study.validar import escenario_efectivo                                   # noqa: E402
from study.analisis import analizar_respuesta, grupo_de, rango_gold, recall_at  # noqa: E402

# Métrica corregida (31-oct): la de la página toma como «permitidos» los códigos de las leyes gold; en «fotos» el gold es
# la Ley General de Extorsión, así que nombrar el Código Penal de Querétaro (el estado de Cris) contaba como otro estado.
# Aquí el permitido es el estado donde ocurren los hechos. Mismas expresiones que metrica_estricta.py (24-oct).
E = r'(?:del?\s+|para\s+(?:el\s+)?)?(?:la\s+|el\s+)?'
CODIGO = {
    'CDMX': re.compile(rf'(?i)c[oó]digo\s+penal\s+{E}(?:distrito\s+federal|ciudad\s+de\s+m[eé]xico)|\bcpcdmx\b|\bcpdf\b|\bcp\s?cdmx\b'),
    'CPEM': re.compile(rf'(?i)c[oó]digo\s+penal\s+{E}(?:estado\s+de\s+m[eé]xico)|\bcpem\b'),
    'Querétaro': re.compile(rf'(?i)c[oó]digo\s+penal\s+{E}(?:estado\s+de\s+)?quer[eé]taro'),
    'Morelos': re.compile(rf'(?i)c[oó]digo\s+penal\s+{E}(?:estado\s+(?:libre\s+y\s+soberano\s+)?de\s+)?morelos'),
}
FOCAL = {('mensajes_trabajo', 'qro'): 'Querétaro', ('mensajes_trabajo', 'cdmx'): 'CDMX', ('fotos', None): 'Querétaro',
         ('citatorio', None): 'Querétaro'}


def otro_estado(resp, esc, var):
    foc = FOCAL.get((esc, var))
    return any(rx.search(resp or '') for lab, rx in CODIGO.items() if lab != foc)


MUJERES = re.compile(r'(?i)acceso\s+de\s+las\s+mujeres\s+a\s+una\s+vida\s+libre|\blgamvlv\b')


def cargar(eid):
    d = main.study_store.export(eid); spec = main.study_store.spec(eid)
    por_id = {e['id']: e for e in spec['escenarios']}
    gold = {}
    for i in d['intentos']:
        k = (i['escenario'], i['variante'])
        if k not in gold and i['escenario'] in por_id:
            ef = escenario_efectivo(por_id[i['escenario']], i['variante'])
            gold[k] = main._study_resolver([g for x in ef.get('gold') or [] for g in main._study_gold_refs(x)])
    esc = {i['id']: (i['escenario'], i['variante']) for i in d['intentos']}
    for t in d['turnos']:
        g = gold.get(esc.get(t['intento_id'])) or []
        t['a'] = analizar_respuesta(t['respuesta'] or '', g) if t.get('respuesta') else None
        t['r10'] = recall_at(rango_gold(g, t.get('ranking') or []), 10) if g else None
    return d, spec


def sus(c):
    r = (c or {}).get('sus') or []
    if len(r) != 10 or not all(isinstance(x, int) for x in r):
        return None
    return 2.5 * sum((x - 1) if k % 2 == 0 else (5 - x) for k, x in enumerate(r))


def media(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def main_():
    rng = random.Random(1)
    out = {}
    d, spec = cargar('ronda2_penal')
    part = {p['codigo']: p for p in d['participantes']}
    cond = {c: (p['condicion'] or '?') for c, p in part.items()}
    form = {c: ('con formación jurídica' if grupo_de(p) == 'derecho' else 'sin formación jurídica') for c, p in part.items()}
    ints = defaultdict(list)
    for i in d['intentos']:
        ints[i['codigo']].append(i)
    turnos = defaultdict(list)
    for t in d['turnos']:
        turnos[t['intento_id']].append(t)

    # Valores por situación (intento) → la persona es la unidad de remuestreo.
    def valores(i):
        r = i.get('respuestas') or {}; sc = i.get('comprension') or {}
        ts = sorted(turnos[i['id']], key=lambda t: t['n'])
        t1 = ts[0] if ts else None
        ok = [t for t in ts if t.get('a')]
        v = {
            'comprension': sc['aciertos'] / sc['total'] if sc.get('total') else None,
            'confianza_1a5': i.get('confianza'),
            'confianza_alta_4o5': None if not i.get('confianza') else float(i['confianza'] >= 4),
            'actuaria': None if not i.get('actuaria') else float(i['actuaria'] == 'si'),
            'noto_problema': None if not i.get('detecto') else float(i['detecto'] == 'si'),
            'escala_confianza_asistente': r.get('escala_confianza_asistente') if isinstance(r.get('escala_confianza_asistente'), int) else None,
            'escala_correcta_percibida': r.get('escala_correcta_percibida') if isinstance(r.get('escala_correcta_percibida'), int) else None,
            'mensajes_por_situacion': len(ts) if i.get('fin') else None,
            'minutos_por_situacion': (i['segundos'] / 60) if i.get('fin') and i.get('segundos') else None,
            '1a_cita_ley_correcta': None if not (t1 and t1.get('a')) else t1['a']['cita_ley_gold'],
            '1a_cita_articulo_correcto': None if not (t1 and t1.get('a')) else t1['a']['cita_articulo_gold'],
            '1a_nombra_codigo_de_otro_estado': None if not (t1 and t1.get('a')) or t1['a']['otro_codigo_estatal'] is None else bool(t1['a']['otro_codigo_estatal']),
            'cualquier_respuesta_nombra_codigo_de_otro_estado': None if not ok else any(t['a']['otro_codigo_estatal'] for t in ok),
            '1a_otro_estado_corregida': None if not (t1 and t1.get('respuesta')) else otro_estado(t1['respuesta'], i['escenario'], i['variante']),
            'alguna_otro_estado_corregida': None if not ok else any(otro_estado(t['respuesta'], i['escenario'], i['variante']) for t in ok),
            'respuestas_que_piden_el_estado': media([float(t['a']['pide_lugar_estricto']) for t in ok]),
            'palabras_por_respuesta': media([t['a']['palabras'] for t in ok]),
            'recall10_1er_mensaje': None if not t1 else t1.get('r10'),
            'fotos_cita_ley_mujeres': None if i['escenario'] != 'fotos' or not ok else any(MUJERES.search(t['respuesta'] or '') for t in ok),
        }
        return {k: (float(x) if isinstance(x, bool) else x) for k, x in v.items()}

    sit = {i['id']: valores(i) for i in d['intentos']}
    metricas = list(next(iter(sit.values())).keys())

    def tabla(filtro_persona, filtro_sit=lambda i: True):
        """{cond: {metrica: (media, n_situaciones)}} + personas."""
        res = {}
        for c in ('original', 'nuevo', 'intermedio'):
            ps = [p for p in ints if cond.get(p) == c and filtro_persona(p)]
            fila = {'personas': len(ps)}
            for m in metricas:
                xs = [sit[i['id']][m] for p in ps for i in ints[p] if filtro_sit(i) and sit[i['id']][m] is not None]
                fila[m] = (round(media(xs), 3) if xs else None, len(xs))
            res[c] = fila
        return res

    def dif(m, a, b, filtro_persona=lambda p: True, filtro_sit=lambda i: True):
        A = [p for p in ints if cond.get(p) == a and filtro_persona(p)]
        B = [p for p in ints if cond.get(p) == b and filtro_persona(p)]
        def mu(ps):
            return media([sit[i['id']][m] for p in ps for i in ints[p] if filtro_sit(i)])
        obs = (mu(B) or 0) - (mu(A) or 0)
        bs = []
        for _ in range(4000):
            x, y = mu([rng.choice(B) for _ in B]), mu([rng.choice(A) for _ in A])
            if x is not None and y is not None:
                bs.append(x - y)
        bs.sort()
        return [round(obs, 3), round(bs[int(.025 * len(bs))], 3), round(bs[int(.975 * len(bs)) - 1], 3)]

    todos = lambda p: True
    out['fecha_datos'] = max(t['ts'] for t in d['turnos'])
    out['participantes'] = {
        'por_prompt': Counter(cond.values()),
        'terminaron_por_prompt': Counter(cond[c] for c, p in part.items() if p.get('terminado_at')),
        'por_prompt_y_formacion': Counter(f'{cond[c]} · {form[c]}' for c in part),
        'perfil_estudios': Counter((p.get('perfil') or {}).get('estudios') for p in part.values()),
        'perfil_area': Counter((p.get('perfil') or {}).get('area') for p in part.values()),
        'perfil_formacion': Counter((p.get('perfil') or {}).get('formacion_juridica') for p in part.values()),
        'perfil_uso_ia': Counter((p.get('perfil') or {}).get('uso_ia') for p in part.values()),
        'perfil_edad': Counter((p.get('perfil') or {}).get('edad') for p in part.values()),
        'origen': Counter((p.get('origen') or 'sin nota') for p in part.values()),
        'situaciones_terminadas': sum(1 for i in d['intentos'] if i.get('fin')),
        'mensajes': len(d['turnos']), 'mensajes_con_error': sum(1 for t in d['turnos'] if t.get('error')),
        'segundos_por_respuesta_media': round(st.mean(t['segundos'] for t in d['turnos'] if t.get('segundos') and not t.get('error')), 1),
        'segundos_por_respuesta_p90': round(sorted(t['segundos'] for t in d['turnos'] if t.get('segundos') and not t.get('error'))[int(.9 * sum(1 for t in d['turnos'] if t.get('segundos') and not t.get('error')))], 1),
    }
    out['por_prompt'] = tabla(todos)
    out['por_prompt_sin_formacion'] = tabla(lambda p: form[p] == 'sin formación jurídica')
    out['por_prompt_con_formacion'] = tabla(lambda p: form[p] == 'con formación jurídica')
    out['por_prompt_y_situacion'] = {e: tabla(todos, lambda i, e=e: i['escenario'] == e) for e in ('mensajes_trabajo', 'fotos', 'citatorio')}
    out['minutos_por_situacion_mediana'] = {c: round(st.median([sit[i['id']]['minutos_por_situacion'] for p in ints if cond[p] == c
                                                                for i in ints[p] if sit[i['id']]['minutos_por_situacion']]), 1)
                                             for c in ('original', 'nuevo', 'intermedio')}
    clave = ['1a_otro_estado_corregida', 'alguna_otro_estado_corregida', 'comprension', 'escala_confianza_asistente', 'escala_correcta_percibida', 'confianza_1a5', 'actuaria',
             'noto_problema', '1a_cita_ley_correcta', '1a_cita_articulo_correcto', '1a_nombra_codigo_de_otro_estado',
             'respuestas_que_piden_el_estado', 'palabras_por_respuesta', 'fotos_cita_ley_mujeres']
    pares = (('original', 'nuevo'), ('original', 'intermedio'), ('nuevo', 'intermedio'))
    out['diferencias_ic95'] = {m: {f'{b} − {a}': dif(m, a, b) for a, b in pares} for m in clave}
    out['diferencias_ic95_sin_formacion'] = {m: {f'{b} − {a}': dif(m, a, b, lambda p: form[p] == 'sin formación jurídica') for a, b in pares}
                                             for m in ('comprension', 'escala_confianza_asistente', 'actuaria', 'noto_problema')}
    # Confianza vs comprensión: ¿la confianza alta acompaña a la comprensión? (por situación)
    cc = defaultdict(lambda: defaultdict(list))
    for p in ints:
        for i in ints[p]:
            v = sit[i['id']]
            if v['comprension'] is not None and v['escala_confianza_asistente'] is not None:
                cc[cond[p]]['alta' if v['escala_confianza_asistente'] >= 4 else 'baja'].append(v['comprension'])
    out['comprension_segun_escala_confianza'] = {c: {k: (round(media(x), 3), len(x)) for k, x in m.items()} for c, m in cc.items()}
    out['sus_por_prompt'] = {c: (round(media([sus(part[p].get('cierre')) for p in part if cond[p] == c]) or 0, 1),
                                 sum(1 for p in part if cond[p] == c and sus(part[p].get('cierre')) is not None))
                             for c in ('original', 'nuevo', 'intermedio')}
    ec = defaultdict(Counter)
    for p in ints:
        for i in ints[p]:
            r = (i.get('respuestas') or {}).get('estado_citado')
            if r:
                ec[cond[p]][r] += 1
    out['ultima_situacion_estado_citado'] = {c: dict(v) for c, v in ec.items()}
    out['md5_prompts_usados'] = Counter(f"{cond.get(next((i['codigo'] for i in d['intentos'] if i['id'] == t['intento_id']), ''), '?')} {str(t.get('sistema_md5'))[:8]}" for t in d['turnos'])

    # Tamaño de muestra: DE entre personas de la media por persona.
    def de_persona(m):
        xs = [media([sit[i['id']][m] for i in ints[p]]) for p in ints]
        xs = [x for x in xs if x is not None]
        return st.stdev(xs) if len(xs) > 2 else None
    z = {'a2': 1.959964, 'b80': 0.841621, 'a1_05': 1.644854, 'b80_2': 1.281552}
    tam = {}
    for m, delta in (('comprension', 0.10), ('comprension', 0.15), ('escala_confianza_asistente', 0.5), ('noto_problema', 0.10), ('actuaria', 0.15)):
        s = de_persona(m)
        if s:
            tam[f'{m} · diferencia {delta}'] = {'de_por_persona': round(s, 3),
                                                'personas_por_prompt_detectar_80pct': math.ceil(2 * (z['a2'] + z['b80']) ** 2 * s * s / delta ** 2)}
    s = de_persona('comprension')
    tam['comprension · equivalencia ±0.10 (TOST, 80 %, diferencia real 0)'] = {
        'de_por_persona': round(s, 3), 'personas_por_prompt': math.ceil(2 * (z['a1_05'] + z['b80_2']) ** 2 * s * s / 0.10 ** 2)}
    out['tamano_de_muestra'] = tam

    # Ronda 1 con la misma métrica (primer mensaje), por condición y total sin piloto.
    d1, _ = cargar('piloto_penal')
    c1 = {p['codigo']: (p['condicion'] or 'piloto') for p in d1['participantes']}
    it1 = {i['id']: i for i in d1['intentos']}
    r1, r1c, r1e = defaultdict(list), defaultdict(list), defaultdict(list)
    for t in d1['turnos']:
        if t['n'] == 1 and t.get('a') and t['a']['otro_codigo_estatal'] is not None:
            i1 = it1[t['intento_id']]
            r1[c1.get(i1['codigo'], '?')].append(bool(t['a']['otro_codigo_estatal']))
            r1c[c1.get(i1['codigo'], '?')].append(otro_estado(t['respuesta'], i1['escenario'], i1['variante']))
            r1e[i1['escenario']].append(otro_estado(t['respuesta'], i1['escenario'], i1['variante']))
    out['ronda1_1a_otro_estado_corregida'] = {c: (round(st.mean(v), 3), sum(v), len(v)) for c, v in sorted(r1c.items())}
    tc = [x for v in r1c.values() for x in v]
    out['ronda1_1a_otro_estado_corregida']['todas'] = (round(st.mean(tc), 3), sum(tc), len(tc))
    out['ronda1_1a_otro_estado_corregida_por_situacion'] = {e: (round(st.mean(v), 3), sum(v), len(v)) for e, v in sorted(r1e.items())}
    out['ronda1_1a_nombra_codigo_de_otro_estado'] = {c: (round(st.mean(v), 3), sum(v), len(v)) for c, v in sorted(r1.items())}
    tot = [x for c, v in r1.items() for x in v]
    out['ronda1_1a_nombra_codigo_de_otro_estado']['todas'] = (round(st.mean(tot), 3), sum(tot), len(tot))
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str))


main_()
