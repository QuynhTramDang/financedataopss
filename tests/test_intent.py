"""Step 4 — Intent & Risk Classifier (model nhỏ + rule override + heuristic fallback)."""

import pytest

from agents.intent_classifier import classify
from model_router.providers import ProviderUnavailable


class FakeRouter:
    """Giả lập router.call_structured trả về JSON cố định."""

    def __init__(self, payload=None, raise_exc=None):
        self._payload = payload
        self._raise = raise_exc

    def call_structured(self, route, prompt, schema, system=None, **kw):
        if self._raise:
            raise self._raise
        return dict(self._payload)


def test_finance_metric_forces_high_risk_even_if_llm_says_low():
    fake = FakeRouter({"intent": "investigate_revenue_mismatch",
                       "metric": "net_revenue", "date": "2026-06-07", "risk_level": "low"})
    out = classify("Revenue report 2026-06-07 lệch 2.1%", router=fake)
    assert out["risk_level"] == "high"        # rule override
    assert out["metric"] == "net_revenue"
    assert out["date"] == "2026-06-07"


def test_enrichment_fills_missing_date_and_metric():
    # LLM bỏ sót metric/date → regex/keyword trích lại
    fake = FakeRouter({"intent": "investigate_revenue_mismatch",
                       "metric": None, "date": None, "risk_level": "medium"})
    out = classify("Revenue report ngày 2026-06-07 đang lệch", router=fake)
    assert out["date"] == "2026-06-07"
    assert out["metric"] == "net_revenue"
    assert out["risk_level"] == "high"


def test_heuristic_fallback_when_no_model():
    fake = FakeRouter(raise_exc=ProviderUnavailable("no model"))
    out = classify("Revenue 2026-06-07 lệch 2.1%", router=fake)
    assert out["intent"] == "investigate_revenue_mismatch"
    assert out["risk_level"] == "high"        # finance keyword → high
    assert out["_fallback"].startswith("heuristic")


def test_non_finance_request_not_forced_high():
    fake = FakeRouter(raise_exc=ProviderUnavailable("no model"))
    out = classify("Job log_cleanup failed hôm nay", router=fake)
    assert out["risk_level"] != "high"        # không phải finance → không override


def test_node_runs_offline_in_graph():
    """Graph chạy offline (không key) vẫn classify được nhờ heuristic fallback."""
    from graph.state import new_state
    from graph.workflow import build_workflow

    final = build_workflow().invoke(new_state("Revenue 2026-06-07 lệch 2.1%"))
    assert final["intent"] == "investigate_revenue_mismatch"
    assert final["risk_level"] == "high"
    assert final["metric"] == "net_revenue"
