"""Filtro por estado: sin filtro (A), v1 (B), v2 (B2) y v3 (B·v3), misma configuración en lo demás (base de la matriz,
penal-original-v1, sin routing), 4 sets, 2 repeticiones. Por set: score, recall y % de respuestas que citan otro estado;
diferencias pareadas con IC 95 %. En el set 14, por categoría de pregunta: score y si la respuesta pide el estado.
Corre en el servidor. Uso: python comparar_filtros.py <ids de B·v3 en el set 13> <ids en el set 12>"""
import json, random, re, sys, statistics as st, collections
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect
from shared.object_store import store
def art(rid):
    with connect() as c, c.cursor() as cur:
        cur.execute("select artifact_key from bench_runs where id=%s", (rid,)); k = cur.fetchone()[0]
    return {r['question_id']: r for r in store.get_json(k.removeprefix(store.prefix))['results'] if not r.get('error')}
v13, v12 = [tuple(int(x) for x in a.split(',')) for a in sys.argv[1:3]]
RUNS = {3: {'A': (109, 125), 'v1': (113, 129), 'v2': (147, 163), 'v3': (179, 181)},
        13: {'A': (107, 123), 'v1': (111, 127), 'v2': (148, 164), 'v3': v13},
        14: {'A': (108, 124), 'v1': (112, 128), 'v2': (149, 165), 'v3': (180, 182)},
        12: {'A': (110, 126), 'v1': (114, 130), 'v2': (150, 166), 'v3': v12}}
PIDE = re.compile(r'(?is)¿[^?]{0,200}\b(estado|entidad)\b[^?]{0,200}\?|\ben\s+qu[eé]\s+(estado|entidad)'
                  r'|(saber|conocer|precis\w*|indiqu\w*|indica\w*|proporcion\w*|dime|d[ií]game|compart\w*|se[nñ]al\w*)'
                  r'[^.]{0,60}\b(el|la|tu|su)\s+(estado|entidad)\b')
with connect() as c, c.cursor() as cur:
    cur.execute("select id, notes from bench_questions where set_id = 14")
    cat = {i: (re.search(r'cat=(\w+)', n or '') or [None, '?'])[1] for i, n in cur.fetchall()}
random.seed(0)
out = {}
for sid, cfgs in RUNS.items():
    A = {k: [art(r) for r in rs] for k, rs in cfgs.items()}
    qs = sorted(set.intersection(*[set(a) for v in A.values() for a in v]))
    media = {k: {q: st.mean(a[q]['score'] for a in v) for q in qs} for k, v in A.items()}
    fila = {}
    for k, v in A.items():
        hit = sum((a[q].get('retrieval') or {}).get('hit', 0) for a in v for q in qs)
        att = sum((a[q].get('retrieval') or {}).get('attainable', 0) for a in v for q in qs)
        otros = [bool((a[q].get('citations') or {}).get('other_states')) for a in v for q in qs
                 if (a[q].get('citations') or {}).get('other_states') is not None]
        fila[k] = {'reps': [round(st.mean(a[q]['score'] for q in qs) * 100, 1) for a in v],
                   'media': round(st.mean(media[k].values()) * 100, 1), 'recall': round(100 * hit / att, 1) if att else None,
                   'otro_estado': round(100 * sum(otros) / len(otros), 1) if otros else None}
    pares = {}
    for a_, b_ in (('A', 'v1'), ('v1', 'v2'), ('v2', 'v3'), ('A', 'v3')):
        d = [media[b_][q] - media[a_][q] for q in qs]
        bs = sorted(st.mean(random.choice(d) for _ in d) for _ in range(2000))
        pares[f'{a_}→{b_}'] = [round(100 * st.mean(d), 1), round(100 * bs[50], 1), round(100 * bs[1949], 1)]
    out[sid] = {'n': len(qs), 'filas': fila, 'pares': pares}
    if sid == 14:
        porcat = collections.defaultdict(dict)
        for k, v in A.items():
            for cname in sorted(set(cat[q] for q in qs)):
                grupo = [q for q in qs if cat[q] == cname]
                pide = sum(bool(PIDE.search(a[q].get('answer') or '')) for a in v for q in grupo)
                porcat[cname][k] = {'n': len(grupo), 'score': round(100 * st.mean(media[k][q] for q in grupo), 1),
                                    'pide_estado': f'{pide}/{2 * len(grupo)}'}
        out[sid]['categorias'] = porcat
print(json.dumps(out, ensure_ascii=False, indent=1))
