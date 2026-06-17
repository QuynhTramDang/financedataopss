"""M3 — inbound trigger: Airflow fail → tự mở investigation (metric-aware, dedup, fail-loud)."""

import pytest

from data.seed_data.seed import main as seed_main
from monitoring.triggers import _metric_for_dag, handle_airflow_failure, reset_dedup


def setup_function():
    reset_dedup()


def test_metric_resolved_from_pipeline_memory():
    assert _metric_for_dag("revenue_daily") == "net_revenue"
    assert _metric_for_dag("dtm_revenue_daily") == "net_revenue"


def test_unknown_dag_fails_loud():
    with pytest.raises(ValueError):
        handle_airflow_failure("khong_co_dag_nay", "2026-06-07")


def test_airflow_failure_opens_investigation():
    seed_main()
    res = handle_airflow_failure("revenue_daily", "2026-06-07", task_id="ods_payment_enriched")
    assert res["status"] == "opened"
    assert res["metric"] == "net_revenue"
    assert res["anomaly_type"] == "enum_drift"        # cùng engine điều tra
    assert res["investigation_id"].startswith("INV-AF-")


def test_dedup_skips_duplicate_failure_event():
    seed_main()
    first = handle_airflow_failure("revenue_daily", "2026-06-08")
    second = handle_airflow_failure("revenue_daily", "2026-06-08")
    assert first["status"] == "opened"
    assert second["status"] == "deduped"              # không mở investigation thứ 2 cho cùng fail
