"""Fix-strategy registry — mỗi anomaly có chiến lược khắc phục riêng (code_patch | operational)."""

import pytest

from remediation.strategies import build_remediation, get_strategy


def _enum_summary():
    return {
        "enum_drift": {"new_values": ["PARTIAL_REFUND"]},
        "code": {"missing_values": ["PARTIAL_REFUND"], "handled_values": ["REFUNDED"],
                 "repo_path": "pipelines/models/ods/ods_payment_enriched.sql",
                 "snippet": "WHEN refund_status = 'REFUNDED' THEN refunded_amount"},
    }


# ── unit: từng strategy ──────────────────────────────────────
def test_enum_drift_yields_code_patch():
    rem = build_remediation({"anomaly_type": "enum_drift", "tool_results_summary": _enum_summary()})
    assert rem["kind"] == "code_patch"
    assert "PARTIAL_REFUND" in rem["details"]["patch"]["new_code"]


def test_missing_partition_yields_operational_backfill():
    rem = build_remediation({"anomaly_type": "missing_partition", "date": "2026-06-09",
                             "tool_results_summary": {"scope": {"pipeline": "dtm_revenue_daily"}}})
    assert rem["kind"] == "operational"
    assert rem["details"]["action"] == "backfill"
    assert rem["details"]["partition"] == "2026-06-09"


def test_null_spike_yields_operational_reingest():
    rem = build_remediation({"anomaly_type": "null_spike",
                             "tool_results_summary": {"scope": {"null_column": "amount"}}})
    assert rem["kind"] == "operational"
    assert rem["details"]["action"] == "reingest"


def test_duplicate_yields_code_patch_dedup():
    rem = build_remediation({"anomaly_type": "duplicate", "tool_results_summary": {"scope": {}}})
    assert rem["kind"] == "code_patch"
    assert rem["details"]["patch"]["change_type"] == "add_dedup"


def test_unknown_anomaly_has_no_strategy():
    assert build_remediation({"anomaly_type": "never_seen"}) is None
    assert build_remediation({}) is None
    assert get_strategy("enum_drift") is not None


# ── graph: anomaly khác nhau → remediation kind khác nhau ─────
def _run(request):
    from data.seed_data.seed import main as seed_main
    from graph.state import new_state
    from graph.workflow import build_workflow
    seed_main()
    return build_workflow().invoke(new_state(request))


def test_workflow_code_patch_on_enum_case():
    final = _run("Revenue 2026-06-07 lệch 2.1%")
    rem = final.get("remediation")
    assert rem and rem["kind"] == "code_patch"
    assert "PARTIAL_REFUND" in final["patch"]["new_code"]


def test_workflow_operational_remediation_on_missing_partition():
    final = _run("Revenue report 2026-06-09 không thấy số")
    rem = final.get("remediation")
    assert rem and rem["kind"] == "operational"
    assert rem["details"]["action"] == "backfill"
