"""B1 — kiểm chứng data nhiều ngày/scenario + pipeline 3 tầng stg → ods → dtm (tính từ SQL)."""

import pytest

from data.seed_data.seed import (
    AFFECTED_AMOUNT,
    CLEAN_TXN_DATE,
    DRIFT_TXN_DATE,
    DUP_TXN_DATE,
    FK_BREAK_TXN_DATE,
    LOWVOL_TXN_DATE,
    MISSING_TXN_DATE,
    NET_REVENUE_CORRECT,
    PRIMARY_TXN_DATE,
    seed_database,
)
from data.seed_data.scenarios import SCENARIOS
from database.connection import get_connection, run_query
from pipelines.run_pipeline import build_layers


@pytest.fixture()
def conn():
    c = get_connection(":memory:")
    seed_database(c)
    build_layers(c)
    yield c
    c.close()


def _scalar(conn, sql, params=None):
    return run_query(sql, params or {}, conn=conn)[0]


def test_layers_built(conn):
    for t in ("stg_payment", "stg_order", "ods_payment_enriched", "dtm_revenue_daily"):
        n = _scalar(conn, f"SELECT COUNT(*) AS c FROM {t}")["c"]
        assert n > 0, f"layer {t} rỗng"


def test_history_breadth(conn):
    days = _scalar(conn, "SELECT COUNT(DISTINCT txn_date) AS c FROM payment_txn")["c"]
    assert days >= 28  # ~30 ngày lịch sử + scenario


def test_dtm_overstates_on_enum_drift(conn):
    dtm = _scalar(conn, "SELECT net_revenue FROM dtm_revenue_daily WHERE txn_date = :d",
                  {"d": PRIMARY_TXN_DATE})["net_revenue"]
    base = _scalar(conn, "SELECT net_revenue_correct FROM revenue_baseline WHERE txn_date = :d",
                   {"d": PRIMARY_TXN_DATE})["net_revenue_correct"]
    assert base == NET_REVENUE_CORRECT
    assert dtm - base == AFFECTED_AMOUNT  # bug ods bỏ sót PARTIAL_REFUND → overstated đúng phần đó


def test_cross_layer_tie_out_on_clean_day(conn):
    g = _scalar(conn, "SELECT gross_revenue, net_revenue FROM dtm_revenue_daily WHERE txn_date = :d",
                {"d": CLEAN_TXN_DATE})
    stg_sum = _scalar(conn, "SELECT SUM(amount) AS s FROM stg_payment WHERE txn_date = :d",
                      {"d": CLEAN_TXN_DATE})["s"]
    base = _scalar(conn, "SELECT net_revenue_correct AS n FROM revenue_baseline WHERE txn_date = :d",
                   {"d": CLEAN_TXN_DATE})["n"]
    assert g["gross_revenue"] == stg_sum   # gross tie-out xuyên tầng
    assert g["net_revenue"] == base        # ngày sạch: net khớp baseline


def test_duplicate_double_counts(conn):
    dups = _scalar(conn,
                   "SELECT COUNT(*) AS c FROM (SELECT order_id FROM payment_txn "
                   "WHERE txn_date = :d GROUP BY order_id HAVING COUNT(*) > 1)",
                   {"d": DUP_TXN_DATE})["c"]
    assert dups == 50
    dtm = _scalar(conn, "SELECT net_revenue FROM dtm_revenue_daily WHERE txn_date = :d",
                  {"d": DUP_TXN_DATE})["net_revenue"]
    base = _scalar(conn, "SELECT net_revenue_correct FROM revenue_baseline WHERE txn_date = :d",
                   {"d": DUP_TXN_DATE})["net_revenue_correct"]
    assert dtm > base  # double count → dtm cao hơn số đúng (deduped)


def test_fk_break_produces_null_dimension(conn):
    orphans = _scalar(conn,
                      "SELECT COUNT(*) AS c FROM ods_payment_enriched "
                      "WHERE txn_date = :d AND order_id IS NOT NULL AND region IS NULL",
                      {"d": FK_BREAK_TXN_DATE})["c"]
    assert orphans == 40


def test_distribution_drift(conn):
    avg_drift = _scalar(conn, "SELECT AVG(amount) AS a FROM payment_txn WHERE txn_date = :d",
                        {"d": DRIFT_TXN_DATE})["a"]
    avg_clean = _scalar(conn, "SELECT AVG(amount) AS a FROM payment_txn WHERE txn_date = :d",
                        {"d": CLEAN_TXN_DATE})["a"]
    assert avg_drift > 3 * avg_clean


def test_volume_and_missing(conn):
    low = _scalar(conn, "SELECT COUNT(*) AS c FROM payment_txn WHERE txn_date = :d",
                  {"d": LOWVOL_TXN_DATE})["c"]
    missing = _scalar(conn, "SELECT COUNT(*) AS c FROM payment_txn WHERE txn_date = :d",
                      {"d": MISSING_TXN_DATE})["c"]
    assert low == 60
    assert missing == 0


def test_partial_refund_only_on_primary(conn):
    rows = run_query("SELECT DISTINCT txn_date FROM payment_txn WHERE refund_status = 'PARTIAL_REFUND'",
                     conn=conn)
    assert {r["txn_date"] for r in rows} == {PRIMARY_TXN_DATE}


def test_scenario_catalog_matches_data(conn):
    for s in SCENARIOS:
        n = _scalar(conn, "SELECT COUNT(*) AS c FROM payment_txn WHERE txn_date = :d",
                    {"d": s["date"]})["c"]
        if s["type"] == "missing_partition":
            assert n == 0, f"{s['date']} phải rỗng"
        else:
            assert n > 0, f"{s['date']} ({s['type']}) phải có data"
