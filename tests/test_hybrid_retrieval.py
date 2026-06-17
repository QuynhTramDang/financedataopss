"""Vector/hybrid memory — lexical + vector (cosine) + RRF, embedder pluggable (offline)."""

import math

from retrieval.embedder import HashingEmbedder, cosine
from retrieval.hybrid import hybrid_search


def test_embedder_deterministic_and_normalized():
    e = HashingEmbedder(dim=64)
    v1, v2 = e.embed("net revenue mismatch"), e.embed("net revenue mismatch")
    assert v1 == v2                                   # deterministic
    assert abs(math.sqrt(sum(x * x for x in v1)) - 1.0) < 1e-9   # L2-normalized


def test_cosine_identical_vs_disjoint():
    e = HashingEmbedder()
    a = e.embed("revenue refund partial")
    assert cosine(a, e.embed("revenue refund partial")) > 0.99
    assert cosine(a, e.embed("zzz qqq www kkk")) < 0.2


def test_hybrid_ranks_relevant_and_filters_noise():
    docs = [{"t": "net_revenue overstated by partial refund"},
            {"t": "weather forecast tomorrow sunny"},
            {"t": "refund mapping in revenue pipeline"}]
    hits = hybrid_search("revenue refund", docs, text_of=lambda d: d["t"], top_k=3)
    texts = [h["item"]["t"] for h in hits]
    assert any("refund" in t for t in texts)
    assert all("weather" not in t for t in texts)     # nhiễu bị relevance floor lọc


def test_memory_search_hybrid_still_finds_incident():
    from tools.memory_search import memory_search
    hits = memory_search("Revenue 2026-06-07 net_revenue mismatch", ["incident"], top_k=1)
    assert hits and hits[0]["record"]["incident_id"] == "INC-2026-0520"


def test_rag_retrieve_hybrid_returns_relevant():
    from tools.rag_retrieve import rag_retrieve
    hits = rag_retrieve("net_revenue definition refund", top_k=3)
    assert hits and all("text" in h and "score" in h for h in hits)
