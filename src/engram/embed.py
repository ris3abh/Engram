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


class OpenAIEmbedder:
    """OpenAI embeddings (text-embedding-3-small by default), cached per text so a re-run only pays for new texts.

    The API returns unit-length vectors; rows are renormalized anyway so cosine stays a dot product.
    """

    PRICE_PER_TOKEN = {"text-embedding-3-small": 0.02 / 1_000_000, "text-embedding-3-large": 0.13 / 1_000_000}
    DIMS = {"text-embedding-3-small": 1536, "text-embedding-3-large": 3072}
    BATCH = 100

    def __init__(self, model: str = "text-embedding-3-small", cache=None):
        self.model = model
        self.cache = cache  # engram.cache.CallCache or None
        self._client = None
        self._lock = threading.Lock()

    def _key(self, text: str) -> str:
        from .cache import call_key

        return call_key("openai", "embed", self.model, text)

    def embed(self, texts: list[str]) -> np.ndarray:
        found: dict[int, list[float]] = {}
        if self.cache:
            for i, t in enumerate(texts):
                if hit := self.cache.get(self._key(t)):
                    found[i] = hit["vector"]
        missing = [i for i in range(len(texts)) if i not in found]
        for start in range(0, len(missing), self.BATCH):
            batch = missing[start : start + self.BATCH]
            with self._lock:
                if self._client is None:
                    import openai

                    self._client = openai.OpenAI(timeout=config.LLM_TIMEOUT_S, max_retries=config.LLM_ATTEMPTS - 1)
                response = self._client.embeddings.create(
                    model=self.model, input=[texts[i] for i in batch], encoding_format="float"
                )
            usd = response.usage.prompt_tokens * self.PRICE_PER_TOKEN.get(self.model, 0.0)
            for i, item in zip(batch, response.data, strict=True):
                found[i] = item.embedding
                if self.cache:
                    self.cache.put(self._key(texts[i]), {"vector": item.embedding})
            if self.cache:
                self.cache.spend("openai", usd)
        if not texts:
            return np.zeros((0, self.DIMS.get(self.model, 0)), dtype=np.float32)
        out = np.asarray([found[i] for i in range(len(texts))], dtype=np.float32)
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        return out / np.where(norms == 0, 1, norms)


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
    order = np.argsort(-scores, kind="stable")[:k]  # stable: ties keep the store's canonical order
    return [(ids[i], float(scores[i])) for i in order]
