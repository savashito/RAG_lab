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

from study.validar import DANOS


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


def grupo_de(p: dict) -> str:
    """Grupo para comparar. Los códigos del kiosco son «general»: se clasifican por lo que la persona dijo
    de su formación (derecho = estudia o estudió Derecho, o trabaja en algo jurídico)."""
    if p.get('grupo') != 'general':
        return p.get('grupo', '?')
    perfil = p.get('perfil') or {}
    if perfil.get('area') == 'derecho' or perfil.get('formacion_juridica') in ('carrera', 'trabajo'):
        return 'derecho'
    return 'no_derecho'


def resumen(datos: dict) -> dict:
    """Métricas por grupo a partir del export (ver store.export). `datos['turnos'][i]['rangos']`
    ya trae la posición de cada artículo gold en el ranking de ese turno."""
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
        if k and t['n'] == 1 and t.get('rangos'):
            esc[k]['r10'].append(recall_at(t['rangos'], 10))
    for it in datos['intentos']:
        sc = it.get('comprension') or {}
        if sc.get('total'):
            esc[clave_de[it['id']]]['comprension'].append(sc['aciertos'] / sc['total'])
        if it.get('detecto'):
            esc[clave_de[it['id']]]['detecto'].append(it['detecto'] == 'si')
    out['_por_escenario'] = {k: {'intentos': len(m['comprension']), 'recall@10_primer_turno': media(m['r10']),
                                 'comprension': media(m['comprension']), 'detecto_problema': media(m['detecto'])}
                             for k, m in sorted(esc.items())}
    out['_acuerdo'] = {'kappa_veredicto_estudiantes': kappa(pares), 'pares': len(pares),
                       'a_experta': sum(1 for cs in cal.values() if necesita_experto(cs))}
    return out
