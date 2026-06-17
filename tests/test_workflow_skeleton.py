"""Step 2 — kiểm tra graph skeleton chạy thông qua tất cả node và rẽ nhánh đúng."""

import pytest

from graph.state import new_state
from graph.workflow import build_workflow


@pytest.fixture(scope="module")
def app():
    return build_workflow()


def _nodes(final):
    return [e["node"] for e in final["timeline"]]


def test_happy_path_runs_full_sequence(app):
    state = new_state("Revenue 2026-06-07 lệch 2.1%")
    state["approval_status"] = "approved"   # mô phỏng human approve để chạy tới writeback
    final = app.invoke(state)
    nodes = _nodes(final)

    # đi qua đủ các node chính theo §5.1
    expected_order = [
        "state_init",
        "intent_risk_classifier",
        "memory_rag_retrieval",
        "known_unknown_router",
        "tool_governance",
        "diagnostic_tools",
        "root_cause_reasoner",
        "claim_verifier",
        "safe_patch_generator",
        "patch_reviewer",
        "validation_engine",
        "trust_scorer",
        "rca_report_generator",
        "test_docs_generator",
        "human_approval",
        "apply_remediation",
        "memory_writeback",
    ]
    assert nodes == expected_order
    assert final["approval_status"] != "rejected"
    assert final["memory_writeback_status"] == "written"


def test_state_initialized(app):
    # intent_risk_classifier nay là thật (Step 4): dùng request revenue để classify đúng
    final = app.invoke(new_state("Revenue report 2026-06-07 lệch 2.1%"))
    assert final["investigation_id"].startswith("INV-")
    assert final["intent"] == "investigate_revenue_mismatch"
    assert final["risk_level"] == "high"


def test_escalate_branch_skips_patch(app):
    # date không có data → diagnostics không thấy drift → confidence thấp → escalate (§11.4)
    from data.seed_data.seed import main as seed_main
    seed_main()
    final = app.invoke(new_state("Revenue 2099-01-01 lệch nhưng chưa rõ nguyên nhân"))
    nodes = _nodes(final)

    assert final["confidence_route"] == "escalate"
    assert "escalate" in nodes
    # nhánh escalate KHÔNG sinh patch / validation
    assert "safe_patch_generator" not in nodes
    assert "validation_engine" not in nodes
    assert final["approval_status"] == "needs_revision"


def test_rejected_approval_skips_writeback(app):
    from data.seed_data.seed import main as seed_main
    seed_main()
    state = new_state("Revenue 2026-06-07 lệch 2.1%")
    state["approval_status"] = "rejected"
    final = app.invoke(state)
    nodes = _nodes(final)

    assert "human_approval" in nodes
    assert "memory_writeback" not in nodes
