import sys, re, random, statistics as st, collections
exec(open('/tmp/analizar_descomponer.py').read().split("RUNS = {")[0])
random.seed(0)
RUNS = {3: {'con': (179, 181), 'sin': (185, 189), 'routing': (187, 191)}, 14: {'con': (180, 182), 'sin': (186, 190), 'routing': (188, 192)}}
def par(A, B, qs):
    d = [st.mean(x[q]['score'] for x in B) - st.mean(x[q]['score'] for x in A) for q in qs]
    bs = sorted(st.mean(random.choice(d) for _ in d) for _ in range(2000))
    return f"{100*st.mean(d):+.1f} (IC 95 % {100*bs[50]:+.1f} a {100*bs[1949]:+.1f})"
def verdict_cita(x, label):
    num = label.split()[-1] if label.split()[-1].lower() not in ('bis', 'ter') else ' '.join(label.split()[-2:])
    for v in x.get('verdicts') or []:
        if v['kind'] == 'must' and re.match(r'(?i)\s*cita', v['text']) and re.search(r'\b' + re.escape(num) + r'\b', v['text'], re.I):
            return v.get('verdict')
    return None
for sid, cfgs in RUNS.items():
    R = {k: [art(r) for r in v] for k, v in cfgs.items()}
    qs = sorted(set.intersection(*[set(a) for v in R.values() for a in v]))
    print(f"set {sid}: score con − sin descomponer {par(R['sin'], R['con'], qs)} · routing − con descomponer {par(R['con'], R['routing'], qs)}")
    c = collections.Counter()
    for q in qs:
        for i in (0, 1):
            con, sin = R['con'][i][q], R['sin'][i][q]
            gc = {tuple(g['labels']): g['rank'] for g in (con.get('retrieval') or {}).get('groups', [])}
            gs = {tuple(g['labels']): g['rank'] for g in (sin.get('retrieval') or {}).get('groups', [])}
            for lab, rank in gc.items():
                if rank and not gs.get(lab):
                    c['ganados'] += 1
                    vc, vs = verdict_cita(con, lab[0]), verdict_cita(sin, lab[0])
                    c[f'con={vc} · sin={vs}'] += 1
                if gs.get(lab) and not rank:
                    c['perdidos'] += 1
    print('   artículos que llegaron SOLO con descomponer:', c['ganados'], '· SOLO sin descomponer:', c['perdidos'])
    for k, v in sorted(c.items()):
        if k.startswith('con='): print('     juez sobre su «Cita el art.»:', k, v)
print('=====')
for sid, cfgs in RUNS.items():
    R = {k: [art(r) for r in v] for k, v in cfgs.items()}
    qs = sorted(set.intersection(*[set(a) for v in R.values() for a in v]))
    for k, nombre in (('sin', 'nada'), ('routing', 'routing'), ('con', 'descomponer')):
        sc = st.mean(st.mean(x[q]['score'] for x in R[k]) for q in qs)
        hit = sum((x[q].get('retrieval') or {}).get('hit', 0) for x in R[k] for q in qs)
        att = sum((x[q].get('retrieval') or {}).get('attainable', 0) for x in R[k] for q in qs)
        b = [(x[q].get('timings') or {}).get('busqueda') for x in R[k] for q in qs]
        b = [v for v in b if v is not None]
        extra = '' if k == 'sin' else f" · score vs nada {par(R['sin'], R[k], qs)}"
        print(f"set {sid} {nombre:12s} score {sc*100:.1f} · recall {hit}/{att} ({100*hit/att:.1f} %) · búsqueda {st.mean(b):.2f} ± {st.pstdev(b):.2f} s{extra}")
