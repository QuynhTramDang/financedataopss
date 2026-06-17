"""Step 1 — kiểm chứng dữ liệu seed cho mismatch ≈ 2.1% (tính từ SQL, không hardcode)."""

import pytest

from data.seed_data.seed import (
    AFFECTED_AMOUNT,
    EXPECTED_MISMATCH,
    NET_REVENUE_CORRECT,
    PRIMARY_TXN_DATE,
    seed_database,
)
from database.connection import get_connection, read_pipeline_sql, run_query


@pytest.fixture()
def conn():
    c = get_connection(":memory:")
    seed_database(c)
    yield c
    c.close()


def test_partial_refund_present_in_profile(conn):
    profile = run_query(
        "SELECT refund_status, COUNT(*) AS cnt, SUM(refunded_amount) AS refunded "
        "FROM payment_txn WHERE txn_date = :d GROUP BY refund_status",
        {"d": PRIMARY_TXN_DATE}, conn=conn,
    )
    by_status = {r["refund_status"]: r for r in profile}
    assert "PARTIAL_REFUND" in by_status, "PARTIAL_REFUND phải xuất hiện trong source"
    assert by_status["PARTIAL_REFUND"]["refunded"] == AFFECTED_AMOUNT


def test_buggy_pipeline_overstates_by_partial_refund(conn):
    # net_revenue theo pipeline (BUG: bỏ sót PARTIAL_REFUND)
    buggy = run_query(read_pipeline_sql(), {"txn_date": PRIMARY_TXN_DATE}, conn=conn)
    buggy_net = buggy[0]["net_revenue"]

    # net_revenue ĐÚNG (trừ cả PARTIAL_REFUND)
    correct = run_query(
        "SELECT SUM(amount) - SUM(CASE WHEN refund_status IN ('REFUNDED','PARTIAL_REFUND') "
        "THEN refunded_amount ELSE 0 END) AS net "
        "FROM payment_txn WHERE txn_date = :d",
        {"d": PRIMARY_TXN_DATE}, conn=conn,
    )
    correct_net = correct[0]["net"]

    assert correct_net == NET_REVENUE_CORRECT
    assert buggy_net - correct_net == AFFECTED_AMOUNT  # overstated đúng phần PARTIAL_REFUND


def test_reconciliation_mismatch_is_about_2_1_percent(conn):
    buggy = run_query(read_pipeline_sql(), {"txn_date": PRIMARY_TXN_DATE}, conn=conn)[0]["net_revenue"]
    baseline = run_query(
        "SELECT net_revenue_correct FROM revenue_baseline WHERE txn_date = :d",
        {"d": PRIMARY_TXN_DATE}, conn=conn,
    )[0]["net_revenue_correct"]

    mismatch = (buggy - baseline) / baseline
    assert mismatch == pytest.approx(EXPECTED_MISMATCH, abs=1e-4)
