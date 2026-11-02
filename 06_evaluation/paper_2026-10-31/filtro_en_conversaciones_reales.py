"""Ronda 2 (ronda2_penal): matriz de confusión del filtro por estado en los mensajes reales del estudio.
No guardamos la decisión del filtro por mensaje; se reconstruye con los códigos estatales del ranking (los 50 candidatos
que trajo el buscador, ya filtrados). Fila = qué estado nombró la persona en sus mensajes hasta ese turno (regex);
columna = qué código estatal dejó pasar el filtro. Estado de la situación: Querétaro, o Ciudad de México en la variante
cdmx de «mensajes_trabajo». Solo agregados.
    python filtro_en_conversaciones_reales.py > filtro_real.json"""
import json, re, sys
from collections import Counter, defaultdict
sys.path.insert(0, '/tmp')
import analisis_ronda2 as A                       # noqa: E402
from study.analisis import grupo_de               # noqa: E402

NOMBRE = {'queretaro': 'Querétaro', 'cdmx': 'CDMX', 'morelos': 'Morelos', 'edomex': 'Estado de México'}
LUGAR = {'Querétaro': re.compile(r'(?i)quer[eé]taro|\bqro\b|corregidora|el marqu[eé]s|san juan del r[ií]o'),
         'CDMX': re.compile(r'(?i)ciudad de m[eé]xico|\bcdmx\b|\bdf\b|distrito federal'),
         'Morelos': re.compile(r'(?i)morelos|cuernavaca'),
         'Estado de México': re.compile(r'(?i)estado de m[eé]xico|edomex|toluca')}

d, _ = A.cargar('ronda2_penal')
part = {p['codigo']: p for p in d['participantes']}
intento = {i['id']: i for i in d['intentos']}
with A.main.connect() as c, c.cursor() as cur:
    cur.execute('SELECT t.id, t.intento_id, t.n, t.pregunta, t.ranking FROM estudio_turnos t '
                'WHERE t.intento_id = ANY(%s) ORDER BY t.intento_id, t.n', (list(intento),))
    turnos = cur.fetchall()
    ids = sorted({x for t in turnos for x in (t[4] or [])})
    cur.execute(f'SELECT id, source FROM {A.main.TABLE} WHERE id = ANY(%s)', (ids,))
    jur = {i: A.main.jurisdiction_for_source(s) for i, s in cur.fetchall()}

filas = []
texto = defaultdict(str)
for tid, iid, n, preg, rank in turnos:
    i = intento[iid]
    p = part.get(i['codigo'])
    if not p or rank is None:
        continue
    texto[iid] += ' ' + (preg or '')
    foco = A.FOCAL.get((i['escenario'], i['variante']))
    nombro = {e for e, rx in LUGAR.items() if rx.search(texto[iid])}
    paso = {NOMBRE[jur[x]] for x in rank if jur.get(x) in NOMBRE}
    fila = ('nombró el estado de la situación' if foco in nombro else
            'nombró solo otro estado' if nombro else 'no nombró ningún estado')
    col = ('ningún código estatal' if not paso else
           'solo el código del estado de la situación' if paso == {foco} else
           'el de la situación y otro' if foco in paso else 'código de otro estado')
    filas.append({'fila': fila, 'col': col, 'primer': n == min(t[2] for t in turnos if t[1] == iid),
                  'fo': 'con' if grupo_de(p) in ('derecho', 'estudiante') else 'sin',
                  'federal': any(jur.get(x) == 'federal' for x in rank)})

out = {}
for nombre, sel in (('todos los mensajes', filas), ('primeros mensajes', [f for f in filas if f['primer']])):
    for fo in ('todos', 'sin', 'con'):
        xs = [f for f in sel if fo == 'todos' or f['fo'] == fo]
        m = Counter((f['fila'], f['col']) for f in xs)
        out[f'{nombre} · {fo}'] = {'n': len(xs), 'matriz': {r: {k: v for (a, k), v in m.items() if a == r}
                                                          for r in sorted({f['fila'] for f in xs})}}
out['codigo_penal_federal_en_ranking'] = Counter(f['federal'] for f in filas)
print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
