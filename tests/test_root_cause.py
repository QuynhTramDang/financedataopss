"""Step 7 — Root Cause Reasoner + confidence gate."""

from agents.root_cause_reasoner import CONFIDENCE_THRESHOLD, reason


def _summary_strong():
    return {
        "enum_drift": {"new_values": ["PARTIAL_REFUND"], "has_drift": True},
        "code": {"missing_values": ["PARTIAL_REFUND"], "handled_values": ["REFUNDED"],
                 "repo_path": "pipelines/models/finance/revenue_daily.sql"},
        "affected_amount": 210_000_000,
    }


class FakeRouter:
    def call_structured(self, route, prompt, schema, system=None, **kw):
        return {"root_cause": "PARTIAL_REFUND chưa được map trong revenue_daily"}


def test_strong_evidence_is_confident_with_root_cause():
    out = reason({"tool_results_summary": _summary_strong()}, router=FakeRouter())
    assert out["confidence"] >= CONFIDENCE_THRESHOLD
    assert out["confidence_route"] == "confident"
    assert out["root_cause"] and "PARTIAL_REFUND" in out["root_cause"]


def test_no_evidence_escalates_without_conclusion():
    out = reason({"tool_results_summary": {"enum_drift": {"new_values": [], "has_drift": False},
                                           "code": {"missing_values": []}, "affected_amount": 0}})
    assert out["confidence_route"] == "escalate"
    assert out["root_cause"] is None        # không kết luận khi thiếu evidence


def test_partial_evidence_below_threshold_escalates():
    # chỉ có drift, code không thiếu (đã handle) → confidence thấp
    out = reason({"tool_results_summary": {
        "enum_drift": {"new_values": ["X"], "has_drift": True},
        "code": {"missing_values": []}, "affected_amount": 0}})
    assert out["confidence_route"] == "escalate"


def test_graph_reaches_patch_on_strong_case():
    from data.seed_data.seed import main as seed_main
    from graph.state import new_state
    from graph.workflow import build_workflow

    seed_main()
    final = build_workflow().invoke(new_state("Revenue 2026-06-07 lệch 2.1%"))
    nodes = [e["node"] for e in final["timeline"]]
    assert final["confidence_route"] == "confident"
    assert "safe_patch_generator" in nodes   # confident → đi tới patch
    assert final["root_cause"]
