import sys, re, collections
exec(open('/tmp/prueba_respuesta.py').read().split("PROMPTS = {")[0])
RUNS = {'penal-original-v1': {3: (155, 171), 13: (156, 172), 14: (157, 173)},
        'tlacua-v1-penas': {3: (159, 175), 13: (160, 176), 14: (161, 177)}}
for p, sets in RUNS.items():
    out = []
    for sid, rs in sets.items():
        c = collections.Counter()
        for r in rs:
            for x in art(r):
                for v in x.get('verdicts') or []:
                    if v['kind'] == 'must' and re.match(r'(?i)\s*cita', v['text']):
                        c['n'] += 1; c['ok'] += v.get('verdict') == 'presente'
                    elif v['kind'] == 'must':
                        c['n2'] += 1; c['ok2'] += v.get('verdict') == 'presente'
                    if v['kind'] == 'must_not' and re.search(r'(?i)elija un solo estado|aunque ya lo dijo', v['text']):
                        c['mn'] += 1; c['viol'] += v.get('verdict') == 'presente'
        out.append(f"set {sid}: «Cita el art.» {c['ok']}/{c['n']} ({100*c['ok']/c['n']:.0f} %) · otros must {(100*c['ok2']/c['n2']) if c['n2'] else 0:.0f} %"
                   + (f" · pide estado de más {c['viol']}/{c['mn']}" if c['mn'] else ''))
    print(p, '\n   ' + '\n   '.join(out))
