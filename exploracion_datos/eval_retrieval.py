"""
Eval de recuperación sobre el golden set jurídico (golden_penal.json).

Compara denso vs BM25 vs híbrido (RRF) sobre los chunks por estructura de
`shared.legal_chunking`, con la métrica corregida (recall@k / MRR) y desglose por
dificultad. Relevancia = el chunk recuperado contiene la frase-respuesta.

    uv run python exploracion_datos/eval_retrieval.py
    uv run python exploracion_datos/eval_retrieval.py --k 5 10 20

Requiere el túnel al TEI arriba; los embeddings de chunks salen de la caché
compartida (exploracion_datos/.embed_cache), así que casi no toca el túnel.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
LABS = HERE.parent
sys.path.insert(0, str(LABS))

from shared.legal_chunking import chunk_documents, clean_corpus, read_markdown_dir
from shared.lexical import BM25, rank_indices_by_score, rrf, tokenize
from shared.tei_client import TEIClient

CORPUS_DIR = LABS / 'ingestion' / 'out' / 'Sistema Penal Acusatorio'
CACHE_DIR = HERE / '.embed_cache'
GOLDEN = HERE / 'golden_penal.json'
Q_INSTRUCT = 'Instruct: Recupera el pasaje del código o la doctrina que responde la pregunta.\nQuery: '


def build_orders(texts, cvecs, qvecs, questions):
    """Para cada consulta: orden de índices de chunk según denso / bm25 / híbrido."""
    bm25 = BM25([tokenize(t) for t in texts])
    orders = {'denso': [], 'bm25': [], 'híbrido': []}
    for qi, question in enumerate(questions):
        dense = list(np.argsort(-(cvecs @ qvecs[qi])))
        lexical = rank_indices_by_score(bm25.scores(tokenize(question)))
        orders['denso'].append(dense)
        orders['bm25'].append(lexical)
        orders['híbrido'].append(rrf([dense, lexical]))
    return orders


def first_rank(order, answer, texts):
    for rank, j in enumerate(order, start=1):
        if answer in texts[j]:
            return rank
    return None


def metrics(order_list, golden, texts, ks):
    hits = {k: [] for k in ks}
    rr = []
    for qi, order in enumerate(order_list):
        rank = first_rank(order, golden[qi]['answer'], texts)
        rr.append(1.0 / rank if rank else 0.0)
        for k in ks:
            hits[k].append(bool(rank and rank <= k))
    return {**{f'recall@{k}': float(np.mean(hits[k])) for k in ks}, 'MRR': float(np.mean(rr))}


def rerank_orders(tei, questions, hybrid_orders, texts, candidates):
    """Reordena el top-N del híbrido con /rerank (cross-encoder). Devuelve, por
    consulta, el orden reordenado seguido del resto del híbrido (para completar)."""
    out = []
    for qi, question in enumerate(questions):
        cand = hybrid_orders[qi][:candidates]
        ranked = tei.rerank(question, [texts[j] for j in cand])
        new = [cand[i] for i, _ in ranked]
        rest = [j for j in hybrid_orders[qi] if j not in set(cand)]
        out.append(new + rest)
    return out


def per_question_records(orders, golden, texts, ks):
    """Una fila por (pregunta, método): rank del gold chunk + hits + reciprocal rank."""
    rows = []
    for name, order_list in orders.items():
        for qi, order in enumerate(order_list):
            rank = first_rank(order, golden[qi]['answer'], texts)
            rows.append({
                'idx': qi, 'question': golden[qi]['q'],
                'difficulty': golden[qi].get('difficulty', ''), 'type': golden[qi].get('type', ''),
                'method': name, 'gold_rank': rank if rank else '',
                **{f'hit@{k}': int(bool(rank and rank <= k)) for k in ks},
                'rr': round(1.0 / rank, 4) if rank else 0.0,
            })
    return pd.DataFrame(rows)


def aggregate_records(orders, golden, texts, ks):
    """Métricas agregadas por scope (global / por dificultad / por tipo) × método.
    Devuelve (DataFrame plano para CSV, dict anidado para JSON)."""
    scopes = [('global', list(range(len(golden))))]
    for d in ['easy', 'medium', 'hard', 'very_hard']:
        idx = [i for i, g in enumerate(golden) if g.get('difficulty') == d]
        if idx:
            scopes.append((f'difficulty:{d}', idx))
    for t in sorted({g.get('type', '') for g in golden}):
        if t:
            scopes.append((f'type:{t}', [i for i, g in enumerate(golden) if g.get('type') == t]))
    rows, nested = [], {}
    for scope, idx in scopes:
        nested[scope] = {}
        for name, order_list in orders.items():
            m = metrics([order_list[i] for i in idx], [golden[i] for i in idx], texts, ks)
            m = {'n': len(idx), **{kk: round(v, 4) for kk, v in m.items()}}
            rows.append({'scope': scope, 'method': name, **m})
            nested[scope][name] = m
    return pd.DataFrame(rows), nested


def _df_to_md(df):
    """Tabla GFM sin depender de `tabulate`."""
    df = df.round(3)
    cols = [str(c) for c in df.columns]
    head = '| ' + ' | '.join([''] + cols) + ' |'
    sep = '| ' + ' | '.join(['---'] * (len(cols) + 1)) + ' |'
    body = ['| ' + ' | '.join([str(i)] + [str(df.loc[i, c]) for c in df.columns]) + ' |' for i in df.index]
    return '\n'.join([head, sep] + body)


def write_results(out_dir, orders, golden, texts, ks, meta):
    """Escribe results.csv (detalle), evaluation_results.csv (agregados),
    metrics.json y results.md para poder analizarlos fuera del notebook."""
    out_dir.mkdir(parents=True, exist_ok=True)
    detail = per_question_records(orders, golden, texts, ks)
    agg, nested = aggregate_records(orders, golden, texts, ks)
    detail.to_csv(out_dir / 'results.csv', index=False)
    agg.to_csv(out_dir / 'evaluation_results.csv', index=False)
    json.dump({'meta': meta, 'metrics': nested},
              open(out_dir / 'metrics.json', 'w'), ensure_ascii=False, indent=2)

    global_df = pd.DataFrame(nested['global'])
    best = 'híbrido+rerank' if 'híbrido+rerank' in orders else 'híbrido'
    by_diff = pd.DataFrame({s.split(':', 1)[1]: nested[s][best]
                            for s in nested if s.startswith('difficulty:')})
    by_type = pd.DataFrame({s.split(':', 1)[1]: nested[s][best]
                            for s in nested if s.startswith('type:')})
    ranks = sorted(((first_rank(orders[best][i], golden[i]['answer'], texts), golden[i])
                    for i in range(len(golden))),
                   key=lambda r: (r[0] is not None, -(r[0] or 10**9)))
    worst = '\n'.join(f"- rank {r if r else '∞'} · [{g.get('difficulty','')}] {g['q']}" for r, g in ranks[:10])

    md = f"""# Resultados — evaluación de recuperación

- Test set: `{meta['golden']}` · preguntas: {meta['n_questions']} · chunks: {meta['n_chunks']}
- Embeddings (caché): `{meta['embed_model']}` · TEI sirve: `{meta['served']}`
- Métodos: {', '.join(orders)} · k = {list(ks)}
- Generado: {meta['timestamp']}

## Global (todas las preguntas)

{_df_to_md(global_df)}

## Por dificultad — {best}

{_df_to_md(by_diff)}

## Por tipo — {best}

{_df_to_md(by_type)}

## 10 peores preguntas — {best}

{worst}
"""
    (out_dir / 'results.md').write_text(md, encoding='utf-8')
    return out_dir


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--k', type=int, nargs='+', default=[5, 10, 20])
    ap.add_argument('--out', default=str(HERE / 'results'),
                    help='directorio donde escribir results.csv / evaluation_results.csv / metrics.json / results.md')
    ap.add_argument('--rerank', action='store_true',
                    help='añade una columna con reranking (TEI debe servir un reranker)')
    ap.add_argument('--embed-model', default=None,
                    help='modelo de la llave de caché de embeddings. Por defecto, el que TEI sirve '
                         '(embebe fresco si es nuevo). Para --rerank, se usa Qwen (lee su caché).')
    ap.add_argument('--candidates', type=int, default=50, help='top-N del híbrido que pasa al reranker')
    ap.add_argument('--multiquery', action='store_true',
                    help='añade multi-query: reescribe con el LLM (shared.llm_client) y fusiona denso(original)+denso(rewrite) por RRF')
    args = ap.parse_args()
    ks = tuple(args.k)
    # Con el reranker servido no se puede embeber; se leen los embeddings de Qwen de la caché.
    if args.rerank and not args.embed_model:
        args.embed_model = 'Qwen/Qwen3-Embedding-0.6B'

    golden = json.load(open(GOLDEN))
    questions = [g['q'] for g in golden]

    documents = clean_corpus(read_markdown_dir(CORPUS_DIR))
    chunks = chunk_documents(documents)
    texts = chunks['text_for_embedding'].tolist()

    tei = TEIClient(cache_dir=CACHE_DIR)
    try:
        served = tei.model_id
    except Exception:
        served = '(TEI offline — leyendo embeddings de caché)'
    print(f'TEI sirve: {served} · chunks: {len(texts)} · preguntas: {len(golden)}')
    # Los embeddings se leen de caché por su modelo original, aunque TEI sirva ahora
    # el reranker (así denso/híbrido se calculan sin el embedder en línea).
    cvecs = tei.embed(texts, cache_key_model=args.embed_model)
    qvecs = tei.embed([Q_INSTRUCT + q for q in questions], cache_key_model=args.embed_model)

    orders = build_orders(texts, cvecs, qvecs, questions)
    if args.multiquery:
        rw_cache = HERE / 'rewrites_penal.json'
        if rw_cache.exists():
            rewrites = json.load(open(rw_cache))
            print(f'multi-query: {len(rewrites)} reescrituras desde caché')
        else:
            from shared.llm_client import LlamaClient
            llm = LlamaClient()
            rewrites = [llm.rewrite_legal(q) for q in questions]
            json.dump(rewrites, open(rw_cache, 'w'), ensure_ascii=False, indent=2)
            print(f'multi-query: {len(rewrites)} reescrituras generadas con {llm.model}')
        rw_vecs = tei.embed([Q_INSTRUCT + r for r in rewrites], cache_key_model=args.embed_model)
        rw_dense = [list(np.argsort(-(cvecs @ rw_vecs[i]))) for i in range(len(questions))]
        orders['multi-query'] = [rrf([orders['denso'][i], rw_dense[i]]) for i in range(len(questions))]
    if args.rerank:
        print(f'reranking top-{args.candidates} del híbrido con {tei.model_id} ...')
        orders['híbrido+rerank'] = rerank_orders(tei, questions, orders['híbrido'], texts, args.candidates)

    # (1) Global
    overall = pd.DataFrame({name: metrics(ol, golden, texts, ks)
                            for name, ol in orders.items()}).round(3)
    print('\n── Global (todas las preguntas) ──')
    print(overall.to_string(), '\n')

    # (2) Por dificultad
    diffs = ['easy', 'medium', 'hard', 'very_hard']
    idx_by_diff = {d: [i for i, g in enumerate(golden) if g['difficulty'] == d] for d in diffs}
    show = ['híbrido'] + (['híbrido+rerank'] if args.rerank else [])
    for name in show:
        rows = {}
        for d in diffs:
            idx = idx_by_diff[d]
            if not idx:
                continue
            m = metrics([orders[name][i] for i in idx], [golden[i] for i in idx], texts, ks)
            rows[f'{d} (n={len(idx)})'] = m
        print(f'── Por dificultad · {name} ──')
        print(pd.DataFrame(rows).round(3).to_string(), '\n')

    # (3) Peores casos del mejor método disponible
    best = 'híbrido+rerank' if args.rerank else 'híbrido'
    ranks = [(first_rank(orders[best][i], golden[i]['answer'], texts), golden[i])
             for i in range(len(golden))]
    worst = sorted(ranks, key=lambda r: (r[0] is not None, -(r[0] or 10**9)))
    print(f'── {best}: 8 peores preguntas (rank del chunk correcto) ──')
    for rank, g in worst[:8]:
        print(f'   rank {rank if rank else "∞":>5}  [{g.get("difficulty",""):<9}] {g["q"][:64]}')

    # (4) Persistir a disco para analizar fuera del notebook.
    meta = {
        'golden': GOLDEN.name, 'n_questions': len(golden), 'n_chunks': len(texts),
        'embed_model': args.embed_model or served, 'served': served,
        'ks': list(ks), 'timestamp': datetime.now(timezone.utc).isoformat(timespec='seconds'),
    }
    out = write_results(Path(args.out), orders, golden, texts, ks, meta)
    print(f'\n✓ escritos: {out}/results.csv, evaluation_results.csv, metrics.json, results.md')


if __name__ == '__main__':
    main()
