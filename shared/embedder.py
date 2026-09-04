"""
shared/embedder.py — the swappable "text → vector" component.

The whole point of these labs is to experiment, so embedding is a PLUGGABLE
piece. Every lab gets its embedder from `get_embedder(name)`; to try a different
local model you change one string (or pass --model on the CLI) and re-ingest.

Starting model: all-MiniLM-L6-v2 (384 dims) — small, fast, CPU-friendly, the
classic baseline. Later labs will benchmark alternatives and, eventually, a
remote embedding service. The interface below stays the same for all of them.
"""

from __future__ import annotations

import json
import os
import urllib.request

import numpy as np

# ── Download guard (data-plan / disk safety) ────────────────────────────────────
# A LOCAL embedder (sentence-transformers) downloads model weights to THIS machine
# — hundreds of MB, easy to trigger by accident on a metered connection. Prefer
# `--model tei`, which embeds on the GPU server (downloads happen there, not here).
# Local downloads are blocked unless you explicitly opt in with RAG_ALLOW_DOWNLOAD=1.
if os.environ.get("RAG_ALLOW_DOWNLOAD") != "1":
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


class Embedder:
    """Minimal interface every embedder implements."""

    name: str  # human/model identifier, stored alongside vectors
    dim: int   # vector length — must match the pgvector column

    def encode(self, texts: list[str]) -> np.ndarray:
        """Return an (len(texts), dim) float32 array of L2-normalised vectors."""
        raise NotImplementedError


class SentenceTransformerEmbedder(Embedder):
    def __init__(self, model_name: str) -> None:
        # imported lazily so labs that don't embed don't pay the torch import
        from sentence_transformers import SentenceTransformer

        self.name = model_name
        try:
            self._model = SentenceTransformer(model_name)
        except Exception as e:  # usually: not cached + offline guard active
            raise RuntimeError(
                f"Local model '{model_name}' isn't cached and downloads are blocked "
                f"(RAG_ALLOW_DOWNLOAD != 1). Use `--model tei` to embed on the GPU "
                f"server (nothing downloads to this machine), or set "
                f"RAG_ALLOW_DOWNLOAD=1 to permit a one-time local download."
            ) from e
        # method was renamed in sentence-transformers 6.0; support both
        get_dim = getattr(
            self._model, "get_embedding_dimension", None
        ) or self._model.get_sentence_embedding_dimension
        self.dim = get_dim()

    def encode(self, texts: list[str]) -> np.ndarray:
        # normalize_embeddings=True → vectors are unit length, so cosine
        # distance (pgvector's <=>) behaves cleanly and is comparable across rows.
        return self._model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ).astype(np.float32)


class RemoteTEIEmbedder(Embedder):
    """
    Calls a Hugging Face Text Embeddings Inference (TEI) server running on the
    GPU box (rtx5090)

    Same interface as the local embedder, so it's a drop-in: labs pick it with
    `--model tei`. TEI serves the *same* all-MiniLM-L6-v2 with L2 normalisation,
    so vectors are compatible with anything embedded locally with `minilm`.

    Reads the endpoint from TEI_URL in .env (default http://localhost:8085,
    which is the SSH tunnel to rtx5090). TEI caps a request at
    max_client_batch_size items, so encode() chunks accordingly.
    """

    def __init__(self, url: str | None = None) -> None:
        self.url = (url or os.environ.get("TEI_URL", "http://localhost:8085")).rstrip("/")
        info = json.load(urllib.request.urlopen(self.url + "/info", timeout=10))
        self.name = "tei:" + info["model_id"]
        self._batch = int(info.get("max_client_batch_size") or 32)
        self.dim = len(self._post(["probe"])[0])  # one call to learn the dimension

    def _post(self, batch: list[str]) -> list[list[float]]:
        body = json.dumps({"inputs": batch, "normalize": True, "truncate": True}).encode()
        req = urllib.request.Request(
            self.url + "/embed", data=body, headers={"Content-Type": "application/json"}
        )
        return json.load(urllib.request.urlopen(req, timeout=60))

    def encode(self, texts: list[str]) -> np.ndarray:
        out: list[list[float]] = []
        for i in range(0, len(texts), self._batch):
            out.extend(self._post(list(texts[i : i + self._batch])))
        return np.asarray(out, dtype=np.float32)


# Short aliases so labs/CLI can say "minilm" instead of the full HF path.
# Add more here as you explore — that's the experiment.
ALIASES = {
    "minilm": "sentence-transformers/all-MiniLM-L6-v2",   # 384d, 256 tok — default
    "mpnet": "sentence-transformers/all-mpnet-base-v2",   # 768d — stronger, slower
    "bge-small": "BAAI/bge-small-en-v1.5",                # 384d — strong small model
    "bge-base": "BAAI/bge-base-en-v1.5",                  # 768d, 512 tok — stronger retrieval
}


def get_embedder(name: str = "rtx") -> Embedder:
    """
    Resolve a name to a ready Embedder.
      * "tei"  → the remote GPU service (rtx5090) via TEI_URL
      * alias  → a local sentence-transformers model (minilm/mpnet/bge-small)
      * raw HF id → that model, locally
    """
    if name in ("tei", "remote", "gpu", "rtx"):
        return RemoteTEIEmbedder()
    return SentenceTransformerEmbedder(ALIASES.get(name, name))
