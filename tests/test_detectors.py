"""Detector registry — anomaly mới (duplicate, distribution_drift) phát hiện được + remediation đúng."""

import pytest

from agents.detectors import DETECTORS, classify


# ── unit: detector registry ──────────────────────────────────
def test_duplicate_detected():
    s = {"quality_checks": {"duplicate": {"has_duplicate": True, "dup_groups": 50,
                                          "dup_rows": 50, "key_col": "order_id"}}}
    h = classify(s, "2026-06-11")
    assert h["anomaly_type"] == "duplicate"
    assert h["route"] == "escalate"


def test_distribution_drift_detected():
    s = {"quality_checks": {"distribution": {"drift": True, "ratio": 5.0,
                                            "avg_today": 5e7, "baseline_avg": 1e7}}}
    h = classify(s, "2026-06-13")
    assert h["anomaly_type"] == "distribution_drift"


def test_enum_has_priority_over_duplicate():
    s = {"enum_drift": {"new_values": ["X"]}, "code": {"missing_values": ["X"]},
         "quality_checks": {"duplicate": {"has_duplicate": True}}}
    assert classify(s, "d")["anomaly_type"] == "enum_drift"   # ưu tiên fixable


def test_no_signal_low_confidence_escalate():
    h = classify({"quality_checks": {}}, "d")
    assert h["anomaly_type"] is None and h["route"] == "escalate"


def test_registry_is_extensible():
    assert len(DETECTORS) >= 6   # thêm anomaly = thêm hàm, không sửa lõi


# ── graph: data đã seed (06-11 duplicate, 06-13 distribution) đi qua engine ──
def _run(request):
    from data.seed_data.seed import main as seed_main
    from graph.state import new_state
    from graph.workflow import build_workflow
    seed_main()
    return build_workflow().invoke(new_state(request))


def test_graph_detects_duplicate_and_proposes_dedup():
    final = _run("Revenue 2026-06-11 nghi bị tính trùng số")
    assert final["anomaly_type"] == "duplicate"
    assert final["confidence_route"] == "escalate"
    assert "safe_patch_generator" not in [e["node"] for e in final["timeline"]]
    assert final["remediation"]["kind"] == "code_patch"          # dedup proposal
    assert final["remediation"]["strategy"] == "dedup_by_business_key"


def test_graph_detects_distribution_drift():
    final = _run("Revenue 2026-06-13 số liệu bất thường")
    assert final["anomaly_type"] == "distribution_drift"
    assert final["remediation"]["kind"] == "operational"
    assert final["remediation"]["strategy"] == "recompute_or_investigate_source"
