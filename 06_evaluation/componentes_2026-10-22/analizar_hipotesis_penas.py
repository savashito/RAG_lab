import sys, re, random, statistics as st, collections
exec(open('/tmp/prueba_respuesta.py').read().split("PROMPTS = {")[0])
FUND = re.compile(r'(?im)^\W*fundamento')
V = {'a control': (193, 197), 'b + Fundamento': (195, 198), 'c + Fundamento + no preguntar': (196, 199)}
A = {k: [{x['question_id']: x for x in art(r) if not x.get('error')} for r in rs] for k, rs in V.items()}
for k, runs in A.items():
    c = collections.Counter()
    for a in runs:
        for x in a.values():
            ans = x.get('answer') or ''
            c['n'] += 1; c['fund'] += bool(FUND.search(ans)); c['pal'] += len(ans.split())
            for v in x.get('verdicts') or []:
                if v['kind'] == 'must' and re.match(r'(?i)\s*cita', v['text']):
                    c['cn'] += 1; c['cok'] += v.get('verdict') == 'presente'
                if v['kind'] == 'must_not' and re.search(r'(?i)elija un solo estado|aunque ya lo dijo', v['text']):
                    c['mn'] += 1; c['viol'] += v.get('verdict') == 'presente'
            c['seg'] += (x.get('timings') or {}).get('respuesta', 0)
    print(f"{k}: sección Fundamento {100*c['fund']/c['n']:.0f} % · «Cita el art.» {c['cok']}/{c['cn']} ({100*c['cok']/c['cn']:.0f} %) · "
          f"pide estado de más {c['viol']}/{c['mn']} · palabras {c['pal']/c['n']:.0f} · respuesta {c['seg']/c['n']:.2f} s")
random.seed(0)
def par(a, b):
    qs = set.intersection(*[set(x) for x in A[a] + A[b]])
    d = [st.mean(x[q]['score'] for x in A[b]) - st.mean(x[q]['score'] for x in A[a]) for q in qs]
    bs = sorted(st.mean(random.choice(d) for _ in d) for _ in range(2000))
    return f"{100*st.mean(d):+.1f} (IC 95 % {100*bs[50]:+.1f} a {100*bs[1949]:+.1f})"
print('a → b:', par('a control', 'b + Fundamento'))
print('b → c:', par('b + Fundamento', 'c + Fundamento + no preguntar'))
print('a → c:', par('a control', 'c + Fundamento + no preguntar'))
