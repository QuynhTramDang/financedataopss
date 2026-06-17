"""context_retriever — gộp memory + RAG thành Runtime Context Pack (§9).

Nguyên tắc: store nhiều, retrieve ít. Chỉ đưa phần đủ để reasoning vào pack (top-k mỗi loại),
không nhét toàn bộ memory/docs. Quyết định known vs unknown dựa trên có incident tương tự hay không.
"""

from __future__ import annotations

from typing import Any, Optional

from tools.memory_search import memory_search
from tools.rag_retrieve import rag_retrieve


def _first(hits: list[dict]) -> Optional[dict]:
    return hits[0]["record"] if hits else None


def _lineage(pipeline_rec: Optional[dict]) -> Optional[str]:
    if not pipeline_rec:
        return None
    up = " + ".join(pipeline_rec.get("upstream", []))
    down = " + ".join(pipeline_rec.get("downstream", []))
    return f"{up} -> {pipeline_rec.get('pipeline')} -> {down}"


def build_context(state: dict) -> dict[str, Any]:
    """Trả {context_pack, issue_mode, retrieved_context} cho node memory_rag_retrieval."""
    metric = state.get("metric") or ""
    query = f"{state.get('user_request', '')} {metric}".strip()

    metric_rec = _first(memory_search(query, ["metric"], 1))
    pipeline_rec = _first(memory_search(query, ["pipeline"], 1))
    incident_hits = memory_search(query, ["incident"], 1)
    incident_rec = _first(incident_hits)
    policy_rec = _first(memory_search(query, ["decision"], 1))
    runbook_rec = _first(memory_search(query, ["runbook"], 1))
    rag_chunks = rag_retrieve(query, top_k=3)

    context_pack = {
        "task": state.get("intent") or "investigate",
        "metric_definition": (
            f"{metric_rec['metric']} = {metric_rec['definition']}" if metric_rec else None
        ),
        "pipeline_lineage": _lineage(pipeline_rec),
        "relevant_policy": policy_rec.get("approval_rule") if policy_rec else None,
        "similar_incident": (
            f"{incident_rec['incident_id']}: {incident_rec['issue']}" if incident_rec else None
        ),
        # runbook đã học từ incident tương tự (tool nên chạy) → planner áp lại để xử nhanh/đúng hơn
        "known_runbook_tools": incident_rec.get("runbook_tools") if incident_rec else None,
        "runbook": runbook_rec.get("steps") if runbook_rec else None,
        "rag_snippets": [{"source": c["source"], "text": c["text"]} for c in rag_chunks],
    }

    # known nếu tìm thấy incident tương tự (đủ điểm); ngược lại Unknown Issue Mode (§11)
    issue_mode = "known" if incident_hits else "unknown"

    retrieved_context = [
        {"type": "metric", "value": context_pack["metric_definition"]},
        {"type": "pipeline_lineage", "value": context_pack["pipeline_lineage"]},
        {"type": "policy", "value": context_pack["relevant_policy"]},
        {"type": "incident", "value": context_pack["similar_incident"]},
        {"type": "runbook", "value": context_pack["runbook"]},
    ]
    retrieved_context = [r for r in retrieved_context if r["value"]]

    return {
        "context_pack": context_pack,
        "issue_mode": issue_mode,
        "retrieved_context": retrieved_context,
    }
