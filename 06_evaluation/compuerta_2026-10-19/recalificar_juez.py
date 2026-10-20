"""Corrige los puntajes guardados de las corridas afectadas por el lector del juez (c1648be: aceptaba solo
«veredicto»; el juez a veces escribe «verdicto»). Relee judge_raw del artefacto con parse_judge corregido y, solo en
las preguntas donde algún veredicto cambia, actualiza bench_results (veredictos, score, pasa, must_ok, violaciones),
las métricas de la corrida y el artefacto. Respaldo previo en _bak_20261019_judge_rescore. Corre en prod:
    cd ~/apps/RAG_lab/apps/rewrite_lab && ~/.local/bin/uv run python ../../06_evaluation/compuerta_2026-10-19/recalificar_juez.py [--aplicar]
Sin --aplicar solo muestra qué cambiaría."""
import json, sys
from dotenv import load_dotenv; load_dotenv('.env')
sys.path[:0] = ['.', '../..']
from shared.db import connect
from shared.object_store import store
from bench import aggregate, parse_judge, score_question

APLICAR = '--aplicar' in sys.argv
COLS = ['score', 'passed', 'must_total', 'must_ok', 'violations', 'verdicts', 'seconds', 'error', 'retrieval', 'citations', 'timings']
with connect() as c, c.cursor() as cur:
    if APLICAR:
        cur.execute("""CREATE TABLE IF NOT EXISTS _bak_20261019_judge_rescore (
            run_id int, question_id int, score real, passed boolean, must_ok int, violations int, verdicts jsonb,
            saved_at timestamptz DEFAULT now())""")
    cur.execute("SELECT id, artifact_key, metrics->>'score' FROM bench_runs WHERE status IN ('done', 'cancelled', 'interrupted') "
                "AND artifact_key IS NOT NULL ORDER BY id")
    runs = cur.fetchall()
    total_q = 0
    for rid, key, old_score in runs:
        try:
            art = store.get_json(key)
        except Exception as e:  # noqa: BLE001
            print(f'#{rid}: sin artefacto ({e})'); continue
        cambios = 0
        for d in art.get('results', []):
            qid = d.get('question_id')
            if d.get('error') or not d.get('verdicts') or not d.get('judge_raw'):
                continue
            comps = [{'text': v['text'], 'kind': v['kind'], 'weight': v.get('weight', 1)} for v in d['verdicts']]
            nuevos = parse_judge(d['judge_raw'], len(comps))
            if [v['verdict'] for v in nuevos] == [v.get('verdict') for v in d['verdicts']]:
                continue
            sc = score_question(comps, nuevos)
            ver = [{**cm, **nv} for cm, nv in zip(comps, nuevos)]
            cambios += 1
            if APLICAR:
                cur.execute("INSERT INTO _bak_20261019_judge_rescore (run_id, question_id, score, passed, must_ok, violations, verdicts) "
                            "SELECT run_id, question_id, score, passed, must_ok, violations, verdicts FROM bench_results "
                            "WHERE run_id = %s AND question_id = %s", (rid, qid))
                cur.execute("UPDATE bench_results SET verdicts = %s::jsonb, score = %s, passed = %s, must_total = %s, must_ok = %s, "
                            "violations = %s WHERE run_id = %s AND question_id = %s",
                            (json.dumps(ver, ensure_ascii=False), sc['score'], sc['passed'], sc['must_total'], sc['must_ok'],
                             sc['violations'], rid, qid))
                d.update(verdicts=ver, score=sc['score'], passed=sc['passed'])
        if not cambios:
            continue
        total_q += cambios
        cur.execute(f"SELECT {', '.join(COLS)} FROM bench_results WHERE run_id = %s", (rid,))
        rows = [dict(zip(COLS, r)) for r in cur.fetchall()]
        if APLICAR:
            metrics = aggregate(rows)
            cur.execute("UPDATE bench_runs SET metrics = %s::jsonb WHERE id = %s", (json.dumps(metrics), rid))
            art['metrics'] = metrics
            store.put_json(key.removeprefix(store.prefix), art)
            c.commit()
            print(f'#{rid}: {cambios} preguntas corregidas · score {float(old_score):.1%} → {metrics["score"]:.1%}')
        else:
            print(f'#{rid}: {cambios} preguntas cambiarían')
    print(('APLICADO' if APLICAR else 'SIMULACIÓN'), '· preguntas:', total_q)
