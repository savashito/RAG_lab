"""
04_hybrid_retrieval/queries.py — labelled queries in two flavours.

Each item is (query, target_doc, group):
  * "exact"    — the query contains a rare exact token (error code, part number,
                 product name). Lexical BM25 should nail these; dense search
                 often confuses documents with near-identical prose.
  * "semantic" — a paraphrase that shares almost no words with the target doc.
                 Dense search should win; BM25 has little to match on.

The target is the filename of the one correct document.
"""

QUERIES: list[tuple[str, str, str]] = [
    # ── exact-token queries ──────────────────────────────────────────────
    ("What does fault ERR_4521 indicate?",            "err_4521.md",  "exact"),
    ("Steps to resolve ERR_7788?",                    "err_7788.md",  "exact"),
    ("Torque spec for the M8x40 bolt?",               "boltm8.md",    "exact"),
    ("QX-9 battery life on a single charge?",         "qx9.md",       "exact"),
    # ── semantic / paraphrase queries ────────────────────────────────────
    ("Which device can be dunked underwater without breaking?", "zephyr3.md",   "semantic"),
    ("Who invented the standard way to calibrate field instruments?", "halvorsen.md", "semantic"),
    ("Is the interface quick to react to a tap?",     "latency.md",   "semantic"),
    ("Will switching hardware lower our electricity spending?", "savings.md",  "semantic"),
]
