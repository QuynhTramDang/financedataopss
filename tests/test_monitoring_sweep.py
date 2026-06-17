"""Step 16 — Proactive Monitoring (sweep + alert + auto-open)."""

import pytest

from data.seed_data.seed import seed_database
from database.connection import get_connection
from monitoring.alert import format_alert
from monitoring.sweep import DEFAULT_WATCH, sweep


@pytest.fixture()
def conn():
    c = get_connection(":memory:")
    seed_database(c)
    yield c
    c.close()


def test_sweep_detects_anomalies_not_clean_date(conn):
    alerts = sweep("net_revenue", DEFAULT_WATCH, conn=conn)
    by_date = {a["date"]: a for a in alerts}
    # 3 ngày lỗi có alert, ngày sạch 2026-06-10 KHÔNG có
    assert by_date["2026-06-07"]["anomaly_type"] == "enum_drift"
    assert by_date["2026-06-08"]["anomaly_type"] == "null_spike"
    assert by_date["2026-06-09"]["anomaly_type"] == "missing_partition"
    assert "2026-06-10" not in by_date


def test_enum_alert_caught_before_finance(conn):
    alert = next(a for a in sweep("net_revenue", ["2026-06-07"], conn=conn))
    assert alert["detected_before_finance"] is True
    assert alert["severity"] == "high"
    assert alert["recommended_action"] == "open_investigation_and_propose_patch"
    assert alert["tier"] == "L2_assisted"
    assert alert["affected_amount"] == 210_000_000


def test_data_quality_alert_uses_l3_safe_action(conn):
    alert = next(a for a in sweep("net_revenue", ["2026-06-08"], conn=conn))   # null spike
    assert alert["tier"] == "L3_safe_autonomous"
    assert alert["recommended_action"] == "notify_owner"


def test_suppress_known_benign(conn):
    alerts = sweep("net_revenue", ["2026-06-07"], conn=conn, suppress=["2026-06-07"])
    assert alerts == []


def test_format_alert_text(conn):
    alert = next(a for a in sweep("net_revenue", ["2026-06-07"], conn=conn))
    msg = format_alert(alert)
    assert "DQ Alert" in msg and "enum_drift" in msg


def test_auto_open_investigation_produces_root_cause():
    from data.seed_data.seed import main as seed_main
    from monitoring.scheduler import auto_open_investigation

    seed_main()
    final = auto_open_investigation("2026-06-07")
    assert final["anomaly_type"] == "enum_drift"
    assert "PARTIAL_REFUND" in final["patch"]["new_code"]
