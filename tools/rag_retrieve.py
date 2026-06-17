"""rag_retrieve — lấy chunk tài liệu ngữ cảnh nghiệp vụ (metric dict, runbook, contract, ...).

Chunk theo heading `## ` trong file markdown; chấm điểm keyword overlap; trả top-k chunk.
RAG ở đây trả lời "data này nghĩa là gì / từng quyết định ra sao" (§10), KHÔNG đọc raw data.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from retrieval.hybrid import hybrid_search

_RAG_DIR = Path(__file__).resolve().parents[1] / "rag_docs"


def _chunks() -> list[dict[str, str]]:
    """Tách mỗi file md thành các chunk theo heading '## '."""
    out: list[dict[str, str]] = []
    for path in sorted(_RAG_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        parts = re.split(r"\n(?=## )", text)
        for part in parts:
            part = part.strip()
            if part:
                out.append({"source": path.name, "text": part})
    return out


def rag_retrieve(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    """Trả list {source, text, score} sort theo điểm hybrid (RRF) giảm dần."""
    hits = hybrid_search(query, _chunks(), text_of=lambda c: c["text"], top_k=top_k)
    return [{"source": h["item"]["source"], "text": h["item"]["text"],
             "score": round(h["score"], 4)} for h in hits]
