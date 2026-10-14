# Solo lectura: TODOS los números de la ronda 1 del estudio (piloto + fase principal), sin las 3 pruebas del 8-oct.
# Salida: /tmp/ronda1.json (agregados + citas) para escribir el documento de hallazgos.
import sys, json, re, statistics as st
from collections import Counter, defaultdict
sys.path[:0] = ['apps/rewrite_lab', '.']
from dotenv import load_dotenv; load_dotenv('apps/rewrite_lab/.env')
from pathlib import Path
from shared.db import connect
from shared.code_routes import codes_in, fold, short_label
from bench import gold_refs, resolve_gold
from study.store import StudyStore
from study.validar import escenario_efectivo
from study.analisis import analizar_respuesta, lugares_mencionados, rango_gold, recall_at, sus, grupo_de, LUGARES
PRUEBAS = {'NGSX-GGPH', 'K9TQ-6P86', 'FYJ2-VS7R'}
E = 'piloto_penal'
s = StudyStore(connect, Path('/nonexistent'))
d = s.export(E); spec = s.spec(E)
P = {p['codigo']: p for p in d['participantes'] if p['codigo'] not in PRUEBAS}
I = {i['id']: i for i in d['intentos'] if i['codigo'] in P}
T = [t for t in d['turnos'] if t['intento_id'] in I]
por_id = {e['id']: e for e in spec['escenarios']}
gold = {}
with connect() as c, c.cursor() as cur:
    for i in I.values():
        k = (i['escenario'], i['variante'])
        if k not in gold:
            ef = escenario_efectivo(por_id[i['escenario']], i['variante'])
            gold[k] = resolve_gold(cur, 'sistema_penal__qwen06__legal', [g for t in ef.get('gold') or [] for g in gold_refs('', [{'kind': 'must', 'text': t}])])
    cur.execute("select id, source from sistema_penal__qwen06__legal where id = any(%s)", (list({x['id'] for t in T for x in (t['contexto'] or []) if x.get('id')}),))
    src_de = dict(cur.fetchall())
def cond(cod):
    p = P[cod]; return 'original_piloto' if p.get('fase') == 'piloto' else ('original' if p.get('condicion') == 'actual' else 'sencillo')
def esc_key(i): return i['escenario'] + (f"/{i['variante']}" if i['variante'] else '')
ESTADO_ESC = {'mensajes_trabajo/qro': 'Querétaro', 'mensajes_trabajo/cdmx': 'CDMX', 'fotos': 'Querétaro', 'citatorio': 'Querétaro'}
NAC = {'CPF', 'CNPP', 'LGExtorsión', 'LGSecuestro', 'LGV', 'LFCDO'}
for t in T:
    i = I[t['intento_id']]
    g = gold.get((i['escenario'], i['variante'])) or []
    t['rangos'] = rango_gold(g, t.get('ranking') or [])
    t['an'] = analizar_respuesta(t.get('respuesta') or '', g) if t.get('respuesta') else None
    t['lugar'] = lugares_mencionados(t['pregunta'])
    # estados en el CONTEXTO (lo que vio el modelo) vs estados citados en la RESPUESTA
    ctx_estados = set()
    for x in t['contexto'] or []:
        lab = short_label(src_de.get(x.get('id')) or x.get('source') or '')
        if lab in LUGARES: ctx_estados.add(lab)
    t['ctx_estados'] = sorted(ctx_estados)
    t['resp_estados'] = sorted({h['label'] for h in codes_in(t.get('respuesta') or '') if h['label'] in LUGARES})
out = {}
# ── participantes
part = []
for cod, p in P.items():
    ints = [i for i in I.values() if i['codigo'] == cod]
    part.append(dict(cod=cod, grupo=cond(cod), origen=p.get('origen'), area=(p['perfil'] or {}).get('area'), formacion=(p['perfil'] or {}).get('formacion_juridica'),
                     uso_ia=(p['perfil'] or {}).get('uso_ia'), confianza_basal=(p['perfil'] or {}).get('confianza_basal'), semestre=(p['perfil'] or {}).get('semestre'),
                     termino=bool(p['terminado_at']), situaciones=sum(1 for i in ints if i['fin']), sus=sus(((p.get('cierre') or {}).get('sus')) or [])))
out['n'] = {g: dict(personas=sum(1 for x in part if x['grupo'] == g), terminaron=sum(1 for x in part if x['grupo'] == g and x['termino']),
                    situaciones=sum(x['situaciones'] for x in part if x['grupo'] == g)) for g in ('original_piloto', 'original', 'sencillo')}
out['demografia'] = {k: dict(Counter(x[k] for x in part)) for k in ('area', 'formacion', 'uso_ia', 'semestre', 'confianza_basal', 'origen')}
fechas = sorted(P[c]['consentimiento_at'] for c in P); out['fechas'] = [fechas[0], fechas[-1]]
med = lambda xs: round(st.median(xs), 2) if xs else None
mean = lambda xs: round(st.mean(xs), 3) if xs else None
# ── por grupo (condición)
G = {}
for g in ('original_piloto', 'original', 'sencillo'):
    ints = [i for i in I.values() if cond(i['codigo']) == g and i['fin']]
    ts = [t for t in T if cond(I[t['intento_id']]['codigo']) == g and t.get('respuesta')]
    t1 = [t for t in ts if t['n'] == 1]
    sc = [i['comprension']['aciertos'] / i['comprension']['total'] for i in ints if (i.get('comprension') or {}).get('total')]
    alta = [i['comprension']['aciertos'] / i['comprension']['total'] for i in ints if (i.get('comprension') or {}).get('total') and (i['confianza'] or 0) >= 4]
    baja = [i['comprension']['aciertos'] / i['comprension']['total'] for i in ints if (i.get('comprension') or {}).get('total') and (i['confianza'] or 0) <= 3]
    susv = [x['sus'] for x in part if x['grupo'] == g and x['sus'] is not None]
    items = [((P[x['cod']].get('cierre') or {}).get('sus')) for x in part if x['grupo'] == g and ((P[x['cod']].get('cierre') or {}).get('sus'))]
    G[g] = dict(
        comprension=mean(sc), comprension_conf_alta=mean(alta), n_conf_alta=len(alta), comprension_conf_baja=mean(baja), n_conf_baja=len(baja),
        confianza=mean([i['confianza'] for i in ints if i['confianza']]), actuaria=mean([i['actuaria'] == 'si' for i in ints if i['actuaria']]),
        noto_problema=mean([i['detecto'] == 'si' for i in ints if i['detecto']]),
        eligio_otra=mean([any(v == 'otra' for k, v in (i['respuestas'] or {}).items() if not k.startswith('_')) for i in ints]),
        sus=mean(susv), sus_items=[round(st.mean(x[j] for x in items), 2) for j in range(10)] if items else None,
        min_por_situacion=med([float(i['segundos']) / 60 for i in ints if i.get('segundos')]), turnos_por_situacion=round(len(ts) / max(len(ints), 1), 2),
        palabras=mean([t['an']['palabras'] for t in ts]), espera_s=med([t['segundos'] for t in ts if t.get('segundos')]),
        pide_lugar=mean([t['an']['pide_lugar'] for t in ts]),
        t1_cita_ley_gold=mean([t['an']['cita_ley_gold'] for t in t1 if t['an']['cita_ley_gold'] is not None]),
        t1_cita_art_gold=mean([t['an']['cita_articulo_gold'] for t in t1 if t['an']['cita_articulo_gold'] is not None]),
        t1_empieza_otro_estado=mean([t['an']['primera_ley_es_otra'] for t in t1 if t['an']['primera_ley_es_otra'] is not None]),
        resp_con_otro_estado=mean([bool(set(t['resp_estados']) - {ESTADO_ESC[esc_key(I[t['intento_id']])]}) for t in ts]),
        t1_r10=mean([recall_at(t['rangos'], 10) for t in t1 if t['rangos']]),
    )
out['por_grupo'] = G
# ── por situación (todos los grupos)
S = {}
for k in sorted({esc_key(i) for i in I.values()}):
    ints = [i for i in I.values() if esc_key(i) == k and i['fin']]
    t1 = [t for t in T if esc_key(I[t['intento_id']]) == k and t['n'] == 1 and t.get('respuesta')]
    con = [t for t in t1 if t['lugar']]; sin = [t for t in t1 if not t['lugar']]
    ts = [t for t in T if esc_key(I[t['intento_id']]) == k and t.get('respuesta')]
    S[k] = dict(intentos=len(ints), comprension=mean([i['comprension']['aciertos'] / i['comprension']['total'] for i in ints if (i.get('comprension') or {}).get('total')]),
                t1_dice_lugar=mean([bool(t['lugar']) for t in t1]), r10_t1=mean([recall_at(t['rangos'], 10) for t in t1 if t['rangos']]),
                r10_con_lugar=mean([recall_at(t['rangos'], 10) for t in con if t['rangos']]), n_con=len(con),
                r10_sin_lugar=mean([recall_at(t['rangos'], 10) for t in sin if t['rangos']]), n_sin=len(sin),
                noto_problema=mean([i['detecto'] == 'si' for i in ints if i['detecto']]), confianza=mean([i['confianza'] for i in ints if i['confianza']]),
                min=med([float(i['segundos']) / 60 for i in ints if i.get('segundos')]),
                resp_con_otro_estado=mean([bool(set(t['resp_estados']) - {ESTADO_ESC[k]}) for t in ts]))
    # distribución de opciones por pregunta
    dist = defaultdict(Counter)
    for i in ints:
        for q, v in (i['respuestas'] or {}).items():
            if not q.endswith('__texto') and not q.startswith('_'): dist[q][v] += 1
    S[k]['opciones'] = {q: dict(c) for q, c in dist.items()}
    ef = escenario_efectivo(por_id[k.split('/')[0]], k.split('/')[1] if '/' in k else None)
    S[k]['correctas'] = {q['id']: q['correcta'] for q in ef['preguntas']}
out['por_situacion'] = S
# ── lugar y mezcla de estados: búsqueda vs. modelo
mix = Counter()
for t in T:
    if not t.get('respuesta'): continue
    k = esc_key(I[t['intento_id']]); est = ESTADO_ESC[k]
    otros_resp = set(t['resp_estados']) - {est}
    otros_ctx = set(t['ctx_estados']) - {est}
    if not otros_resp: mix['sin_otros_estados'] += 1
    elif otros_resp <= otros_ctx: mix['otros_estados_venian_en_contexto'] += 1
    else: mix['cita_estados_que_NO_estaban_en_contexto'] += 1
    if t['lugar'] or any(lugares_mencionados(x['pregunta']) for x in T if x['intento_id'] == t['intento_id'] and x['n'] < t['n']):
        mix['con_lugar_dicho_total'] += 1
        if otros_resp: mix['con_lugar_dicho_y_otros_estados'] += 1
out['mezcla_estados'] = dict(mix)
# ── Quáter / Quinquies / LG extorsión en «fotos»
q = Counter()
for t in T:
    if I[t['intento_id']]['escenario'] != 'fotos' or not t.get('respuesta'): continue
    a = fold(t['respuesta']); q['respuestas'] += 1
    q['cita_quater'] += bool(re.search(r'167\s*quater', a)); q['cita_quinquies'] += bool(re.search(r'167\s*quinquies', a))
    q['cita_lg15'] += bool(re.search(r'art(iculo|\.)?\s*15\b', a)) and 'extorsion' in a
    q['menciona_ley_olimpia'] += 'olimpia' in a
out['fotos_articulos'] = dict(q)
# ── estado citado (última situación)
out['estado_citado'] = dict(Counter((i['respuestas'] or {}).get('_estado_citado') for i in I.values() if '_estado_citado' in (i['respuestas'] or {})))
# ── citas textuales
out['otra_textos'] = [(esc_key(i), v) for i in I.values() for k2, v in (i['respuestas'] or {}).items() if k2.endswith('__texto')]
out['detecto_cual'] = [(cond(i['codigo']), esc_key(i), i['detecto_cual']) for i in I.values() if i.get('detecto_cual')]
out['comentarios'] = [(cond(i['codigo']), esc_key(i), i['comentario']) for i in I.values() if i.get('comentario')]
out['abiertas'] = [(cond(c), P[c]['perfil'].get('area'), qq, a) for c in P for qq, a in ((P[c].get('cierre') or {}).get('abiertas') or {}).items() if (a or '').strip()]
out['preguntas_ejemplo'] = {k: [(cond(I[t['intento_id']]['codigo']), t['pregunta']) for t in T if esc_key(I[t['intento_id']]) == k and t['n'] == 1][:40] for k in S}
out['participantes'] = part
json.dump(out, open('/tmp/ronda1.json', 'w'), ensure_ascii=False, indent=1, default=str)
print(json.dumps({k: out[k] for k in ('n', 'fechas', 'por_grupo', 'mezcla_estados', 'fotos_articulos', 'estado_citado')}, ensure_ascii=False, indent=1, default=str))
