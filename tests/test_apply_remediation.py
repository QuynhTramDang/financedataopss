"""M2 — apply_remediation: thực thi remediation qua MCP SAU approval (write tool, governed)."""

import pytest

from graph.nodes import apply_remediation


def test_code_patch_remediation_creates_mr_via_mcp():
    state = {
        "investigation_id": "INV-y", "metric": "net_revenue", "date": "2026-06-07",
        "patch": {"new_code": "in ('REFUNDED','PARTIAL_REFUND')"},
        "rca_report": "RCA: PARTIAL_REFUND chưa map.",
        "remediation": {"kind": "code_patch", "strategy": "expand_mapping", "details": {}},
    }
    out = apply_remediation(state)
    dr = out["dispatch_result"]
    assert any(a["tool"] == "gitlab_create_mr" and a["status"] == "collected" for a in dr["actions"])
    assert dr["teams"]["status"] == "skipped"   # không có TEAMS_WEBHOOK_URL → no-op


def test_operational_remediation_triggers_backfill_via_mcp():
    state = {
        "investigation_id": "INV-x", "metric": "net_revenue", "date": "2026-06-09",
        "remediation": {"kind": "operational", "strategy": "backfill_partition",
                        "details": {"action": "backfill", "partition": "2026-06-09",
                                    "pipeline": "revenue_daily"}},
    }
    out = apply_remediation(state)
    dr = out["dispatch_result"]
    assert any(a["tool"] == "airflow_trigger_dag" and a["status"] == "collected" for a in dr["actions"])


def test_no_actionable_remediation_dispatches_nothing():
    # reingest = proposal vận hành, chưa auto-execute → không dispatch MCP write
    state = {"investigation_id": "INV-z", "remediation": {"kind": "operational",
             "strategy": "reingest_source", "details": {"action": "reingest"}}}
    out = apply_remediation(state)
    assert out["dispatch_result"]["actions"] == []


def test_write_mcp_tools_governed():
    from orchestration.registry import get_registry
    reg = get_registry()
    assert reg.get("gitlab_create_mr").governance["decision"] == "allowed"      # L2, không bị block
    assert reg.get("airflow_trigger_dag").governance["decision"] == "allowed"
    # gitlab_create_mr là L2 → requires_approval True (governance đánh dấu)
    assert reg.get("gitlab_create_mr").governance["requires_approval"] is True


def test_graph_happy_path_dispatches_after_approval():
    from data.seed_data.seed import main as seed_main
    from graph.state import new_state
    from graph.workflow import build_workflow

    seed_main()
    state = new_state("Revenue 2026-06-07 lệch 2.1%")
    state["approval_status"] = "approved"
    final = build_workflow().invoke(state)
    nodes = [e["node"] for e in final["timeline"]]
    assert "apply_remediation" in nodes
    dr = final["dispatch_result"]
    assert any(a["tool"] == "gitlab_create_mr" for a in dr["actions"])   # enum → code_patch → MR
    assert final["memory_writeback_status"] == "written"
