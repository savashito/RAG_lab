"""Cálculos del estudio, sin BD ni LLM (para que se puedan probar y reproducir).

  · asignar: qué escenarios ve cada participante (balanceado por grupo, orden al azar).
  · puntuar_comprension: aciertos en las preguntas de opción múltiple.
  · rango_gold / recall_at: ¿la búsqueda trajo el artículo correcto con la pregunta de la persona?
  · kappa: acuerdo entre las dos calificaciones de estudiantes (Cohen).
  · necesita_experto: cuándo una respuesta pasa a la experta para desempatar.
  · sus: puntaje System Usability Scale (0–100).
  · resumen: las métricas del artículo, por grupo.
"""
from __future__ import annotations

import random
from collections import Counter, defaultdict

import re
import unicodedata

from shared.code_routes import codes_in, fold, short_label
from study.validar import DANOS

# Entidades o códigos penales que fijan la jurisdicción si la persona los nombra en su pregunta.
LUGARES = {'CDMX', 'CPEM', 'Morelos', 'Querétaro', 'CPF'}


def lugares_mencionados(pregunta: str) -> list[str]:
    """Qué estado o código penal nombra la persona en su pregunta («en qro», «en la cdmx», «código
    federal»…), con el mismo detector del routing por código. [] = no dijo dónde."""
    return [h['label'] for h in codes_in(pregunta or '') if h['label'] in LUGARES]


def asignar(escenarios: list[str], conteos: dict[str, int], n: int, rng: random.Random | None = None) -> list[str]:
    """Los `n` escenarios menos vistos por el grupo de la persona (empates al azar), en orden al azar.
    Así cada escenario recibe un número parecido de participantes de cada grupo."""
    rng = rng or random.Random()
    orden = sorted(escenarios, key=lambda e: (conteos.get(e, 0), rng.random()))
    elegidos = orden[:n]
    rng.shuffle(elegidos)
    return elegidos


def asignar_variante(variantes: list[str], conteos: dict[str, int], rng: random.Random | None = None) -> str:
    """La variante menos asignada en el grupo (empates al azar): mitad y mitad, sin que nadie vea dos."""
    rng = rng or random.Random()
    return min(variantes, key=lambda v: (conteos.get(v, 0), rng.random()))


def puntuar_comprension(escenario: dict, respuestas: dict) -> dict:
    """{'aciertos', 'total', 'no_se', 'detalle': {pregunta: bool | None}} — None = contestó «no sé»."""
    detalle = {}
    for p in escenario.get('preguntas') or []:
        r = (respuestas or {}).get(p['id'])
        detalle[p['id']] = None if r in (None, '', 'no_se') else r == p.get('correcta')
    return {'aciertos': sum(1 for v in detalle.values() if v), 'total': len(detalle),
            'no_se': sum(1 for v in detalle.values() if v is None), 'detalle': detalle}


def rango_gold(grupos: list[list[dict]], ranking: list[int]) -> list[int | None]:
    """Para cada artículo necesario (grupo de alternativas con sus `ids` de chunk), su mejor
    posición en el ranking (1 = primero) o None si no aparece."""
    pos = {cid: i + 1 for i, cid in enumerate(ranking or [])}
    out = []
    for g in grupos:
        rs = [pos[i] for x in g for i in x.get('ids') or [] if i in pos]
        out.append(min(rs) if rs else None)
    return out


def recall_at(rangos: list[int | None], k: int) -> float | None:
    return sum(1 for r in rangos if r is not None and r <= k) / len(rangos) if rangos else None


def kappa(pares: list[tuple[str, str]]) -> float | None:
    """Kappa de Cohen para pares (calificación A, calificación B) de la misma respuesta."""
    if not pares:
        return None
    n = len(pares)
    po = sum(1 for a, b in pares if a == b) / n
    ca, cb = Counter(a for a, _ in pares), Counter(b for _, b in pares)
    pe = sum(ca[c] * cb[c] for c in set(ca) | set(cb)) / (n * n)
    return 1.0 if pe == 1 else round((po - pe) / (1 - pe), 3)


def necesita_experto(calificaciones: list[dict]) -> bool:
    """Dos estudiantes en desacuerdo (veredicto, o daño a más de un nivel), o alguien marcó
    «peligroso»: la respuesta va a la experta."""
    est = [c for c in calificaciones if c['rol'] == 'estudiante']
    if any(c['dano'] == 'peligroso' for c in est):
        return True
    if len(est) < 2:
        return False
    a, b = est[0], est[1]
    return a['veredicto'] != b['veredicto'] or abs(DANOS.index(a['dano']) - DANOS.index(b['dano'])) > 1


def final(calificaciones: list[dict]) -> dict | None:
    """Calificación que cuenta: la de la experta si existe; si no, la de los estudiantes cuando
    coinciden en el veredicto (el daño, el más grave de los dos)."""
    exp = [c for c in calificaciones if c['rol'] == 'experto']
    if exp:
        return exp[-1]
    est = [c for c in calificaciones if c['rol'] == 'estudiante'][:2]
    if len(est) == 2 and not necesita_experto(est):
        peor = max(est, key=lambda c: DANOS.index(c['dano']))
        return dict(peor, veredicto=est[0]['veredicto'])
    return None


def sus(respuestas: list[int]) -> float | None:
    """Puntaje SUS 0–100 a partir de 10 respuestas 1–5."""
    if not respuestas or len(respuestas) != 10 or not all(isinstance(r, int) and 1 <= r <= 5 for r in respuestas):
        return None
    return sum((r - 1) if i % 2 == 0 else (5 - r) for i, r in enumerate(respuestas)) * 2.5


# Métricas corregidas (24-oct-2026, tras repetir las conversaciones de la ronda 1). Las originales cuentan menciones de
# lugares: «la competencia es de Querétaro y no de la Ciudad de México» contaba como citar la CDMX, y «la ley del lugar
# donde ocurrieron los hechos» como pedir el estado. Se calculan sobre el texto con fold() (minúsculas, sin acentos).
_E = r'(?:de |del |para )?(?:el |la )?'
CODIGO_ESTATAL = {   # el código penal de cada estado, nombrado como tal (no basta con el nombre del lugar)
    'CDMX': re.compile(rf'codigo penal {_E}(?:distrito federal|ciudad de mexico)|\bcpcdmx\b|\bcpdf\b'),
    'CPEM': re.compile(rf'codigo penal {_E}estado de mexico|\bcpem\b'),
    'Querétaro': re.compile(rf'codigo penal {_E}(?:estado de )?queretaro'),
    'Morelos': re.compile(rf'codigo penal {_E}(?:estado (?:libre y soberano )?de )?morelos'),
}
_LUGAR = r'(?:en que (?:estado|entidad|ciudad|lugar|municipio)|que (?:estado|entidad)|donde (?:ocurri|paso|sucedi|fue))'
_PIDE_ESTRICTO = re.compile(r'¿[^?]*' + _LUGAR + r'[^?]*\?')   # sobre el texto con acentos quitados pero con signos
_PIDE_DIRECTO = re.compile(r'(?:indica(?:me|nos)?|indique(?:me|nos)?|dime|digame|precis(?:a|ar|e)|necesito (?:saber|conocer)|'
                           r'necesario (?:saber|conocer|precisar)|podrias? (?:decirme|indicarme)|confirm(?:a|e|ar))[^.?]{0,60}' + _LUGAR)


def _sin_acentos(t: str) -> str:
    t = unicodedata.normalize('NFD', t or '')
    return ''.join(ch for ch in t if unicodedata.category(ch) != 'Mn').lower()


_PIDE_LUGAR = re.compile(r'en que (estado|entidad|lugar|ciudad)|que (estado|entidad)|entidad federativa donde|'
                         r'donde (ocurri|sucedi|paso|pasaron)|(indica|dime|podrias decir|necesito saber).{0,60}(estado|entidad|lugar)')


def analizar_respuesta(respuesta: str, gold: list[list[dict]]) -> dict:
    """Lo que se puede medir de una respuesta del asistente sin juez, comparándola con los artículos esperados
    (`gold` = grupos con 'source' y 'article'):
      · cita_ley_gold / cita_articulo_gold: ¿nombra el código correcto y el artículo correcto?
      · otros_estados: códigos penales de OTRA entidad (o el federal) que cita y no eran los esperados;
      · primera_ley: la primera ley que nombra (lo que la persona lee primero);
      · pide_lugar: ¿pregunta en qué estado ocurrió?;
      · palabras: longitud de la respuesta.
    Corregidas (24-oct): otro_codigo_estatal = códigos penales de otro estado que la respuesta NOMBRA como código (no
    basta con mencionar el lugar; el CPF no cuenta); pide_lugar_estricto = una pregunta «¿…?» o una petición directa
    («indícame…», «es necesario precisar…») sobre el estado o dónde ocurrió (no cuenta «la ley del lugar donde ocurrió»)."""
    txt = fold(respuesta or '')
    leyes = [h['label'] for h in codes_in(respuesta or '')]
    gold_leyes = {short_label(x.get('source')) for g in gold for x in g if x.get('source')}
    art_ok = False
    for g in gold:
        for x in g:
            partes = fold(x.get('article') or '').split()
            if not partes or short_label(x.get('source')) not in leyes:
                continue
            sufijo = r'\s*'.join(map(re.escape, partes))
            if re.search(r'(?<![0-9])' + sufijo + (r'(?!\s*(bis|ter|quater|quinquies|quintus|sextus)\b)' if len(partes) == 1 else r'\b'), txt):
                art_ok = True
    otros = [l for l in leyes if l in LUGARES and l not in gold_leyes]
    sin_ac = _sin_acentos(respuesta)
    otro_codigo = [l for l, rx in CODIGO_ESTATAL.items() if l not in gold_leyes and rx.search(txt)]
    return {'cita_ley_gold': bool(gold_leyes & set(leyes)) if gold_leyes else None,
            'cita_articulo_gold': art_ok if gold_leyes else None,
            'otros_estados': otros, 'primera_ley': leyes[0] if leyes else None,
            'primera_ley_es_otra': bool(leyes) and leyes[0] in LUGARES and leyes[0] not in gold_leyes if gold_leyes else None,
            'pide_lugar': bool(_PIDE_LUGAR.search(txt)), 'palabras': len((respuesta or '').split()),
            'otro_codigo_estatal': otro_codigo if gold_leyes else None,
            'pide_lugar_estricto': bool(_PIDE_ESTRICTO.search(sin_ac) or _PIDE_DIRECTO.search(fold(respuesta or '')))}


def grupo_de(p: dict) -> str:
    """Grupo para comparar. Los códigos del kiosco son «general»: se clasifican por lo que la persona dijo
    de su formación (derecho = estudia o estudió Derecho, o trabaja en algo jurídico)."""
    if p.get('grupo') != 'general':
        return p.get('grupo', '?')
    perfil = p.get('perfil') or {}
    if perfil.get('area') == 'derecho' or perfil.get('formacion_juridica') in ('carrera', 'trabajo'):
        return 'derecho'
    return 'no_derecho'


def resumen(datos: dict, fase: str | None = None) -> dict:
    """Métricas por grupo a partir del export (ver store.export). `datos['turnos'][i]['rangos']`
    ya trae la posición de cada artículo gold en el ranking de ese turno. `fase` = solo esos participantes
    («piloto», «principal»…); None = todos."""
    if fase is not None:
        cods = {p['codigo'] for p in datos['participantes'] if (p.get('fase') or '(sin fase)') == fase}
        ints = [i for i in datos['intentos'] if i['codigo'] in cods]
        ids = {i['id'] for i in ints}
        turnos = [t for t in datos['turnos'] if t['intento_id'] in ids]
        tids = {t['id'] for t in turnos}
        datos = dict(datos, participantes=[p for p in datos['participantes'] if p['codigo'] in cods], intentos=ints,
                     turnos=turnos, calificaciones=[c for c in datos['calificaciones'] if c['turno_id'] in tids])
    part = {p['codigo']: dict(p, grupo=grupo_de(p)) for p in datos['participantes']}
    intentos = {i['id']: i for i in datos['intentos']}
    cal = defaultdict(list)
    for c in datos['calificaciones']:
        cal[c['turno_id']].append(c)

    g = defaultdict(lambda: defaultdict(list))
    for t in datos['turnos']:
        it = intentos.get(t['intento_id'])
        if not it:
            continue
        grupo = (part.get(it['codigo']) or {}).get('grupo', '?')
        if t['n'] == 1 and t.get('rangos'):
            g[grupo]['r10_primer_turno'].append(recall_at(t['rangos'], 10))
        f = final(cal[t['id']])
        if f:
            g[grupo]['correcta'].append(f['veredicto'] == 'correcta')
            g[grupo]['danina'].append(f['dano'] in ('enganoso', 'peligroso'))
            if f['dano'] in ('enganoso', 'peligroso'):
                g[grupo]['danina_por_jurisdiccion'].append(f.get('error_jurisdiccion') == 'si')
    for it in datos['intentos']:
        grupo = (part.get(it['codigo']) or {}).get('grupo', '?')
        sc = it.get('comprension') or {}
        if sc.get('total'):
            acierto = sc['aciertos'] / sc['total']
            g[grupo]['comprension'].append(acierto)
            if it.get('confianza'):
                g[grupo]['confianza_vs_acierto'].append((it['confianza'], acierto))
    for p in part.values():
        s = sus(((p.get('cierre') or {}).get('sus')) or [])
        if s is not None:
            g[p['grupo']]['sus'].append(s)

    def media(xs):
        xs = [x for x in xs if x is not None]
        return round(sum(xs) / len(xs), 3) if xs else None

    out = {}
    for grupo, m in g.items():
        conf = m['confianza_vs_acierto']
        alta = [a for c, a in conf if c >= 4]
        out[grupo] = {
            'participantes': sum(1 for p in part.values() if p['grupo'] == grupo),
            'recall@10_primer_turno': media(m['r10_primer_turno']), 'n_turnos_con_gold': len(m['r10_primer_turno']),
            'respuestas_correctas': media(m['correcta']), 'respuestas_daninas': media(m['danina']),
            'daninas_por_jurisdiccion': media(m['danina_por_jurisdiccion']),
            'comprension': media(m['comprension']),
            # Sobreconfianza: con confianza 4–5, ¿qué tanto acertaron de verdad?
            'comprension_con_confianza_alta': media(alta), 'n_confianza_alta': len(alta),
            'sus': media(m['sus']),
        }
    pares = []
    for tid, cs in cal.items():
        est = [c for c in cs if c['rol'] == 'estudiante'][:2]
        if len(est) == 2:
            pares.append((est[0]['veredicto'], est[1]['veredicto']))
    # Por escenario (y variante): ¿en qué situación falla más? Separa p. ej. Querétaro vs CDMX.
    esc = defaultdict(lambda: defaultdict(list))
    clave_de = {i['id']: i['escenario'] + (f"/{i['variante']}" if i.get('variante') else '') for i in datos['intentos']}
    for t in datos['turnos']:
        k = clave_de.get(t['intento_id'])
        if not k or t['n'] != 1:
            continue
        lugar = bool(lugares_mencionados(t['pregunta']))
        esc[k]['menciona_lugar'].append(lugar)
        if t.get('rangos'):
            r = recall_at(t['rangos'], 10)
            esc[k]['r10'].append(r)
            esc[k]['r10_con_lugar' if lugar else 'r10_sin_lugar'].append(r)
    for it in datos['intentos']:
        sc = it.get('comprension') or {}
        if sc.get('total'):
            esc[clave_de[it['id']]]['comprension'].append(sc['aciertos'] / sc['total'])
        if it.get('detecto'):
            esc[clave_de[it['id']]]['detecto'].append(it['detecto'] == 'si')
    out['_por_escenario'] = {k: {'intentos': len(m['comprension']), 'recall@10_primer_turno': media(m['r10']),
                                 # ¿La primera pregunta dice dónde pasó? Y cómo cambia la búsqueda si no.
                                 'primera_pregunta_dice_lugar': media(m['menciona_lugar']),
                                 'recall@10_con_lugar': media(m['r10_con_lugar']),
                                 'recall@10_sin_lugar': media(m['r10_sin_lugar']),
                                 'comprension': media(m['comprension']), 'detecto_problema': media(m['detecto'])}
                             for k, m in sorted(esc.items())}
    # Por condición experimental (p. ej. prompt actual vs. sencillo): la comparación principal del experimento.
    cnd = defaultdict(lambda: defaultdict(list))
    cond_de = {i['id']: (part.get(i['codigo']) or {}).get('condicion') or '(sin condición)' for i in datos['intentos']}
    for t in datos['turnos']:
        k = cond_de.get(t['intento_id'])
        if not k:
            continue
        a = t.get('analisis') or {}
        cnd[k]['palabras'].append(a.get('palabras'))
        cnd[k]['pide_lugar'].append(a.get('pide_lugar'))
        cnd[k]['pide_lugar_estricto'].append(a.get('pide_lugar_estricto'))
        if t['n'] == 1:
            cnd[k]['cita_ley_gold'].append(a.get('cita_ley_gold'))
            cnd[k]['cita_articulo_gold'].append(a.get('cita_articulo_gold'))
            cnd[k]['primera_ley_es_otra'].append(a.get('primera_ley_es_otra'))
            if a.get('otro_codigo_estatal') is not None:
                cnd[k]['otro_codigo'].append(bool(a['otro_codigo_estatal']))
        f = final(cal[t['id']])
        if f:
            cnd[k]['correcta'].append(f['veredicto'] == 'correcta')
            cnd[k]['danina'].append(f['dano'] in ('enganoso', 'peligroso'))
    for it in datos['intentos']:
        k = cond_de[it['id']]
        sc = it.get('comprension') or {}
        if sc.get('total'):
            ac = sc['aciertos'] / sc['total']
            cnd[k]['comprension'].append(ac)
            if (it.get('confianza') or 0) >= 4:
                cnd[k]['comprension_conf_alta'].append(ac)
            cnd[k]['confianza'].append(it.get('confianza'))
        if it.get('detecto'):
            cnd[k]['detecto'].append(it['detecto'] == 'si')
        if it.get('actuaria'):
            cnd[k]['actuaria'].append(it['actuaria'] == 'si')
        r = it.get('respuestas') or {}
        if sc.get('total'):
            cnd[k]['eligio_otra'].append(any(v == 'otra' for q, v in r.items() if not q.startswith('_')))
    out['_por_condicion'] = {k: {
        'participantes': sum(1 for p in part.values() if (p.get('condicion') or '(sin condición)') == k),
        'situaciones': len(m['comprension']), 'comprension': media(m['comprension']),
        'confianza_media': media(m['confianza']), 'comprension_con_confianza_alta': media(m['comprension_conf_alta']),
        'noto_problema': media(m['detecto']), 'actuaria': media(m['actuaria']), 'eligio_no_esta_mi_respuesta': media(m['eligio_otra']),
        'palabras_por_respuesta': media(m['palabras']), 'asistente_pide_lugar': media(m['pide_lugar']),
        '1a_respuesta_cita_ley_correcta': media(m['cita_ley_gold']), '1a_respuesta_cita_articulo_correcto': media(m['cita_articulo_gold']),
        '1a_respuesta_empieza_con_otro_estado': media(m['primera_ley_es_otra']),
        '1a_respuesta_nombra_codigo_de_otro_estado': media(m['otro_codigo']), 'asistente_pide_lugar_estricto': media(m['pide_lugar_estricto']),
        'respuestas_correctas': media(m['correcta']), 'respuestas_daninas': media(m['danina'])}
        for k, m in sorted(cnd.items())}
    out['_acuerdo'] = {'kappa_veredicto_estudiantes': kappa(pares), 'pares': len(pares),
                       'a_experta': sum(1 for cs in cal.values() if necesita_experto(cs))}
    return out
