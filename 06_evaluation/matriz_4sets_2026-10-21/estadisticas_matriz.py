"""Estadísticas de la matriz 2026-10-21: por set y config, score de cada repetición, media, IC 95 % por bootstrap sobre
preguntas y comparaciones pareadas por pregunta. Se corre en el servidor; imprime JSON."""
import sys, json, random, re, statistics as st
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect
with connect() as c, c.cursor() as cur:
    cur.execute("select id, set_id, label, metrics from bench_runs where label like 'matriz-2026-10-21%%' and status='done' order by id")
    runs = cur.fetchall()
    cur.execute("select r.run_id, r.question_id, r.score from bench_results r join bench_runs b on b.id=r.run_id "
                "where b.label like 'matriz-2026-10-21%%' and r.error is null")
    por = {}
    for rid, qid, sc in cur.fetchall(): por.setdefault(rid, {})[qid] = sc
out = []
for rid, sid, label, m in runs:
    cfg = re.search(r'· (\w+) ', label).group(1); rep = int(label.rsplit('rep ', 1)[1])
    out.append({'id': rid, 'set': sid, 'cfg': cfg, 'rep': rep, 'score': m.get('score'), 'recall': m.get('retrieval_recall'),
                'otro': m.get('other_state_rate'), 'must': m.get('must_coverage'), 'pass': m.get('pass_rate'),
                'seg': m.get('avg_seconds'), 'unsup': m.get('cit_unsupported'), 'memoria': m.get('cit_memory'),
                'q': por.get(rid, {})})
# IC 95 % por bootstrap sobre preguntas (promedio de las 2 repeticiones por pregunta)
random.seed(0)
res = {}
for x in out:
    res.setdefault((x['set'], x['cfg']), []).append(x)
tabla = []
for (sid, cfg), xs in sorted(res.items()):
    xs.sort(key=lambda z: z['rep'])
    qs = sorted(set.intersection(*[set(z['q']) for z in xs]))
    medias = [st.mean(z['q'][q] for z in xs) for q in qs]
    boots = sorted(st.mean(random.choice(medias) for _ in medias) for _ in range(2000))
    def avg(k):
        v = [z[k] for z in xs if z[k] is not None]; return round(st.mean(v), 4) if v else None
    # Ruido de una misma pregunta entre las 2 repeticiones: DE combinada sqrt(media((a-b)^2 / 2)).
    de_rep = (st.mean((xs[0]['q'][q] - xs[1]['q'][q]) ** 2 / 2 for q in qs)) ** 0.5 if len(xs) == 2 else None
    tabla.append({'set': sid, 'cfg': cfg, 'runs': [z['id'] for z in xs], 'scores': [z['score'] for z in xs],
                  'de_preguntas': round(st.stdev(medias), 4) if len(medias) > 1 else None,
                  'de_rep': round(de_rep, 4) if de_rep is not None else None,
                  'media': round(st.mean(medias), 4), 'ic': [round(boots[50], 4), round(boots[1949], 4)], 'n': len(qs),
                  'recall': avg('recall'), 'otro': avg('otro'), 'must': avg('must'), 'pass': avg('pass'),
                  'seg': avg('seg'), 'unsup': avg('unsup'), 'memoria': avg('memoria')})
# comparaciones pareadas por pregunta (diferencia media e IC) para las preguntas clave
def pareada(sid, a, b):
    A = {q: st.mean(z['q'][q] for z in res[(sid, a)]) for q in set.intersection(*[set(z['q']) for z in res[(sid, a)]])}
    B = {q: st.mean(z['q'][q] for z in res[(sid, b)]) for q in set.intersection(*[set(z['q']) for z in res[(sid, b)]])}
    d = [B[q] - A[q] for q in A if q in B]
    boots = sorted(st.mean(random.choice(d) for _ in d) for _ in range(2000))
    return {'set': sid, 'a': a, 'b': b, 'dif': round(st.mean(d), 4), 'ic': [round(boots[50], 4), round(boots[1949], 4)], 'n': len(d)}
pares = [pareada(s, a, b) for s in (3, 13, 14, 12) for a, b in
         (('A', 'B'), ('B', 'B2'), ('A', 'B2'), ('B2', 'G2'), ('G2', 'C2'), ('C2', 'D2'), ('C', 'D'), ('D', 'E'))]
print(json.dumps({'tabla': tabla, 'pares': pares}, ensure_ascii=False))
