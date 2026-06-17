"""Step 17 — Incident Agent (classify + tier-based action)."""

from agents.incident_agent import handle_incident
from governance.action_policy import decide_action, is_autonomous_allowed
from tools.run_classifier import classify_failure


# ── classifier ───────────────────────────────────────────────
def test_classify_failure_types():
    assert classify_failure("HTTP 429 Too Many Requests")["failure_type"] == "transient"
    assert classify_failure("Schema mismatch: required column added")["failure_type"] == "schema_drift"
    assert classify_failure("permission denied for table x")["failure_type"] == "permission"
    assert classify_failure("Traceback ... KeyError: 'amount'")["failure_type"] == "code_bug"
    assert classify_failure("dbt test accepted_values failed")["failure_type"] == "data_quality"
    assert classify_failure("hoàn toàn lạ")["failure_type"] == "unknown"


# ── action policy / tiers ────────────────────────────────────
def test_transient_is_autonomous_retry():
    d = decide_action("transient")
    assert d["action"] == "retry_job"
    assert d["autonomous"] is True
    assert is_autonomous_allowed(d["action"]) is True


def test_schema_drift_needs_approval_not_autonomous():
    d = decide_action("schema_drift")
    assert d["requires_approval"] is True
    assert d["autonomous"] is False


# ── incident handling end-to-end (mock logs) ────────────────
def test_transient_job_auto_retries():
    res = handle_incident("load_stripe_payments")
    assert res["failure_type"] == "transient"
    assert res["auto_action_taken"] == "retry_job"      # L3 tự chạy
    assert "No manual action" in res["summary"]


def test_schema_drift_job_proposes_patch_no_auto():
    res = handle_incident("daily_orders_pipeline")
    assert res["failure_type"] == "schema_drift"
    assert res["auto_action_taken"] is None             # KHÔNG tự apply
    assert res["requires_approval"] is True
    assert res["action"] == "propose_patch"


def test_data_quality_job_notifies_owner():
    res = handle_incident("revenue_daily")
    assert res["failure_type"] == "data_quality"
    assert res["auto_action_taken"] == "notify_owner"   # L3 reversible


def test_permission_job_escalates_no_auto():
    res = handle_incident("export_finance_report")
    assert res["failure_type"] == "permission"
    assert res["auto_action_taken"] is None


def test_unknown_job_escalates():
    res = handle_incident("job_khong_ton_tai")
    assert res["action"] == "escalate"


def test_audit_trail_present():
    res = handle_incident("load_stripe_payments")
    assert res["audit"] and any("classified" in a for a in res["audit"])
