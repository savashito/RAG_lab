"""Clean OCR'd CAG markdown for RAG ingestion.

Fixes, per file:
  * removes Docling `<!-- image -->` placeholders
  * de-hyphenates words split across line breaks  (natu-\\nraleza -> naturaleza)
  * rejoins words wrongly split by a space         (natu raleza  -> naturaleza)
  * collapses runs of blank lines and trailing whitespace

Word rejoining is accent-insensitive (OCR drops Spanish accents) and only
merges when the joined form is a real Spanish word AND at least one fragment
is NOT — so real word pairs like "de la" or "entidad soberana" are left alone.

Usage:
    python ingestion/clean_cag.py            # clean the two body PDFs (skips the index)

Input : ingestion/markdown/CAG/<name>.md
Output: ingestion/markdown/CAG_clean/<name>.md
"""

import re
import unicodedata
from pathlib import Path

from wordfreq import get_frequency_dict

BASE = Path(__file__).resolve().parent
SRC_DIR = BASE / "markdown" / "CAG"
OUT_DIR = BASE / "markdown" / "CAG_clean"

# Index is navigation, not content -> excluded from the RAG corpus.
FILES = ["Primera parte CAG.md", "Segunda parte CAG.md"]

WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)  # letters only (incl. accents/ñ)


def deaccent(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s.lower())
        if unicodedata.category(c) != "Mn"
    )


print("building Spanish vocabulary ...")
_fd = get_frequency_dict("es")
VALID = {deaccent(w) for w, f in _fd.items() if f >= 1e-7 and w.isalpha()}


def is_word(tok: str) -> bool:
    return deaccent(tok) in VALID


def should_merge(a: str, b: str) -> bool:
    """True if a+b is a real word and at least one fragment is not."""
    if not (WORD_RE.fullmatch(a) and WORD_RE.fullmatch(b)):
        return False
    if len(a) < 2 or len(b) < 2:  # keep prepositions/articles intact
        return False
    return is_word(a + b) and not (is_word(a) and is_word(b))


def rejoin_spaces(line: str, stats: dict) -> str:
    """Single left-to-right pass: merge adjacent tokens split by one space."""
    tokens = line.split(" ")
    out: list[str] = []
    i = 0
    while i < len(tokens):
        cur = tokens[i]
        if i + 1 < len(tokens) and should_merge(cur, tokens[i + 1]):
            out.append(cur + tokens[i + 1])
            stats["space_merges"] += 1
            i += 2
        else:
            out.append(cur)
            i += 1
    return " ".join(out)


def dehyphenate(text: str, stats: dict) -> str:
    def repl(m: re.Match) -> str:
        a, b = m.group(1), m.group(2)
        stats["hyphen_joins"] += 1
        return a + b if should_merge(a, b) else f"{a}-{b}"
    # word, hyphen, end of line, optional spaces, word
    return re.sub(r"([^\W\d_]+)-\n[ \t]*([^\W\d_]+)", repl, text)


def clean_text(text: str, stats: dict) -> str:
    # drop image placeholders
    before = text.count("<!-- image -->")
    text = re.sub(r"[ \t]*<!-- image -->[ \t]*\n?", "", text)
    stats["images_removed"] += before

    text = dehyphenate(text, stats)

    lines = [rejoin_spaces(ln.rstrip(), stats) for ln in text.split("\n")]
    text = "\n".join(lines)

    text = re.sub(r"\n{3,}", "\n\n", text)  # collapse blank runs
    return text.strip() + "\n"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        src = SRC_DIR / name
        if not src.exists():
            print(f"SKIP (not found): {src}")
            continue
        stats = {"images_removed": 0, "hyphen_joins": 0, "space_merges": 0}
        raw = src.read_text(encoding="utf-8")
        cleaned = clean_text(raw, stats)
        out = OUT_DIR / name
        out.write_text(cleaned, encoding="utf-8")
        print(
            f"{name}: images-removed={stats['images_removed']} "
            f"hyphen-joins={stats['hyphen_joins']} "
            f"space-merges={stats['space_merges']} "
            f"| {len(raw):,} -> {len(cleaned):,} chars -> {out}"
        )


if __name__ == "__main__":
    main()
