"""Learning loop — agent học từ correction của người (kể cả khi miss/escalate) + áp runbook đã học."""

import pytest

import agents.diagnostic_planner as dp
from data.seed_data.seed import PRIMARY_TXN_DATE, seed_database
from database.connection import get_connection
from tools.memory_writeback import build_incident, write_incident


@pytest.fixture()
def conn():
    c = get_connection(":memory:")
    seed_database(c)
    yield c
    c.close()


# ── (2)+(3): ghi học từ correction, kể cả khi KHÔNG approved ──
def test_write_learns_from_human_correction_even_without_approval():
    state = {
        "date": "2026-06-08", "metric": "net_revenue",
        "root_cause": None,                       # agent MISS
        "tool_plan": ["freshness_check", "null_check"],
        "human_correction": {
            "root_cause": "Upstream ingestion lỗi làm amount null",
            "fix": "reload partition 2026-06-08",
            "anomaly_type": "late_arriving",
            "suggested_tools": ["freshness_check", "null_check"],
        },
    }
    res = write_incident(state, "needs_revision")    # CHƯA approve nhưng có correction
    assert res["status"] == "learned"
    inc = res["incident"]
    assert inc["root_cause"] == "Upstream ingestion lỗi làm amount null"   # lấy từ người, không phải agent
    assert inc["fix"] == "reload partition 2026-06-08"
    assert inc["anomaly_type"] == "late_arriving"
    assert inc["created_from"] == "human_correction"
    assert inc["runbook_tools"] == ["freshness_check", "null_check"]


def test_no_correction_no_approval_skips():
    res = write_incident({"date": "2026-06-08", "metric": "net_revenue"}, "rejected")
    assert res["status"] == "skipped"


def test_approved_without_correction_still_writes():
    state = {"date": PRIMARY_TXN_DATE, "metric": "net_revenue",
             "root_cause": "PARTIAL_REFUND chưa map", "tool_plan": ["sql_profile"]}
    res = write_incident(state, "approved")
    assert res["status"] == "written"
    assert res["incident"]["created_from"] == "human_approved_rca"


# ── (4): memory dẫn dắt plan — incident đã học có runbook → áp đúng bộ tool đó ──
def test_planner_applies_known_runbook(conn):
    state = {
        "date": PRIMARY_TXN_DATE, "metric": "net_revenue",
        "context_pack": {"known_runbook_tools": ["metadata_scan", "sql_profile", "code_search"]},
    }
    summary = dp.run(state, conn=conn)
    used = set(summary["tools_used"])
    assert {"metadata_scan", "sql_profile", "code_search", "enum_drift_check"} <= used
    # runbook KHÔNG gồm volume/null → không chạy (bằng chứng memory đổi hành vi thật)
    assert "volume_check" not in used
    assert "null_check" not in used


# ── tích hợp: agent miss (escalate) + người chỉ → workflow ghi vào memory ──
def test_workflow_learns_from_correction_on_escalate():
    from data.seed_data.seed import main as seed_main
    from graph.state import new_state
    from graph.workflow import build_workflow

    seed_main()
    state = new_state("Revenue 2026-06-08 nghi vấn dữ liệu")   # null spike → escalate
    state["human_correction"] = {"root_cause": "upstream load lỗi",
                                 "suggested_tools": ["freshness_check", "null_check"]}
    final = build_workflow().invoke(state)
    nodes = [e["node"] for e in final["timeline"]]

    assert final["confidence_route"] == "escalate"
    assert "escalate" in nodes
    assert "memory_writeback" in nodes               # escalate giờ vẫn tới được writeback
    assert final["memory_writeback_status"] == "learned"
