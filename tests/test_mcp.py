"""M0 — MCP boundary: gateway allow-list + audit + executor branch + governance (read-only)."""

import pytest

from orchestration.executor import execute_plan
from orchestration.mcp_gateway import FakeTransport, MCPGateway, MCPToolRef, get_gateway
from orchestration.registry import get_registry


def _step(sid, tool, inputs=None):
    return {"id": sid, "tool": tool, "capability": "x", "reason": "t",
            "inputs": inputs or {}, "depends_on": [], "expected_evidence": "x"}


# ── gateway: default-deny + audit ────────────────────────────
def test_gateway_denies_unlisted_tool():
    gw = MCPGateway({"a": MCPToolRef("a", "srv", "toolA")}, FakeTransport())
    with pytest.raises(PermissionError):
        gw.call("not_listed", {})


def test_gateway_calls_transport_and_audits():
    gw = MCPGateway(
        {"airflow_dag_status": MCPToolRef("airflow_dag_status", "airflow", "get_dag_run_status")},
        FakeTransport({"get_dag_run_status": {"state": "failed", "dag_id": "revenue_daily"}}),
    )
    res = gw.call("airflow_dag_status", {"dag_id": "revenue_daily"})
    assert res["state"] == "failed"
    audit = gw.audit_log()
    assert audit[0]["tool"] == "airflow_dag_status"
    assert audit[0]["status"] == "ok"
    assert audit[0]["server"] == "airflow"


# ── registry + governance: MCP read-only tool được duyệt L1 ──
def test_registry_exposes_governed_mcp_tools():
    reg = get_registry()
    rec = reg.get("airflow_dag_status")
    assert rec.source == "mcp"
    assert rec.mcp_server == "airflow"
    assert rec.governance["decision"] == "allowed"      # read-only → L1
    assert reg.list(source="mcp")                        # có ít nhất 1 MCP tool


def test_default_gateway_allowlists_registry_mcp_tools():
    gw = get_gateway()
    assert gw.is_allowed("airflow_dag_status")
    assert gw.is_allowed("gitlab_pipeline_status")
    assert not gw.is_allowed("some_random_tool")


# ── executor: chạy MCP tool qua gateway, evidence chuẩn hoá ──
def test_executor_runs_mcp_tool_via_gateway():
    gw = MCPGateway(
        {"airflow_dag_status": MCPToolRef("airflow_dag_status", "airflow", "get_dag_run_status")},
        FakeTransport({"get_dag_run_status": {"state": "failed"}}),
    )
    ev = execute_plan([_step("s1", "airflow_dag_status", {"dag_id": "x"})], gateway=gw)
    assert ev[0]["status"] == "collected"
    assert ev[0]["source"] == "mcp"
    assert ev[0]["data"]["state"] == "failed"
    assert gw.audit_log()[0]["tool"] == "airflow_dag_status"
