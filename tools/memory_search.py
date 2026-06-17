"""memory_search — tìm structured memory liên quan (metric, pipeline, incident, decision, runbook).

Hybrid retrieval deterministic (không LLM): lexical (token overlap) + vector (cosine embedding) qua
RRF — xem retrieval/hybrid.py. Nguyên tắc §8: store nhiều, retrieve ít — chỉ trả top-k.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from retrieval.hybrid import hybrid_search

_MEM_DIR = Path(__file__).resolve().parents[1] / "memory"

_FILES = {
    "user": "user_memory.json",
    "metric": "metric_memory.json",
    "pipeline": "pipeline_memory.json",
    "incident": "incident_memory.json",
    "decision": "decision_policy_memory.json",
    "runbook": "approved_runbooks.json",
}


def _load(kind: str) -> list[dict]:
    data = json.loads((_MEM_DIR / _FILES[kind]).read_text(encoding="utf-8"))
    return data if isinstance(data, list) else [data]


def memory_search(query: str, kinds: Optional[list[str]] = None,
                  top_k: int = 3) -> list[dict[str, Any]]:
    """Trả list {type, score, record} đã sort theo điểm hybrid (RRF) giảm dần."""
    items = [(kind, rec) for kind in (kinds or list(_FILES.keys())) for rec in _load(kind)]
    hits = hybrid_search(
        query, items, text_of=lambda it: json.dumps(it[1], ensure_ascii=False), top_k=top_k)
    return [{"type": h["item"][0], "score": round(h["score"], 4), "record": h["item"][1]}
            for h in hits]
