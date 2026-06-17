"""Step 12 — Unknown Issue Mode: case khác loại (null spike, missing partition).

Chứng minh engine tổng quát hoá: cùng pipeline xử lý nhiều loại lỗi, không hardcode quanh enum drift.
"""

import pytest

from data.seed_data.seed import (
    MISSING_TXN_DATE,
    PRIMARY_TXN_DATE,
    SECOND_NULL_RATE,
    SECOND_TXN_DATE,
    seed_database,
)
from database.connection import get_connection
from tools.freshness_check import freshness_check
from tools.null_check import null_check
from tools.volume_check import volume_check


@pytest.fixture()
def conn():
    c = get_connection(":memory:")
    seed_database(c)
    yield c
    c.close()


# ── tool-level ───────────────────────────────────────────────
def test_freshness_detects_missing_partition(conn):
    assert freshness_check(MISSING_TXN_DATE, "payment_txn", conn=conn)["loaded"] is False
    assert freshness_check(PRIMARY_TXN_DATE, "payment_txn", conn=conn)["loaded"] is True


def test_null_check_detects_spike(conn):
    res = null_check(SECOND_TXN_DATE, "payment_txn", "amount", conn=conn)
    assert res["spike"] is True
    assert res["null_rate"] == pytest.approx(SECOND_NULL_RATE, abs=1e-3)
    # ngày primary không có null spike
    assert null_check(PRIMARY_TXN_DATE, "payment_txn", "amount", conn=conn)["spike"] is False


def test_volume_drop(conn):
    assert volume_check(SECOND_TXN_DATE, "payment_txn", conn=conn)["drop"] is True
    assert volume_check(PRIMARY_TXN_DATE, "payment_txn", conn=conn)["drop"] is False


# ── graph-level: case khác loại đi qua cùng engine ──────────
def _run(request):
    from data.seed_data.seed import main as seed_main
    from graph.state import new_state
    from graph.workflow import build_workflow
    seed_main()
    return build_workflow().invoke(new_state(request))


def test_null_spike_case_routes_to_escalate_without_patch():
    final = _run("Revenue report 2026-06-08 nghi có vấn đề dữ liệu")
    nodes = [e["node"] for e in final["timeline"]]
    assert final["anomaly_type"] == "null_spike"
    assert final["confidence_route"] == "escalate"
    assert "escalate" in nodes
    assert "safe_patch_generator" not in nodes      # data quality → KHÔNG code patch
    assert "null" in (final["root_cause"] or "").lower()
    assert final["rca_report"]                        # có evidence pack


def test_missing_partition_case():
    final = _run("Revenue report 2026-06-09 không thấy số")
    assert final["anomaly_type"] == "missing_partition"
    assert final["confidence_route"] == "escalate"
    assert "safe_patch_generator" not in [e["node"] for e in final["timeline"]]


def test_enum_case_still_confident_and_patches():
    final = _run("Revenue report 2026-06-07 lệch 2.1%")
    assert final["anomaly_type"] == "enum_drift"
    assert final["confidence_route"] == "confident"
    assert "PARTIAL_REFUND" in final["patch"]["new_code"]


def test_unmatched_issue_creates_candidate_definition_without_promotion():
    from agents.root_cause_reasoner import reason

    out = reason({
        "user_request": "Revenue total dung nhung sai theo region ngay 2026-06-07",
        "date": "2026-06-07",
        "tool_results_summary": {
            "enum_drift": {"new_values": [], "has_drift": False},
            "code": {"missing_values": [], "files_searched": ["revenue_daily.sql"]},
            "lineage": {"upstream": ["stg_payment"], "downstream": ["finance_report"]},
            "quality_checks": {"volume": {"drop": False}},
        },
    })
    assert out["confidence_route"] == "escalate"
    assert out["anomaly_type"] == "unknown_issue"
    assert out["root_cause"] is None
    assert out["candidate_issue"]["candidate_issue_type"] == "dimension_allocation_drift"
    assert out["candidate_issue"]["requires_human_review"] is True
