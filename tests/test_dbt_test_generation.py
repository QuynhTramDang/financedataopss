"""Step 11A — dbt test + docs generation (fail-then-pass)."""

import pytest

from data.seed_data.seed import PRIMARY_TXN_DATE, seed_database
from database.connection import get_connection
from domain.contracts import get_contract
from tools.generate_dbt_test import generate_dbt_test
from tools.generate_docs import generate_docs

_CONTRACT = get_contract("net_revenue")


@pytest.fixture()
def conn():
    c = get_connection(":memory:")
    seed_database(c)
    yield c
    c.close()


def _summary():
    return {"enum_drift": {"new_values": ["PARTIAL_REFUND"]},
            "code": {"missing_values": ["PARTIAL_REFUND"]}}


def test_dbt_test_includes_partial_refund_accepted_value(conn):
    res = generate_dbt_test(_summary(), _CONTRACT, PRIMARY_TXN_DATE, conn=conn)
    assert "PARTIAL_REFUND" in res["accepted_values"]
    assert "accepted_values" in res["yaml"]
    assert "revenue_reconciliation" in res["yaml"]


def test_generated_test_catches_the_bug(conn):
    # test phải FAIL trên logic cũ và PASS sau patch
    res = generate_dbt_test(_summary(), _CONTRACT, PRIMARY_TXN_DATE, conn=conn)
    v = res["verification"]
    assert v["before_fix_status"] == "FAIL"
    assert v["after_fix_status"] == "PASS"
    assert v["catches_bug"] is True


def test_generate_docs_proposes_update():
    docs = generate_docs({"tool_results_summary": _summary(), "metric": "net_revenue",
                          "date": "2026-06-07", "investigation_id": "INV-1",
                          "patch": {"new_code": "in ('REFUNDED','PARTIAL_REFUND')"}})
    assert docs["suggested_path"].startswith("proposed/")
    assert "PARTIAL_REFUND" in docs["markdown"]


def test_node_generates_artifacts_in_graph():
    from data.seed_data.seed import main as seed_main
    from graph.state import new_state
    from graph.workflow import build_workflow

    seed_main()
    final = build_workflow().invoke(new_state("Revenue 2026-06-07 lệch 2.1%"))
    assert final["dbt_test"]["verification"]["catches_bug"] is True
    assert "PARTIAL_REFUND" in final["dbt_test"]["accepted_values"]
    assert final["docs_update"]["markdown"]
