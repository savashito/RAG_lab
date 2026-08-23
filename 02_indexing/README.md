# Lab 02 — Indexing & Scale

Lab 01 searched by **brute force**: every query compared against every stored
vector. Exact, but the cost grows linearly with your corpus — unusable at
millions of vectors. This lab adds an **Approximate Nearest Neighbour (ANN)**
index (**HNSW**) and *measures* the tradeoff it makes.

## Run it

Terminal 1: `./tunnel.sh`

Terminal 2:
```bash
# generate 5000 real embeddings, store, build the HNSW index
uv run python 02_indexing/bench.py build --n 5000

# benchmark exact vs HNSW across ef_search values, on held-out queries
uv run python 02_indexing/bench.py run --queries 100 --k 10
```

Real output from a 5000-vector run (yours will differ slightly):

```
method         ef_search   recall@10  ms/query  total_ms
--------------------------------------------------------
flat (exact)          -        1.000     2.399     239.9
hnsw                 10        0.963     0.520      52.0
hnsw                 20        0.988     0.630      63.0
hnsw                 40        1.000     0.647      64.7   ← sweet spot
hnsw                100        1.000     0.953      95.3
hnsw                200        1.000     2.115     211.5   ← over-tuned: as slow as flat
```

## How to read it

- **recall@10** = of the 10 truly-nearest chunks (from exact search), how many
  did the fast index find? `1.000` = identical to exact.
- **ms/query** = server-side execution time (`EXPLAIN ANALYZE`) divided by the
  number of queries — *not* wall-clock, so it reflects the index, not the tunnel.
- The knob **`ef_search`** slides you along the curve: higher = more of the graph
  explored = higher recall but slower. It's tunable *per query, at runtime* — no
  reindexing. That's HNSW's superpower.

**Two lessons from the table above:**
1. `ef_search = 40` already recovers **100% recall at ~4× the speed** of flat.
   You rarely need exact search.
2. `ef_search = 200` is **as slow as the flat scan for zero extra recall** —
   over-tuning burns time for nothing. Find the knee of the curve and stop.

At only 5000 vectors the flat scan is already fast (~2 ms), so the win looks
modest. **Re-run with `build --n 50000` (or 200000)** and watch the flat time
climb roughly linearly while HNSW barely moves — that's the whole reason indexes
exist.

## HNSW in one paragraph

HNSW = *Hierarchical Navigable Small World*. It builds a multi-layer graph where
each vector links to a few near neighbours. A search enters at the top (sparse,
long hops), greedily walks toward the query, and descends layer by layer to
refine — like zooming in on a map. It never looks at most vectors, which is why
it's sub-linear. Because it's greedy, it can miss the true nearest (hence
*approximate*), and `ef_search` controls how thoroughly it looks.

## The three knobs

| Knob | When | Effect |
|------|------|--------|
| `m` | build | edges per node. Higher = better recall + bigger index + slower build. 16 is a good default. |
| `ef_construction` | build | how hard it works to place each node. Higher = better graph, slower build. 64–200 typical. |
| `ef_search` | **query** | how thoroughly each search explores. Higher = better recall, slower query. Tune live. |

> **Build the index *after* bulk-loading** (as `build` does). Maintaining the
> graph on every INSERT is far slower than one build over the full table. For
> big builds, raise `maintenance_work_mem` so the graph fits in memory.

## HNSW vs IVFFlat (the other pgvector index)

pgvector offers a second index, **IVFFlat**, which clusters vectors into lists
and only scans the nearest lists. It builds faster and uses less memory, but
needs the data present *before* building (to learn clusters) and generally gives
worse recall/speed than HNSW. **Default to HNSW** unless build time or memory is
tight. (Both are approximate; a plain table with no index is your only *exact*
option.)

## A subtle correctness note

We generate **held-out** query sentences (a different random seed) so a query is
never identical to a stored vector — otherwise recall would be trivially perfect.
And we compute ground truth by disabling index scans
(`SET enable_indexscan = off`), forcing Postgres to do an exact full scan.

## Concepts introduced

| Term | Meaning |
|------|---------|
| **ANN** | Approximate nearest neighbour — trade a little accuracy for big speed. |
| **HNSW** | Graph-based ANN index; the pgvector default. |
| **recall@k** | Fraction of the true top-k that the index actually returned. |
| **ef_search** | Query-time recall/speed knob. |
| **IVFFlat** | Cluster-based ANN index; faster build, usually lower quality than HNSW. |

Next: **Lab 03 — Chunking**, where we stop taking chunk boundaries for granted
and measure how much they move retrieval quality (remember the hybrid-retrieval
chunk that ranked #2 in Lab 01?).
