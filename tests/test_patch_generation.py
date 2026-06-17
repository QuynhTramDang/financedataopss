"""Step 9 — Impact simulation + Patch Generator + Patch Reviewer."""

import pytest

from agents.patch_reviewer import review_patch
from data.seed_data.seed import AFFECTED_AMOUNT, NET_REVENUE_CORRECT, PRIMARY_TXN_DATE, seed_database
from database.connection import get_connection
from domain.contracts import get_contract
from tools.generate_patch import generate_patch
from tools.impact_simulation import simulate_impact

_CONTRACT = get_contract("net_revenue")


@pytest.fixture()
def conn():
    c = get_connection(":memory:")
    seed_database(c)
    yield c
    c.close()


def _summary():
    return {
        "enum_drift": {"new_values": ["PARTIAL_REFUND"]},
        "code": {
            "missing_values": ["PARTIAL_REFUND"],
            "handled_values": ["REFUNDED"],
            "repo_path": "pipelines/models/finance/revenue_daily.sql",
            "snippet": "CASE WHEN refund_status = 'REFUNDED' THEN refunded_amount ELSE 0 END",
        },
        "affected_amount": AFFECTED_AMOUNT,
    }


def test_impact_simulation_before_after_from_sql(conn):
    impact = simulate_impact(PRIMARY_TXN_DATE, ["PARTIAL_REFUND"], _CONTRACT, conn=conn)
    assert impact["baseline"] == NET_REVENUE_CORRECT
    assert impact["affected_amount"] == AFFECTED_AMOUNT
    # trước fix lệch ~2.1%, sau fix ~0%
    assert impact["before_fix_diff"] == pytest.approx(0.021, abs=1e-4)
    assert abs(impact["after_fix_diff"]) < 1e-6


def test_generate_patch_includes_partial_refund_minimal_change():
    patch = generate_patch(_summary())
    assert patch["change_type"] == "replace_block"
    assert patch["requires_approval"] is True
    assert "PARTIAL_REFUND" in patch["new_code"]
    assert "REFUNDED" in patch["new_code"]
    assert "in (" in patch["new_code"].lower()        # đổi '=' thành 'in (...)'
    assert patch["old_code"] != patch["new_code"]


def test_patch_reviewer_flags_high_risk_and_approval():
    review = review_patch(generate_patch(_summary()))
    assert review["business_risk"] == "high"
    assert review["requires_approval"] is True
    assert any("reconciliation" in t for t in review["suggested_tests"])


def test_node_sets_patch_and_impact_in_graph():
    from data.seed_data.seed import main as seed_main
    from graph.state import new_state
    from graph.workflow import build_workflow

    seed_main()
    final = build_workflow().invoke(new_state("Revenue 2026-06-07 lệch 2.1%"))
    assert final["patch"]["requires_approval"] is True
    assert "PARTIAL_REFUND" in final["patch"]["new_code"]
    assert final["impact_analysis"]["affected_amount"] == AFFECTED_AMOUNT
