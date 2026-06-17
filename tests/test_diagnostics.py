"""Step 6 — diagnostic tools thật (sql_profile qua governance, enum_drift, code_search, lineage)."""

import pytest

from agents import diagnostic_planner
from data.seed_data.seed import AFFECTED_AMOUNT, PRIMARY_TXN_DATE, seed_database
from database.connection import get_connection
from tools.code_search import code_search
from tools.enum_drift_check import enum_drift_check
from tools.lineage_lookup import lineage_lookup
from tools.metadata_scan import metadata_scan
from tools.sql_profile import sql_profile


@pytest.fixture()
def conn():
    c = get_connection(":memory:")
    seed_database(c)
    yield c
    c.close()


def test_sql_profile_goes_through_governance_and_finds_partial_refund(conn):
    res = sql_profile(PRIMARY_TXN_DATE, table="payment_txn", group_col="refund_status",
                      measure_column="amount", deduction_column="refunded_amount", conn=conn)
    assert res["governance"]["decision"] == "allowed"   # aggregate có partition filter
    profile = res["profile"]
    assert "PARTIAL_REFUND" in profile
    assert profile["PARTIAL_REFUND"]["deduction"] == AFFECTED_AMOUNT


def test_metadata_baseline_excludes_partial_refund():
    meta = metadata_scan("payment_txn")
    assert meta["found"]
    assert "PARTIAL_REFUND" not in meta["known_values"]["refund_status"]


def test_enum_drift_detects_new_value():
    drift = enum_drift_check(["NONE", "REFUNDED", "PARTIAL_REFUND"], ["NONE", "REFUNDED"])
    assert drift["has_drift"]
    assert drift["new_values"] == ["PARTIAL_REFUND"]


def test_code_search_finds_mapping_and_handled_values():
    res = code_search("refund_status", repo_paths=["pipelines/models/finance/revenue_daily.sql"])
    assert res["matches"], "phải tìm thấy dòng refund_status trong revenue_daily.sql"
    assert "REFUNDED" in res["handled_values"]
    assert "PARTIAL_REFUND" not in res["handled_values"]   # pipeline chưa handle


def test_lineage_lookup():
    # revenue_daily (legacy flat model) đọc thẳng payment_txn
    lin = lineage_lookup("revenue_daily")
    assert lin["found"]
    assert "payment_txn" in lin["upstream"]
    assert "finance_revenue_report" in lin["downstream"]

    # pipeline 3 tầng mới: ods_payment_enriched ← stg_payment/stg_order, → dtm_revenue_daily
    ods = lineage_lookup("ods_payment_enriched")
    assert ods["found"]
    assert "stg_payment" in ods["upstream"]
    assert "dtm_revenue_daily" in ods["downstream"]


def test_diagnostic_planner_full_summary(conn):
    summary = diagnostic_planner.run({"date": PRIMARY_TXN_DATE, "metric": "net_revenue"}, conn=conn)
    assert summary["sql_governance"] == "allowed"
    assert summary["enum_drift"]["new_values"] == ["PARTIAL_REFUND"]
    assert summary["affected_amount"] == AFFECTED_AMOUNT
    assert summary["code"]["missing_values"] == ["PARTIAL_REFUND"]
    assert summary["scope"]["table"] == "payment_txn"
    assert summary["plan_steps"]
    assert summary["evidence"]
    assert {item["source_tool"] for item in summary["evidence"]} >= {
        "metadata_scan", "sql_profile", "enum_drift_check", "code_search"
    }
    # đảm bảo không lọt raw row — chỉ có aggregate theo nhóm
    assert set(summary["group_profile"].keys()) <= {"NONE", "REFUNDED", "PARTIAL_REFUND"}


def test_tool_registry_exposes_governed_local_tools():
    from orchestration import get_registry

    registry = get_registry()
    sql_tool = registry.get("sql_profile")
    assert sql_tool.capability == "data_profile"
    assert sql_tool.source == "local"
    assert sql_tool.governance["decision"] == "allowed"


def test_node_runs_diagnostics_in_graph():
    """Graph chạy diagnostics thật trên DB đã seed."""
    from data.seed_data.seed import main as seed_main
    from graph.state import new_state
    from graph.workflow import build_workflow

    seed_main()  # đảm bảo db file đã seed
    final = build_workflow().invoke(new_state("Revenue 2026-06-07 lệch 2.1%"))
    summary = final.get("tool_results_summary", {})
    assert "PARTIAL_REFUND" in summary.get("enum_drift", {}).get("new_values", [])
    assert summary["affected_amount"] == AFFECTED_AMOUNT
