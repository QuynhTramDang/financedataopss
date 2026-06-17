"""Hybrid retrieval — kết hợp lexical (token overlap) + vector (cosine embedding) qua RRF.

Best practice 2025: dense + sparse rồi reciprocal rank fusion → bắt cả khớp từ khoá lẫn ngữ nghĩa.
Lọc theo relevance floor (lex>0 hoặc cosine>ngưỡng) để không trả nhiễu. Reranker = seam tương lai.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from .embedder import Embedder, cosine, get_embedder, tokens

_RRF_K = 60
_VEC_FLOOR = 0.10


def hybrid_search(query: str, items: list[Any], text_of: Callable[[Any], str],
                  top_k: int = 3, embedder: Optional[Embedder] = None) -> list[dict[str, Any]]:
    """Trả top_k [{item, lex, vec, score}] theo điểm RRF (lexical + vector)."""
    emb = embedder or get_embedder()
    q_tokens = set(tokens(query))
    q_vec = emb.embed(query)

    scored: list[dict[str, Any]] = []
    for it in items:
        text = text_of(it)
        lex = len(q_tokens & set(tokens(text)))
        vec = cosine(q_vec, emb.embed(text))
        if lex > 0 or vec > _VEC_FLOOR:           # relevance floor → bỏ nhiễu
            scored.append({"item": it, "lex": lex, "vec": vec, "score": 0.0})

    # reciprocal rank fusion của 2 bảng xếp hạng
    by_lex = sorted(scored, key=lambda s: s["lex"], reverse=True)
    by_vec = sorted(scored, key=lambda s: s["vec"], reverse=True)
    for rank, s in enumerate(by_lex):
        s["score"] += 1.0 / (_RRF_K + rank + 1)
    for rank, s in enumerate(by_vec):
        s["score"] += 1.0 / (_RRF_K + rank + 1)

    scored.sort(key=lambda s: s["score"], reverse=True)
    return scored[:top_k]
