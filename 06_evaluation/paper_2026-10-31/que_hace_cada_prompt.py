"""Ronda 2 (ronda2_penal): ¿qué hace cada prompt en las respuestas, y qué rasgos de la respuesta acompañan la confianza y
la disposición a actuar? (Major concern 4: el prompt cambia tono, extensión, estructura, cautela, preguntas, ofertas.)
1. Rasgos medidos con reglas fijas (sin LLM) en todas las respuestas y en la 1a, por prompt.
2. Por situación: cada rasgo (promedio de las respuestas de la situación) contra «actuaría» y la confianza 1–5, DENTRO de
   cada prompt (se resta la media del prompt), por formación jurídica. Diferencia entre el tercio alto y el bajo del rasgo.
3. Cuánto del efecto del prompt (intermedio − original y nuevo − original) queda al ajustar por los rasgos (MCO con
   variables de prompt; probabilidad lineal).
Bootstrap por participante (4000 réplicas, IC 95 %). Solo agregados.
    python que_hace_cada_prompt.py > que_hace_cada_prompt.json"""
import json, random, re, sys
from collections import defaultdict
import numpy as np
sys.path.insert(0, '/tmp')
import analisis_ronda2 as A                       # noqa: E402
from study.analisis import grupo_de               # noqa: E402

rng = random.Random(1)
PROMPTS = ('original', 'nuevo', 'intermedio')
R = lambda p: re.compile(p, re.I)                 # noqa: E731
TECNICISMOS = R(r'tipo penal|tipicidad|sujeto (?:activo|pasivo)|bien jur[ií]dico|elementos? (?:objetivos?|normativos?|subjetivos?)'
                r'|antijur[ií]dic|culpabilidad|dolo(?:so)?\b|querella|imputad[oa]|vinculaci[oó]n a proceso|medidas? cautelar'
                r'|ministerio p[uú]blico|carpeta de investigaci[oó]n|coadyuv|sobreseimiento|calificativ|agravante|punibilidad'
                r'|ordenamiento|fracci[oó]n|apartado [a-c]\b|en t[eé]rminos del|de conformidad con|con fundamento en')
CAUTELA = R(r'podr[ií]a|posiblemente|probablemente|depender[aá]|depende de|hip[oó]tesis|no es posible (?:determinar|afirmar)'
            r'|sujet[oa] a|en su caso|eventualmente|no se puede (?:afirmar|determinar|concluir)|provisional|no garantiz')
ABOGADO = R(r'abogad[oa]|asesor[ií]a (?:jur[ií]dica|legal|profesional)|asesor jur[ií]dico|defensor[ií]a|defensor(?:a)? p[uú]blic')
LIMITE = R(r'contexto|fragmentos? proporcionad|no contiene[n]? informaci[oó]n suficiente|informaci[oó]n insuficiente')
PASOS = R(r'\b(?:acude|ac[uú]dir|presenta|denuncia|guarda|conserva|toma (?:capturas?|fotos?)|llama|solicita|pide|bloquea'
          r'|reporta|no borres|no elimines|no pagues|no respondas|re[uú]ne|lleva|ve a|comun[ií]cate)\b')
OFRECE = R(r'(?:quieres|deseas|te gustar[ií]a|puedo ayudarte|si quieres|si lo deseas|si gustas)[^.?\n]{0,80}'
           r'(?:redact|borrador|escrito|denuncia|querella|formato)')
EMPATIA = R(r'lamento|siento mucho|entiendo|comprendo|no est[aá]s sol[oa]|no es tu culpa|es normal|es comprensible'
            r'|tranquil|no te preocupes|es v[aá]lido')
USTED = R(r'\busted(?:es)?\b|\bsu (?:caso|situaci[oó]n|denuncia)\b')
TU = R(r'\bt[uú]\b|\bte\b|\btu\b|\bpuedes\b|\bdebes\b|\btienes\b')
ARTICULO = R(r'\bart(?:[ií]culo|\.)s?\s*\d+')
CONCLUYE = R(r's[ií],? (?:es|constituye|podr[ií]a ser) (?:un )?delito|(?:esto|lo que describes|estos hechos) (?:es|son|constituye|podr[ií]a(?:n)? constituir)')


def silabas(p):
    return max(1, len(re.findall(r'[aeiouáéíóúü]+', p.lower())))


def rasgos(t):
    t = t or ''
    pal = re.findall(r'[A-Za-zÁÉÍÓÚáéíóúÑñÜü]+', t)
    n = max(len(pal), 1)
    frases = max(1, len([f for f in re.split(r'[.!?¿¡:\n]+', t) if len(f.split()) >= 3]))
    lineas = [l.strip() for l in t.splitlines() if l.strip()]
    vin = sum(bool(re.match(r'^(?:[-*•]|\d+[.)])\s', l)) for l in lineas)
    enc = sum(bool(re.match(r'^(?:#{1,4}\s|\*\*[^*]{2,60}\*\*:?\s*$)', l)) for l in lineas)
    c100 = lambda rx: 100 * len(rx.findall(t)) / n   # noqa: E731
    return {
        'palabras': len(pal),
        'palabras_por_frase': len(pal) / frases,
        'legibilidad_inflesz': 206.835 - 62.3 * sum(silabas(p) for p in pal) / n - len(pal) / frases,
        'lineas_en_vinetas_pct': 100 * vin / max(len(lineas), 1),
        'encabezados': enc,
        'articulos_citados': len(ARTICULO.findall(t)),
        'tecnicismos_por_100': c100(TECNICISMOS),
        'cautela_por_100': c100(CAUTELA),
        'menciona_abogado': float(bool(ABOGADO.search(t))),
        'habla_del_contexto_o_limites': float(bool(LIMITE.search(t))),
        'pasos_concretos': len(PASOS.findall(t)),
        'ofrece_redactar': float(bool(OFRECE.search(t))),
        'preguntas': t.count('¿'),
        'empatia': float(bool(EMPATIA.search(t))),
        'trata_de_usted': float(len(USTED.findall(t)) > len(TU.findall(t))),
        'dice_si_es_delito': float(bool(CONCLUYE.search(t))),
    }


RASGOS = list(rasgos('x'))
d, _ = A.cargar('ronda2_penal')
part = {p['codigo']: p for p in d['participantes']}
turnos = defaultdict(list)
for t in d['turnos']:
    turnos[t['intento_id']].append(t)
sit = []
for i in d['intentos']:
    p = part.get(i['codigo'])
    ts = [t for t in sorted(turnos[i['id']], key=lambda t: t['n']) if t.get('respuesta')]
    if not p or not ts or not i.get('fin') or p['condicion'] not in PROMPTS:
        continue
    rs = [rasgos(t['respuesta']) for t in ts]
    r = i.get('respuestas') or {}
    sit.append({'persona': i['codigo'], 'prompt': p['condicion'],
                'fo': 'con' if grupo_de(p) in ('derecho', 'estudiante') else 'sin',
                'primera': rs[0], 'todas': {k: float(np.mean([x[k] for x in rs])) for k in RASGOS}, 'n_resp': len(rs),
                'actuaria': None if not i.get('actuaria') else float(i['actuaria'] == 'si'),
                'confianza_1a5': i.get('confianza'),
                'escala_confianza_asistente': r.get('escala_confianza_asistente') if isinstance(r.get('escala_confianza_asistente'), int) else None})


def personas(ss):
    g = defaultdict(list)
    for s in ss:
        g[s['persona']].append(s)
    return list(g.values())


def ic(f, ss):
    """Valor e IC 95 % por bootstrap de participantes; f(lista de situaciones) → número o None."""
    v = f(ss)
    if v is None:
        return None
    ps = personas(ss)
    bs = sorted(x for x in (f([s for p in (rng.choice(ps) for _ in ps) for s in p]) for _ in range(4000)) if x is not None)
    return [round(v, 3), round(bs[int(.025 * len(bs))], 3), round(bs[int(.975 * len(bs)) - 1], 3)] if bs else None


out = {'n_situaciones': {fo: {c: len([s for s in sit if s['prompt'] == c and (fo == 'todos' or s['fo'] == fo)]) for c in PROMPTS}
                         for fo in ('todos', 'sin', 'con')}}

# 1. Qué hace cada prompt
out['rasgos_por_prompt'] = {
    cual: {k: {c: round(float(np.mean([s[cual][k] for s in sit if s['prompt'] == c])), 2) for c in PROMPTS} for k in RASGOS}
    for cual in ('primera', 'todas')}
out['respuestas_por_situacion'] = {c: round(float(np.mean([s['n_resp'] for s in sit if s['prompt'] == c])), 2) for c in PROMPTS}


# 2. Rasgo vs desenlace, dentro de cada prompt: tercio alto − tercio bajo del rasgo (cortes dentro del prompt)
def alto_menos_bajo(k, y):
    def f(ss):
        dif, peso = 0.0, 0
        for c in PROMPTS:
            xs = [s for s in ss if s['prompt'] == c and s[y] is not None]
            if len(xs) < 6:
                continue
            v = sorted(s['todas'][k] for s in xs)
            lo, hi = v[len(v) // 3], v[(2 * len(v)) // 3]
            if lo == hi:
                continue
            b = [s[y] for s in xs if s['todas'][k] <= lo]
            a = [s[y] for s in xs if s['todas'][k] >= hi]
            if a and b:
                dif += (np.mean(a) - np.mean(b)) * len(xs); peso += len(xs)
        return dif / peso if peso else None
    return f


out['rasgo_vs_desenlace_dentro_del_prompt'] = {
    fo: {y: {k: ic(alto_menos_bajo(k, y), [s for s in sit if fo == 'todos' or s['fo'] == fo]) for k in RASGOS}
         for y in ('actuaria', 'confianza_1a5', 'escala_confianza_asistente')}
    for fo in ('sin', 'con', 'todos')}


# 3. Efecto del prompt sin y con ajuste por rasgos (MCO, probabilidad lineal)
def efecto(y, ajuste, contraste):
    def f(ss):
        xs = [s for s in ss if s[y] is not None]
        if len(xs) < 20:
            return None
        X = [[1.0, float(s['prompt'] == 'nuevo'), float(s['prompt'] == 'intermedio')] +
             [s['todas'][k] for k in ajuste] for s in xs]
        X = np.array(X)
        if ajuste:
            m, sd = X[:, 3:].mean(0), X[:, 3:].std(0)
            sd[sd == 0] = 1
            X[:, 3:] = (X[:, 3:] - m) / sd
        b = np.linalg.lstsq(X, np.array([s[y] for s in xs]), rcond=None)[0]
        return float(b[1 if contraste == 'nuevo' else 2])
    return f


GRUPOS_AJUSTE = {
    'sin ajuste': [],
    'extensión y estructura': ['palabras', 'palabras_por_frase', 'lineas_en_vinetas_pct', 'encabezados'],
    'lenguaje (legibilidad, tecnicismos, usted)': ['legibilidad_inflesz', 'tecnicismos_por_100', 'trata_de_usted'],
    'cautela y límites': ['cautela_por_100', 'menciona_abogado', 'habla_del_contexto_o_limites'],
    'acción (pasos, ofrece redactar, dice si es delito)': ['pasos_concretos', 'ofrece_redactar', 'dice_si_es_delito'],
    'preguntas y empatía': ['preguntas', 'empatia'],
    'todos los rasgos': RASGOS,
}
out['efecto_del_prompt_con_ajuste'] = {
    fo: {y: {f'{c} − original': {g: ic(efecto(y, aj, c), [s for s in sit if fo == 'todos' or s['fo'] == fo])
                                 for g, aj in GRUPOS_AJUSTE.items()} for c in ('intermedio', 'nuevo')}
         for y in ('actuaria', 'confianza_1a5', 'escala_confianza_asistente')}
    for fo in ('sin', 'todos')}
print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
