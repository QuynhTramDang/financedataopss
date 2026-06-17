"""Step 11 — Approval flow + Memory write-back gating (§8.3, FR-015, FR-016)."""

import json
import os

import pytest

from tools.approval_state import apply_decision, can_apply
from tools.memory_writeback import build_incident, write_incident


def _state():
    return {
        "investigation_id": "INV-TEST",
        "date": "2026-06-07",
        "metric": "net_revenue",
        "root_cause": "PARTIAL_REFUND chưa map",
        "patch": {"new_code": "refund_status in ('REFUNDED', 'PARTIAL_REFUND')"},
        "tool_plan": ["sql_profile", "code_search"],
        "tool_results_summary": {"enum_drift": {"new_values": ["PARTIAL_REFUND"]}},
    }


# ── approval_state ───────────────────────────────────────────
def test_apply_decision_mapping():
    assert apply_decision("approve") == "approved"
    assert apply_decision("reject") == "rejected"
    assert apply_decision("request_revision") == "needs_revision"
    with pytest.raises(ValueError):
        apply_decision("xyz")


def test_can_apply_only_when_approved():
    assert can_apply("approved") is True
    assert can_apply("pending") is False


# ── memory write-back gating ─────────────────────────────────
def test_writeback_skipped_when_not_approved(tmp_path, monkeypatch):
    monkeypatch.setenv("DATAOPS_INCIDENT_MEMORY", str(tmp_path / "inc.json"))
    res = write_incident(_state(), "pending")
    assert res["status"] == "skipped"
    assert not (tmp_path / "inc.json").exists()   # không ghi gì


def test_writeback_writes_when_approved(tmp_path, monkeypatch):
    path = tmp_path / "inc.json"
    monkeypatch.setenv("DATAOPS_INCIDENT_MEMORY", str(path))
    res = write_incident(_state(), "approved")
    assert res["status"] == "written"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert any(r["incident_id"] == "INC-2026-06-07-net_revenue" for r in data)
    rec = data[0]
    assert rec["created_from"] == "human_approved_rca"
    assert rec["root_cause"]


def test_writeback_idempotent_upsert(tmp_path, monkeypatch):
    path = tmp_path / "inc.json"
    monkeypatch.setenv("DATAOPS_INCIDENT_MEMORY", str(path))
    write_incident(_state(), "approved")
    write_incident(_state(), "approved")
    data = json.loads(path.read_text(encoding="utf-8"))
    ids = [r["incident_id"] for r in data]
    assert ids.count("INC-2026-06-07-net_revenue") == 1   # không nhân đôi


def test_build_incident_structure():
    inc = build_incident(_state())
    assert inc["created_from"] == "human_approved_rca"
    assert inc["metric"] == "net_revenue"
    assert "diagnostic_steps" in inc


# ── graph integration ────────────────────────────────────────
def test_graph_pending_does_not_write():
    from graph.state import new_state
    from graph.workflow import build_workflow

    final = build_workflow().invoke(new_state("Revenue 2026-06-07 lệch 2.1%"))
    # mặc định pending → không ghi memory (không auto-deploy)
    assert final.get("memory_writeback_status") in ("not_started",)


def test_graph_approved_writes(monkeypatch, tmp_path):
    from data.seed_data.seed import main as seed_main
    from graph.state import new_state
    from graph.workflow import build_workflow

    monkeypatch.setenv("DATAOPS_INCIDENT_MEMORY", str(tmp_path / "inc.json"))
    seed_main()
    state = new_state("Revenue 2026-06-07 lệch 2.1%")
    state["approval_status"] = "approved"
    final = build_workflow().invoke(state)
    assert final["memory_writeback_status"] == "written"
