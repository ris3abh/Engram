"""Embeddings for candidate retrieval only. Every decision about a candidate is Jev's."""

import hashlib
import os
import re
import threading
from typing import Protocol

import numpy as np

from . import config


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> np.ndarray:
        """(len(texts), dim) float32, L2-normalized rows."""
        ...


class SentenceEmbedder:
    """Local sentence-transformers model, loaded on first use."""

    def __init__(self, model_name: str = config.EMBED_MODEL):
        self.model_name = model_name
        self._model = None
        self._lock = threading.Lock()  # one load, and one encode at a time: torch is not re-entrant here

    def embed(self, texts: list[str]) -> np.ndarray:
        with self._lock:
            if self._model is None:
                os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.model_name, device=config.EMBED_DEVICE)
            vectors = self._model.encode(
                texts, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False
            )
        return np.asarray(vectors, dtype=np.float32)


class HashEmbedder:
    """Deterministic bag-of-words hashing. For tests and offline dev only."""

    def __init__(self, dim: int = 256):
        self.dim = dim

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for word in re.findall(r"[a-z0-9]+", text.lower()):
                out[row, int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dim] += 1.0
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        return out / np.where(norms == 0, 1, norms)


def top_k(query: np.ndarray, ids: list[str], matrix: np.ndarray, k: int) -> list[tuple[str, float]]:
    """The k ids most similar to `query` by cosine (rows are normalized, so a dot product)."""
    if not ids or k <= 0:
        return []
    scores = matrix @ query
    order = np.argsort(-scores)[:k]
    return [(ids[i], float(scores[i])) for i in order]
