"""Hybrid retrieval (lexical + vector + RRF), embedder pluggable."""

from .embedder import HashingEmbedder, get_embedder, set_embedder
from .hybrid import hybrid_search

__all__ = ["hybrid_search", "get_embedder", "set_embedder", "HashingEmbedder"]
