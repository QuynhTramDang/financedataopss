"""Step 3 — memory + RAG retrieval + Runtime Context Pack."""

from agents.context_retriever import build_context
from graph.state import new_state
from tools.memory_search import memory_search
from tools.rag_retrieve import rag_retrieve


def test_memory_search_finds_metric_and_incident():
    hits = memory_search("net_revenue mismatch", top_k=5)
    types = {h["type"] for h in hits}
    assert "metric" in types
    assert "incident" in types
    # incident liên quan đúng là INC-2026-0520
    incident = next(h["record"] for h in hits if h["type"] == "incident")
    assert incident["incident_id"] == "INC-2026-0520"


def test_memory_search_topk_and_sorted():
    hits = memory_search("revenue refund_status", top_k=2)
    assert len(hits) <= 2
    scores = [h["score"] for h in hits]
    assert scores == sorted(scores, reverse=True)


def test_rag_retrieve_returns_relevant_chunk():
    chunks = rag_retrieve("net_revenue refund_status", top_k=3)
    assert chunks, "phải có ít nhất 1 chunk"
    joined = " ".join(c["text"] for c in chunks).lower()
    assert "refund_status" in joined


def test_build_context_pack_for_revenue_case():
    state = new_state("Revenue report 2026-06-07 lệch 2.1% so với payment dashboard")
    state["metric"] = "net_revenue"
    result = build_context(dict(state))
    pack = result["context_pack"]

    assert pack["metric_definition"] == "net_revenue = paid_amount - refunded_amount"
    assert "revenue_daily" in (pack["pipeline_lineage"] or "")
    assert pack["relevant_policy"] is not None
    assert pack["similar_incident"] and "INC-2026-0520" in pack["similar_incident"]
    # tìm thấy incident tương tự → known issue mode
    assert result["issue_mode"] == "known"
    assert len(result["retrieved_context"]) >= 4


def test_node_sets_context_in_state():
    from graph.workflow import build_workflow

    final = build_workflow().invoke(new_state("Revenue 2026-06-07 lệch 2.1%"))
    assert final.get("context_pack", {}).get("metric_definition")
    assert final.get("issue_mode") in {"known", "unknown"}
