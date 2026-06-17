"""Step 10 — Validation Engine (reconciliation thật, deterministic pass/fail)."""

import pytest

from data.seed_data.seed import PRIMARY_TXN_DATE, seed_database
from database.connection import get_connection
from domain.contracts import get_contract
from tools.run_validation import run_validation

_CONTRACT = get_contract("net_revenue")


@pytest.fixture()
def conn():
    c = get_connection(":memory:")
    seed_database(c)
    yield c
    c.close()


def test_validation_passes_after_fix(conn):
    res = run_validation(PRIMARY_TXN_DATE, ["PARTIAL_REFUND"], _CONTRACT, conn=conn)
    assert res["validation_status"] == "PASS"
    assert res["passed"] == res["total"]


def test_reconciliation_before_worse_than_after(conn):
    res = run_validation(PRIMARY_TXN_DATE, ["PARTIAL_REFUND"], _CONTRACT, conn=conn)
    recon = res["reconciliation"]
    assert abs(recon["before_fix_diff"]) > abs(recon["after_fix_diff"])
    assert abs(recon["after_fix_diff"]) < 0.001        # sau fix gần như khớp


def test_reconciliation_fails_if_new_value_not_included(conn):
    # nếu fix KHÔNG include PARTIAL_REFUND → reconciliation vẫn lệch → FAIL
    res = run_validation(PRIMARY_TXN_DATE, [], _CONTRACT, conn=conn)
    recon = next(t for t in res["tests"] if t["name"] == "revenue_reconciliation_check")
    assert recon["status"] == "FAIL"


def test_individual_checks_present(conn):
    res = run_validation(PRIMARY_TXN_DATE, ["PARTIAL_REFUND"], _CONTRACT, conn=conn)
    names = {t["name"] for t in res["tests"]}
    assert {"schema_contract_check", "null_check", "duplicate_transaction_check",
            "accepted_values_check", "revenue_reconciliation_check"} <= names


def test_node_sets_validation_result_in_graph():
    from data.seed_data.seed import main as seed_main
    from graph.state import new_state
    from graph.workflow import build_workflow

    seed_main()
    final = build_workflow().invoke(new_state("Revenue 2026-06-07 lệch 2.1%"))
    vr = final.get("validation_result", {})
    assert vr.get("validation_status") == "PASS"
