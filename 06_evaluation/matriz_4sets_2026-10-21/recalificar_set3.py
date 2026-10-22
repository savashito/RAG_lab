"""Recalifica las corridas guardadas del set 3 con los criterios corregidos por corregir_set3.py (correrlo antes).

- Preguntas a las que solo se les quitó un `should` duplicado: se quita SOLO el veredicto de ese criterio y se
  recalcula el puntaje. No hace falta llamar al juez (cada criterio tiene su propio veredicto en el JSON del juez).
  Los demás veredictos quedan como estaban, aunque la corrida sea anterior a otras ediciones del set.
- La pregunta de la prescripción (criterios nuevos): el juez vuelve a calificar la respuesta GUARDADA (no se genera
  una respuesta nueva), con el mismo prompt del juez y los criterios del set.

Actualiza bench_results, las métricas de la corrida y el artefacto (guarda el veredicto previo en `judge_raw_previo`).
No recalcula el recall del buscador: los ids de los chunks de corridas viejas no corresponden a la base actual.
Respaldo previo en _bak_20261021_set3_rescore. Corre en prod:
    cd ~/apps/RAG_lab/apps/rewrite_lab && ../../.venv/bin/python ../../06_evaluation/matriz_4sets_2026-10-21/recalificar_set3.py [--aplicar]"""
import json, os, sys
from dotenv import load_dotenv; load_dotenv('.env')
sys.path[:0] = ['.', '../..']
from shared.db import connect
from shared.llm_client import LlamaClient
from shared.object_store import store
from bench import aggregate, build_judge_prompt, judge_system, parse_judge, score_question

APLICAR = '--aplicar' in sys.argv
SET = 3
COLS = ['score', 'passed', 'must_total', 'must_ok', 'violations', 'verdicts', 'seconds', 'error', 'retrieval', 'citations', 'timings']
judge = LlamaClient(url=os.environ.get('JUDGE_URL') or os.environ.get('LLM_URL', 'http://127.0.0.1:1237'))

with connect() as c, c.cursor() as cur:
    cur.execute("SELECT judge_notes FROM bench_sets WHERE id = %s", (SET,))
    notas = (cur.fetchone()[0] or '').strip()
    cur.execute("SELECT q.id, q.expected_answer, k.text, k.kind, k.weight FROM bench_questions q "
                "JOIN bench_components k ON k.question_id = q.id WHERE q.set_id = %s ORDER BY q.id, k.position", (SET,))
    nuevos, esperada = {}, {}
    for qid, exp, text, kind, w in cur.fetchall():
        nuevos.setdefault(qid, []).append({'text': text, 'kind': kind, 'weight': float(w or 1)})
        esperada[qid] = exp or ''
    # Lo que cambió corregir_set3.py: criterios borrados (respaldo − actuales) y la pregunta con criterios nuevos.
    cur.execute("SELECT b.question_id, b.text, b.kind FROM _bak_20261021_set3_components b "
                "LEFT JOIN bench_components k ON k.id = b.id WHERE k.id IS NULL")
    borrados = {}
    for qid, text, kind in cur.fetchall():
        borrados.setdefault(qid, set()).add((text, kind))
    cur.execute("SELECT q.id FROM bench_questions q JOIN _bak_20261021_set3_questions b ON b.id = q.id "
                "WHERE q.expected_answer IS DISTINCT FROM b.expected_answer")
    rejuzgar = {r[0] for r in cur.fetchall()}
    print('criterios borrados en', sorted(q for q in borrados if q not in rejuzgar), '· rejuzgar', sorted(rejuzgar))
    if APLICAR:
        cur.execute("""CREATE TABLE IF NOT EXISTS _bak_20261021_set3_rescore (
            run_id int, question_id int, score real, passed boolean, must_total int, must_ok int, violations int,
            verdicts jsonb, saved_at timestamptz DEFAULT now())""")
    cur.execute("SELECT id, artifact_key, metrics FROM bench_runs WHERE set_id = %s AND status = 'done' "
                "AND artifact_key IS NOT NULL ORDER BY id", (SET,))
    runs = cur.fetchall()
    juez_n = 0
    for rid, key, metrics_viejas in runs:
        k = key.removeprefix(store.prefix)
        art = store.get_json(k)
        cambios = []
        for d in art.get('results', []):
            qid, ver = d.get('question_id'), d.get('verdicts') or []
            if d.get('error') or not ver or (qid not in borrados and qid not in rejuzgar):
                continue
            if qid not in rejuzgar:
                nv = [v for v in ver if (v['text'], v['kind']) not in borrados[qid]]
                if len(nv) == len(ver):
                    continue   # esta corrida no tenía ese criterio
                comps = [{'text': v['text'], 'kind': v['kind'], 'weight': v.get('weight', 1)} for v in nv]
                como = 'sin juez'
            else:
                comps = nuevos[qid]
                if not d.get('answer'):
                    continue
                prompt = build_judge_prompt(d['question'], d['answer'], comps, esperada[qid])
                raw = judge.chat(judge_system(notas), prompt, temperature=0.0, max_tokens=1200, timeout=180,
                                 extra={'response_format': {'type': 'json_object'}}) if APLICAR else None
                juez_n += 1
                if raw is None:
                    cambios.append((qid, d.get('score'), None, 'juez (simulación)'))
                    continue
                nv = [{**x, **v} for x, v in zip(comps, parse_judge(raw, len(comps)))]
                d['judge_raw_previo'], d['judge_raw'], d['judge_prompt'] = d.get('judge_raw'), raw, prompt
                como = 'juez'
            sc = score_question(comps, nv)
            cambios.append((qid, d.get('score'), sc['score'], como))
            if APLICAR:
                cur.execute("INSERT INTO _bak_20261021_set3_rescore (run_id, question_id, score, passed, must_total, must_ok, "
                            "violations, verdicts) SELECT run_id, question_id, score, passed, must_total, must_ok, violations, "
                            "verdicts FROM bench_results WHERE run_id = %s AND question_id = %s", (rid, qid))
                cur.execute("UPDATE bench_results SET verdicts = %s::jsonb, score = %s, passed = %s, must_total = %s, "
                            "must_ok = %s, violations = %s WHERE run_id = %s AND question_id = %s",
                            (json.dumps(nv, ensure_ascii=False), sc['score'], sc['passed'], sc['must_total'],
                             sc['must_ok'], sc['violations'], rid, qid))
                d.update(verdicts=nv, components=comps, score=sc['score'], passed=sc['passed'])
                if qid in rejuzgar:
                    d['expected_answer'] = esperada[qid]
        if not cambios:
            continue
        linea = ' · '.join(f'q{q} {a:.2f}→{"?" if b is None else f"{b:.2f}"}' for q, a, b, _ in cambios if a is not None)
        if APLICAR:
            cur.execute(f"SELECT {', '.join(COLS)} FROM bench_results WHERE run_id = %s", (rid,))
            rows = [dict(zip(COLS, r)) for r in cur.fetchall()]
            metrics = {**(metrics_viejas or {}), **aggregate(rows), 'recalificado': '2026-10-21 set 3 corregido'}
            cur.execute("UPDATE bench_runs SET metrics = %s::jsonb WHERE id = %s", (json.dumps(metrics), rid))
            art['metrics'] = metrics
            store.put_json(k, art)
            c.commit()
            print(f'#{rid}: score {metrics_viejas["score"]:.1%} → {metrics["score"]:.1%} | {linea}', flush=True)
        else:
            print(f'#{rid}: {len(cambios)} preguntas cambiarían | {linea}', flush=True)
    print(('APLICADO' if APLICAR else 'SIMULACIÓN'), f'· corridas {len(runs)} · llamadas al juez {juez_n}')
