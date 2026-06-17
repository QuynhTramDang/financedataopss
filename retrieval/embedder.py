"""Embedder pluggable cho hybrid retrieval.

Mặc định HashingEmbedder (bag-of-words hashed + tf, L2-normalize) — DETERMINISTIC, không phụ thuộc
model/đường mạng → offline/CI chạy được. Seam get_embedder() để cắm embedding THẬT (sentence-
transformers hoặc API) khi cần semantic mạnh hơn — chỉ đổi 1 chỗ, không sửa caller.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _bucket(token: str, dim: int) -> int:
    return int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16) % dim


class Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


class HashingEmbedder:
    """BoW hashed embedder: tf theo bucket hash ổn định (md5) + L2 normalize. Deterministic."""

    def __init__(self, dim: int = 256):
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for tok in tokens(text):
            vec[_bucket(tok, self.dim)] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))   # vector đã L2-normalize


_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    """Trả embedder dùng chung. Mặc định HashingEmbedder (offline).

    Để dùng embedding THẬT: cài sentence-transformers / cấu hình API rồi thay tại đây
    (vd đọc env EMBEDDINGS_MODEL). Caller không cần đổi.
    """
    global _embedder
    if _embedder is None:
        _embedder = HashingEmbedder()
    return _embedder


def set_embedder(embedder: Embedder) -> None:
    global _embedder
    _embedder = embedder
