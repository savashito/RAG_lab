"""Prueba de la llamada del JUEZ: consistencia. El juez vuelve a calificar dos veces las MISMAS respuestas guardadas
(B·v3: #179 set 3 y #180 set 14), con el mismo prompt y temperatura 0. Mide:
- acuerdo por criterio (presente/parcial/ausente) entre la calificación original y cada recalificación;
- DE del score de una misma respuesta entre calificaciones (ruido del juez). Se compara con la «DE repetición» de la
  matriz, que mezcla el ruido de la respuesta y el del juez.
No modifica nada en la base. Corre en el servidor."""
import json, os, statistics as st, sys
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect
from shared.llm_client import LlamaClient
from shared.object_store import store
from bench import build_judge_prompt, judge_system, parse_judge, score_question
judge = LlamaClient(url=os.environ.get('JUDGE_URL') or os.environ.get('LLM_URL', 'http://127.0.0.1:1237'))
res = {}
for rid in (179, 180):
    with connect() as c, c.cursor() as cur:
        cur.execute("select b.artifact_key, coalesce(s.judge_notes, ''), b.set_id from bench_runs b join bench_sets s on s.id = b.set_id where b.id = %s", (rid,))
        key, notas, sid = cur.fetchone()
    filas = [x for x in store.get_json(key.removeprefix(store.prefix))['results'] if not x.get('error') and x.get('verdicts')]
    acuerdo, total, des, cambia = 0, 0, [], 0
    for x in filas:
        comps = [{'text': v['text'], 'kind': v['kind'], 'weight': v.get('weight', 1)} for v in x['verdicts']]
        scores = [x['score']]
        for _ in range(2):
            raw = judge.chat(judge_system(notas), build_judge_prompt(x['question'], x['answer'], comps, x.get('expected_answer') or ''),
                             temperature=0.0, max_tokens=1200, timeout=180, extra={'response_format': {'type': 'json_object'}})
            nv = parse_judge(raw, len(comps))
            acuerdo += sum(a.get('verdict') == b.get('verdict') for a, b in zip(x['verdicts'], nv)); total += len(comps)
            scores.append(score_question(comps, nv)['score'])
        des.append(st.pstdev(scores)); cambia += max(scores) - min(scores) >= 0.2
    res[sid] = {'respuestas': len(filas), 'acuerdo_criterio': round(acuerdo / total, 4), 'de_media': round(st.mean(des), 4),
                'de_rms': round(st.mean(d * d for d in des) ** 0.5, 4), 'cambian_20pts': cambia}
    print(f"set {sid}: {len(filas)} respuestas · acuerdo por criterio {acuerdo/total:.1%} · DE del score entre "
          f"calificaciones {res[sid]['de_rms']*100:.1f} puntos · respuestas cuyo score cambia ≥20 puntos: {cambia}", flush=True)
json.dump(res, open('/tmp/prueba_juez.json', 'w'))
