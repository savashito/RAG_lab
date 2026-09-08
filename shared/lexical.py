"""
shared/lexical.py — recuperación léxica (BM25) y fusión de rankings (RRF).

BM25 hecho a mano para que la fórmula del curso quede visible, más Reciprocal Rank
Fusion para combinar el ranking léxico con el denso. Es la misma lógica que
`04_hybrid_retrieval/hybrid.py`, extraída aquí para que los notebooks la importen sin
arrastrar la dependencia de Postgres de aquel lab.

    idf * tf*(k1+1) / (tf + k1*(1 - b + b*dl/avgdl))
"""

from __future__ import annotations

import math
import re


def tokenize(text: str) -> list[str]:
    # \w conserva guiones bajos/dígitos, así "art_5" o "139 Ter" quedan tokenizables.
    return re.findall(r"[a-záéíóúñü0-9_]+", text.lower())


class BM25:
    """Okapi BM25. `corpus_tokens` es la lista de documentos ya tokenizados."""

    def __init__(self, corpus_tokens: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs = corpus_tokens
        self.N = len(corpus_tokens)
        self.avgdl = sum(len(d) for d in corpus_tokens) / max(self.N, 1)
        df: dict[str, int] = {}
        for d in corpus_tokens:
            for t in set(d):
                df[t] = df.get(t, 0) + 1
        self.idf = {t: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for t, n in df.items()}
        self.tf = [{t: d.count(t) for t in set(d)} for d in corpus_tokens]

    def scores(self, query_tokens: list[str]) -> list[float]:
        out = []
        for i, d in enumerate(self.docs):
            dl = len(d)
            s = 0.0
            for t in query_tokens:
                f = self.tf[i].get(t, 0)
                if not f:
                    continue
                s += self.idf.get(t, 0.0) * (f * (self.k1 + 1)) / (
                    f + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                )
            out.append(s)
        return out


def rank_indices_by_score(scores: list[float]) -> list[int]:
    """Índices de documentos ordenados de mayor a menor score."""
    return sorted(range(len(scores)), key=lambda i: -scores[i])


def rrf(ranked_lists: list[list[int]], k: int = 60) -> list[int]:
    """Reciprocal Rank Fusion: suma 1/(k + rank) sobre listas de índices. Ignora las
    escalas de score, así que combina denso y léxico sin normalizarlos."""
    agg: dict[int, float] = {}
    for rl in ranked_lists:
        for rank, idx in enumerate(rl):
            agg[idx] = agg.get(idx, 0.0) + 1.0 / (k + rank + 1)
    return sorted(agg, key=lambda i: -agg[i])
