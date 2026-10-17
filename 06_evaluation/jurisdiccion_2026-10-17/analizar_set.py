"""Análisis sin juez de corridas del set «Jurisdicción · un solo estado»: por respuesta, ¿cita ARTÍCULOS de otra
entidad (pareando artículo→ley con verificar_citas.citas)?, ¿menciona otra entidad?, ¿cita el artículo correcto?,
y se compara con el veredicto del juez (must_not). Uso: python analizar_set.py <run_id> [<run_id> …]"""
import sys, json, re, collections
sys.path[:0] = ['/tmp', '/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect
from shared.object_store import store
from shared.code_routes import codes_in
from verificar_citas import citas
ESTADOS = {'CDMX': 'CDMX', 'QRO': 'Querétaro', 'EDOMEX': 'CPEM', 'MOR': 'Morelos'}   # notas → etiqueta de codes_in
ENTIDADES = set(ESTADOS.values())
for rid in map(int, sys.argv[1:]):
    with connect() as c, c.cursor() as cur:
        cur.execute("SELECT label, artifact_key FROM bench_runs WHERE id=%s", (rid,)); label, key = cur.fetchone()
        cur.execute("SELECT id, notes FROM bench_questions WHERE set_id=13"); notas = dict(cur.fetchall())
    art = store.get_json(key)
    filas, por_estado = [], collections.defaultdict(list)
    for r in art['results']:
        est = ESTADOS[re.search(r'estado=(\w+)', notas[r['question_id']]).group(1)]
        ans = r.get('answer') or ''
        cit = citas(ans)
        otros_art = sorted({f'{lab} {a}' for src, lab, a, _ in cit if lab in ENTIDADES and lab != est})
        menciona = sorted({h['label'] for h in codes_in(ans) if h['label'] in ENTIDADES} - {est})
        v = r.get('verdicts') or []
        juez_viola = any(c['kind'] == 'must_not' and (x or {}).get('verdict') == 'presente' for c, x in zip(r['components'], v))
        f = dict(q=r['question_id'], estado=est, otros_articulos=otros_art, menciona_otra=menciona, juez_viola=juez_viola,
                 pasa=r.get('passed'), recuperado=bool((r.get('retrieval') or {}).get('hit')), palabras=len(ans.split()))
        filas.append(f); por_estado[est].append(f)
    m = lambda xs: f'{sum(xs)}/{len(xs)} ({sum(xs) / len(xs):.0%})'
    print(f'\n### run {rid} · {label}')
    print('  cita ARTÍCULOS de otra entidad :', m([bool(f['otros_articulos']) for f in filas]))
    print('  menciona otra entidad (aunque sea para descartarla):', m([bool(f['menciona_otra']) for f in filas]))
    print('  juez: presenta otra entidad como aplicable:', m([f['juez_viola'] for f in filas]))
    print('  pasa (cita el artículo correcto y sin violación):', m([bool(f['pasa']) for f in filas]))
    print('  el artículo correcto llegó al contexto:', m([f['recuperado'] for f in filas]))
    acuerdo = sum(bool(f['otros_articulos']) == f['juez_viola'] for f in filas)
    print(f'  acuerdo juez vs. conteo de artículos: {acuerdo}/{len(filas)}')
    for est, fs in por_estado.items():
        print(f'    {est:10} otros artículos {m([bool(f["otros_articulos"]) for f in fs])} · pasa {m([bool(f["pasa"]) for f in fs])} · recuperado {m([f["recuperado"] for f in fs])}')
    for f in filas:
        if f['otros_articulos'] or f['juez_viola']:
            print(f"    q{f['q']} {f['estado']}: artículos de otra entidad {f['otros_articulos']} · juez={'viola' if f['juez_viola'] else 'ok'}")
    json.dump(filas, open(f'/tmp/jur_run{rid}.json', 'w'), ensure_ascii=False, indent=1)
