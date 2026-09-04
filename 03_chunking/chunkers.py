"""
03_chunking/chunkers.py — the chunking strategies we compare.

Each function takes a document's text and returns a list of chunk strings.
The whole point of the lab is that *where you cut* changes what can be retrieved.
Real systems use spaCy/nltk for sentence splitting; we keep a naive splitter so
the mechanics stay visible.
"""

from __future__ import annotations

import re

import numpy as np

# What if no whitespace? just \n?
def _sentences(text: str) -> list[str]:
    """Naive sentence splitter: break after . ! ? followed by whitespace."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


# ── 1. Fixed-size (the Lab 01 baseline) ─────────────────────────────────────────
def fixed(text: str, size: int = 40, overlap: int = 10) -> list[str]:
    """`size` words per chunk, sliding by (size - overlap). Ignores meaning."""
    words = text.split()
    step = max(1, size - overlap)
    chunks: list[str] = []
    for start in range(0, len(words), step):
        piece = words[start : start + size]
        if piece:
            chunks.append(" ".join(piece))
        if start + size >= len(words):
            break
    return chunks


def _group(sents: list[str], per_chunk: int, overlap: int) -> list[str]:
    """Pack a list of sentences into chunks of `per_chunk`, sliding by overlap."""
    step = max(1, per_chunk - overlap)
    chunks: list[str] = []
    for start in range(0, len(sents), step):
        grp = sents[start : start + per_chunk]
        if grp:
            chunks.append(" ".join(grp))
        if start + per_chunk >= len(sents):
            break
    return chunks


# ── 2. Sentence, naive splitter (N sentences per chunk) ─────────────────────────
def sentence(text: str, per_chunk: int = 2, overlap: int = 0) -> list[str]:
    """Group whole sentences so a chunk never cuts mid-sentence."""
    return _group(_sentences(text), per_chunk, overlap)


# ── 2b. Sentence, PROPER segmenter (pysbd) — the real-pipeline upgrade ──────────
_SEG = None


def _sentences_pysbd(text: str) -> list[str]:
    """
    Proper sentence segmentation via pysbd. Unlike the naive regex, it does NOT
    break on 'Dr.', 'U.S.', 'e.g.', or decimals like 3.5 — the abbreviation/number
    cases that quietly corrupt naive chunking. (spaCy / nltk do the same job;
    pysbd is pure-Python and needs no model download.)
    """
    global _SEG
    import pysbd
    if _SEG is None:
        _SEG = pysbd.Segmenter(language="en", clean=False)
    return [s.strip() for s in _SEG.segment(text) if s.strip()]


def sentence_pysbd(text: str, per_chunk: int = 2, overlap: int = 0) -> list[str]:
    return _group(_sentences_pysbd(text), per_chunk, overlap)


# ── 3. Recursive (respect boundaries, pack up to ~size words) ────────────────────
def recursive(text: str, size: int = 40) -> list[str]:
    """
    Greedily pack whole sentences up to ~size words. If one sentence alone is
    longer than size, fall back to word-splitting just that sentence. This keeps
    natural boundaries while still bounding chunk length — the idea behind
    LangChain's RecursiveCharacterTextSplitter.
    """
    chunks: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for sentence in _sentences(text):
        s_len = len(sentence.split())
        if s_len > size:
            if cur:
                chunks.append(" ".join(cur))
                cur, cur_len = [], 0
            chunks.extend(fixed(sentence, size=size, overlap=0))
            continue
        if cur and cur_len + s_len > size:
            chunks.append(" ".join(cur))
            cur, cur_len = [], 0
        cur.append(sentence)
        cur_len += s_len
    if cur:
        chunks.append(" ".join(cur))
    return chunks


# ── 4. Semantic (cut where the topic shifts) ────────────────────────────────────
def semantic(text: str, embedder, threshold: float = 0.5) -> list[str]:
    """
    Embed each sentence; start a new chunk when consecutive sentences become
    dissimilar (cosine similarity < threshold). Groups sentences that are 'about
    the same thing' into one vector. Uses the same (swappable) embedder as the
    rest of the pipeline, so `--model tei` accelerates this too.
    """
    sents = _sentences(text)
    if len(sents) <= 1:
        return sents
    embs = embedder.encode(sents)  # L2-normalised, so dot == cosine similarity
    chunks: list[str] = []
    cur = [sents[0]]
    for i in range(1, len(sents)):
        sim = float(np.dot(embs[i], embs[i - 1]))
        if sim < threshold:
            chunks.append(" ".join(cur))
            cur = [sents[i]]
        else:
            cur.append(sents[i])
    chunks.append(" ".join(cur))
    return chunks


# ── 5. By-article (structure-aware, for legal codes) ────────────────────────────
# Start of an article at the beginning of a line, tolerating the Markdown markup
# (#, *, _, >, <u>) left over from the PDF → Markdown conversion.
_ARTICLE_START = re.compile(r"(?m)^[\s#*_>]*(?:<u>)?\**Art[íi]culo\s+\d+\s*[oº]?", re.I)


def article_spans(text: str) -> list[str]:
    """El texto de cada artículo (de un 'Artículo N' al siguiente), para analizar
    su tamaño. Excluye el preámbulo anterior al primer artículo; lista vacía si el
    documento no tiene marcas de artículo."""
    starts = [m.start() for m in _ARTICLE_START.finditer(text)]
    bounds = starts + [len(text)]
    return [text[bounds[i] : bounds[i + 1]] for i in range(len(starts))]


def by_article(text: str, max_words: int = 250, overlap: int = 25) -> list[str]:
    """
    Cut on 'Artículo N' boundaries so each chunk is ONE article — the unit people
    actually ask a legal code about — instead of a blind word window that slices
    an article in half. Articles longer than `max_words` are sub-split with
    `fixed`; prose with no article markers (e.g. a doctrinal book) falls back to a
    single `fixed` pass over the whole text, so it's safe on any document.
    """
    starts = [m.start() for m in _ARTICLE_START.finditer(text)]
    if not starts:
        return fixed(text, size=max_words, overlap=overlap)
    bounds = starts + [len(text)]
    blocks = ([text[: starts[0]]] if starts[0] > 0 else [])  # preamble before art. 1
    blocks += [text[bounds[i] : bounds[i + 1]] for i in range(len(starts))]
    chunks: list[str] = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        if len(block.split()) <= max_words:
            chunks.append(block)
        else:
            chunks.extend(fixed(block, size=max_words, overlap=overlap))
    return chunks
