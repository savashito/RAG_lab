"""Ablación de recuperación (solo lectura): recall@10/@20 del artículo gold por configuración."""
import sys, os, time, json
os.chdir('/tmp/rltest/apps/rewrite_lab'); sys.path.insert(0, '.'); sys.path.insert(0, '../..')
import main as M, bench as B
CONFIGS = [  # (nombre, setting, hyde, decompose, route)
    ('BM25', 'bm25', False, False, False),
    ('Dense', 'orig', False, False, False),
    ('Hybrid (RRF)', 'híbrido', False, False, False),
    ('Hybrid+HyDE', 'híbrido', True, False, False),
    ('Hybrid+Decomp', 'híbrido', False, True, False),
    ('Hybrid+Routing', 'híbrido', False, False, True),
    ('Hybrid+HyDE+Decomp', 'híbrido', True, True, False),
    ('Hybrid+HyDE+Routing', 'híbrido', True, False, True),
]
SETS = [int(x) for x in sys.argv[1].split(',')]
res = {}
with M.connect() as c, c.cursor() as cur:
    for sid in SETS:
        s = B.Bench.load_set(type('X', (), {'topic_label': lambda self, t: t})(), cur, sid)
        qs = []
        for q in s['questions']:
            gold = [g for g in B.resolve_gold(cur, M.TABLE, B.gold_refs(q['question'], B.effective_components(q))) if any(x.get('ids') for x in g)]
            if gold: qs.append((q['question'], gold))
        for name, setting, hyde, dec, route in CONFIGS:
            h10 = h20 = n = 0; rr = 0.0; t0 = time.time()
            for question, gold in qs:
                scored, _, _ = M.retrieve_ranked(cur, question, setting, s['topic'], None, True, hyde, False, dec, route=route)
                ids = [cid for cid, _ in scored]
                chk = B.retrieval_check(gold, ids[:50])
                for g in chk['groups']:
                    n += 1; r = g['rank']
                    h10 += bool(r and r <= 10); h20 += bool(r and r <= 20); rr += (1 / r) if r else 0
            res[(sid, name)] = (h10, h20, n, rr / n, (time.time() - t0) / len(qs))
            print(f'set {sid} ({len(qs)} q, {n} gold) {name:22} R@10 {h10/n:.3f}  R@20 {h20/n:.3f}  MRR@50 {rr/n:.3f}  {(time.time()-t0)/len(qs):.2f}s/q', flush=True)
json.dump({f'{k[0]}|{k[1]}': v for k, v in res.items()}, open('/tmp/ablation.json', 'w'))
