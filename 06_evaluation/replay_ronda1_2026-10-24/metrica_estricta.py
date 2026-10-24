"""La métrica de la ronda 1 («otros_estados», con codes_in) cuenta como cita cualquier mención de un lugar: en «citatorio»
la respuesta dice «la competencia es de Querétaro y no de la Ciudad de México» (donde vive la persona) y cuenta como
citar la CDMX. Esta versión estricta solo cuenta si la respuesta NOMBRA EL CÓDIGO PENAL de un estado que no es el de la
situación (o cita un artículo junto al nombre de ese estado). Mismos datos: ronda 1 guardada y repetición. Solo agregados.
    python metrica_estricta.py"""
import json, random, re, statistics as st, sys
from collections import defaultdict
from pathlib import Path
RAIZ = Path('/home/tlacua/apps/RAG_lab')
sys.path[:0] = [str(RAIZ / 'apps' / 'rewrite_lab'), str(RAIZ)]
import os; os.chdir(RAIZ / 'apps' / 'rewrite_lab')
import main                                          # noqa: E402
from shared.code_routes import short_label            # noqa: E402
from study.validar import escenario_efectivo          # noqa: E402

E = r'(?:del?\s+|para\s+(?:el\s+)?)?(?:la\s+|el\s+)?'
CODIGO = {
    'CDMX': re.compile(rf'(?i)c[oó]digo\s+penal\s+{E}(?:distrito\s+federal|ciudad\s+de\s+m[eé]xico)|\bcpcdmx\b|\bcpdf\b|\bcp\s?cdmx\b'),
    'CPEM': re.compile(rf'(?i)c[oó]digo\s+penal\s+{E}(?:estado\s+de\s+m[eé]xico)|\bcpem\b'),
    'Querétaro': re.compile(rf'(?i)c[oó]digo\s+penal\s+{E}(?:estado\s+de\s+)?quer[eé]taro'),
    'Morelos': re.compile(rf'(?i)c[oó]digo\s+penal\s+{E}(?:estado\s+(?:libre\s+y\s+soberano\s+)?de\s+)?morelos'),
}
datos = main.study_store.export('piloto_penal'); spec = main.study_store.spec('piloto_penal')
por_id = {e['id']: e for e in spec['escenarios']}
gold = {}
for i in datos['intentos']:
    k = (i['escenario'], i['variante'])
    if k not in gold and i['escenario'] in por_id:
        ef = escenario_efectivo(por_id[i['escenario']], i['variante'])
        grupos = main._study_resolver([g for x in ef.get('gold') or [] for g in main._study_gold_refs(x)])
        gold[k] = {short_label(x.get('source')) for g in grupos for x in g if x.get('source')}
print('Leyes esperadas por situación:', {f'{e} {v or ""}'.strip(): sorted(s) for (e, v), s in gold.items()})
def otro_codigo(resp, esc, var):
    return any(rx.search(resp or '') for lab, rx in CODIGO.items() if lab not in gold.get((esc, var), set()))

cond = {p['codigo']: p['condicion'] or 'piloto' for p in datos['participantes']}
intento = {i['id']: i for i in datos['intentos']}
base = defaultdict(list)
for t in datos['turnos']:
    if t['respuesta'] and t['n'] == 1:
        i = intento[t['intento_id']]
        base[cond.get(i['codigo'], '?')].append(otro_codigo(t['respuesta'], i['escenario'], i['variante']))
print('\nRonda 1 guardada · primer mensaje · nombra el código penal de otro estado:',
      {c: f'{100 * st.mean(v):.1f} % (n={len(v)})' for c, v in sorted(base.items())})

val = defaultdict(lambda: defaultdict(list))   # config → (intento, escenario) → [0/1 por repetición]
for f in sorted(Path('/tmp/replay_ronda1').glob('*_rep*.jsonl')):
    cfg = f.stem.rsplit('_rep', 1)[0]
    for l in f.open():
        x = json.loads(l)
        val[cfg][(x['intento_id'], x['escenario'])].append(otro_codigo(x['turnos'][0]['respuesta'], x['escenario'], x['variante']))
print('\nRepetición · primer mensaje · nombra el código penal de otro estado:')
for cfg, d in sorted(val.items()):
    por_esc = defaultdict(list)
    for (iid, esc), v in d.items():
        por_esc[esc].append(st.mean(v))
    print(f'  {cfg:9} {100 * st.mean(st.mean(v) for v in d.values()):.1f} % · ' +
          ' · '.join(f'{e} {100 * st.mean(v):.1f} %' for e, v in sorted(por_esc.items())))
random.seed(1)
for a, b in (('A_ronda1', 'B_filtro'), ('A_ronda1', 'C_nuevo')):
    d = [st.mean(val[b][k]) - st.mean(val[a][k]) for k in val[a] if k in val[b]]
    bs = sorted(st.mean(random.choices(d, k=len(d))) for _ in range(5000))
    print(f'  {a} → {b}: {100 * st.mean(d):+.1f} puntos [{100 * bs[125]:+.1f}, {100 * bs[4875]:+.1f}] (n={len(d)})')

# «pide_lugar» de la ronda 1 también cuenta frases que explican («la ley del lugar donde ocurrieron los hechos»). Estricta:
# una pregunta entre «¿…?», o una petición directa («indícame…», «es necesario precisar…»), sobre el estado o dónde ocurrió.
LUGAR = r'(en\s+qu[eé]\s+(estado|entidad|ciudad|lugar|municipio)|qu[eé]\s+(estado|entidad)|d[oó]nde\s+(ocurri|pas[oó]|sucedi|fue))'
PIDE = re.compile(r'(?i)¿[^?]*' + LUGAR + r'[^?]*\?|(ind[ií]ca(me|nos)?|ind[ií]que(me|nos)?|dime|d[ií]game|precis(a|ar|e)|'
                  r'necesito\s+(saber|conocer)|necesario\s+(saber|conocer|precisar)|podr[ií]as?\s+(decirme|indicarme)|confirm(a|e|ar))'
                  r'[^.?]{0,60}' + LUGAR)
print('\nRepetición · pide el estado (pregunta «¿…?» o petición directa) · por lo que decidió el filtro:')
for cfg in sorted(val):
    d = defaultdict(list)
    for f in sorted(Path('/tmp/replay_ronda1').glob(f'{cfg}_rep*.jsonl')):
        for l in f.open():
            x = json.loads(l)
            for j, t in enumerate(x['turnos']):
                fl = t.get('filtro')
                k = 'sin filtro' if fl is None else ('estado detectado' if fl.get('estados') else 'sin estado')
                d[(('primer mensaje' if j == 0 else 'siguientes'), k)].append(bool(PIDE.search(t['respuesta'] or '')))
    print(f'  {cfg:9} ' + ' · '.join(f'{a}, {k}: {100 * st.mean(v):.0f} % (n={len(v)})' for (a, k), v in sorted(d.items())))
