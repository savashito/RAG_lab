"""
Lab 06 — Evaluation: an embedder bake-off on the real RAM papers.

This is where "which model is better?" stops being vibes. It reuses the
ingestion pipeline (chunk → embed → pgvector) and the hand-labelled eval set to
compute REAL retrieval metrics (recall@k, MRR, nDCG) for whatever embedder TEI
is currently serving. Run it once per model (swap TEI's --model-id between runs),
then `report` prints the combined table.

Workflow (see 06_evaluation/README.md):
    # 1. point TEI at a model on the GPU (downloads on the server), tunnel up
    # 2. score it:
    uv run python 06_evaluation/bakeoff.py run --k 5
    # 3. swap TEI to the next model, score again, then:
    uv run python 06_evaluation/bakeoff.py report

Nothing downloads to your laptop — embedding happens on the GPU via `--model tei`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))                 # labs/  (shared)
sys.path.insert(0, str(HERE.parent / "ingestion"))   # ram_rag
sys.path.insert(0, str(HERE))                        # eval_set, metrics

from shared.embedder import get_embedder

import ram_rag  # noqa: E402
import metrics as M  # noqa: E402
from eval_set import EVAL  # noqa: E402

RESULTS = HERE / "results.json"
RETRIEVE_N = 30  # fetch enough chunks that the top few unique papers are covered

# Qwen3-Embedding is instruction-tuned: queries (not documents) get a task prefix.
QWEN_INSTRUCT = (
    "Instruct: Given a question, retrieve the scientific paper passage "
    "that answers it\nQuery: "
)


def ranked_papers(embedder, question: str, n: int, table: str) -> list[str]:
    """Retrieve top-n chunks, collapse to a ranked list of unique papers."""
    q = QWEN_INSTRUCT + question if "qwen3" in embedder.name.lower() else question
    rows = ram_rag.retrieve(embedder, q, n, table)  # [(source, text, dist), ...]
    seen: set[str] = set()
    order: list[str] = []
    for src, _, _ in rows:
        if src not in seen:
            seen.add(src)
            order.append(src)
    return order


def run(model: str, k: int) -> None:
    embedder = get_embedder(model)
    table = ram_rag.table_name("ram", model)  # e.g. ram__minilm__fixed
    print(f"model: {embedder.name} ({embedder.dim}d) → table {table}")
    n_chunks = ram_rag.ingest(model, remove_citations=True, table=table)  # refs stripped
    print(f"ingested {n_chunks} chunks; scoring {len(EVAL)} labelled questions...")

    rankings = [(ranked_papers(embedder, q, RETRIEVE_N, table), gold) for q, gold in EVAL]
    res = M.aggregate(rankings, ks=(1, 3, k))
    res |= {"model": embedder.name, "dim": embedder.dim, "n_chunks": n_chunks}

    data = json.loads(RESULTS.read_text()) if RESULTS.exists() else {}
    data[embedder.name] = res
    RESULTS.write_text(json.dumps(data, indent=2))

    print("  " + "  ".join(f"{m}={v:.3f}" for m, v in res.items()
                           if isinstance(v, float)))
    print(f"✓ saved. Run more models, then: bakeoff.py report")


def report() -> None:
    if not RESULTS.exists():
        print("no results yet — run the bake-off first.")
        return
    data = json.loads(RESULTS.read_text())
    rows = sorted(data.values(), key=lambda r: -r.get("mrr", 0))
    mk = [k for k in rows[0] if k.startswith(("recall@", "ndcg@")) or k == "mrr"]
    print(f"\n{'model':<40}{'dim':>5}{'chunks':>8}" + "".join(f"{m:>10}" for m in mk))
    print("-" * (61 + 10 * len(mk)))
    for r in rows:
        name = r["model"][:38]
        print(f"{name:<40}{r['dim']:>5}{r['n_chunks']:>8}"
              + "".join(f"{r[m]:>10.3f}" for m in mk))
    print("\nHigher is better everywhere. recall@1 = right paper ranked first;")
    print("MRR rewards ranking it near the top; nDCG discounts lower ranks.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Lab 06 — embedder bake-off")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("run", help="score the model TEI is currently serving")
    pr.add_argument("--model", default="tei")
    pr.add_argument("--k", type=int, default=5)
    sub.add_parser("report", help="print the combined table")
    args = ap.parse_args()
    if args.cmd == "run":
        run(args.model, args.k)
    else:
        report()


if __name__ == "__main__":
    main()
