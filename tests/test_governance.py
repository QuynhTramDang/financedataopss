"""Step 5 — Tool Governance Engine (rule engine, offline)."""

from governance import (
    PermissionTier,
    check_sql,
    check_tool,
    decide_risk_action,
    mask_record,
    tier_of_action,
)


# ── sql_policy ───────────────────────────────────────────────
def test_block_select_star():
    out = check_sql("select * from payment_txn where txn_date = '2026-06-07'")
    assert out["decision"] == "blocked"
    assert "select *" in out["reason"].lower()
    assert out["suggestion"]


def test_block_missing_partition_filter():
    out = check_sql("select refund_status, count(*) from payment_txn group by refund_status")
    assert out["decision"] == "blocked"
    assert "txn_date" in out["reason"]


def test_allow_aggregate_with_partition_filter():
    sql = ("select refund_status, count(*) as c, sum(amount) as amt "
           "from payment_txn where txn_date = '2026-06-07' group by refund_status")
    out = check_sql(sql)
    assert out["decision"] == "allowed"


def test_block_dml():
    out = check_sql("update payment_txn set amount = 0 where txn_date = '2026-06-07'")
    assert out["decision"] == "blocked"


# ── tool_policy ──────────────────────────────────────────────
def test_tool_allowlist_and_block():
    assert check_tool("sql_profile")["decision"] == "allowed"
    assert check_tool("deploy_pipeline")["decision"] == "blocked"
    assert check_tool("khong_ton_tai")["decision"] == "blocked"


def test_write_tool_requires_approval_and_tier():
    out = check_tool("generate_patch")
    assert out["decision"] == "allowed"
    assert out["requires_approval"] is True
    assert out["tier"] == PermissionTier.L2_ASSISTED.value


def test_diagnostic_tool_is_l1_no_approval():
    out = check_tool("sql_profile")
    assert out["requires_approval"] is False
    assert out["tier"] == PermissionTier.L1_READ_ONLY.value


# ── approval_policy ──────────────────────────────────────────
def test_high_risk_requires_approval_no_deploy():
    d = decide_risk_action("high")
    assert d["requires_approval"] is True
    assert d["can_deploy"] is False
    assert d["tier"] == PermissionTier.L2_ASSISTED.value


def test_low_risk_no_approval():
    d = decide_risk_action("low")
    assert d["requires_approval"] is False
    assert d["tier"] == PermissionTier.L1_READ_ONLY.value


def test_tier_of_retry_is_l3():
    assert tier_of_action("retry_transient") == PermissionTier.L3_SAFE_AUTONOMOUS


# ── pii_policy ───────────────────────────────────────────────
def test_mask_sensitive_fields():
    masked = mask_record({"email": "alice@example.com", "amount": 1000, "card_no": "1234567890"})
    assert masked["email"] != "alice@example.com"
    assert "*" in masked["email"]
    assert masked["amount"] == 1000           # field thường không bị mask


# ── node integration ─────────────────────────────────────────
def test_node_attaches_governance_decision():
    from graph.state import new_state
    from graph.workflow import build_workflow

    final = build_workflow().invoke(new_state("Revenue 2026-06-07 lệch 2.1%"))
    gov = final.get("governance", {})
    assert gov.get("requires_approval") is True   # finance → high → cần approval
    assert gov.get("tier") == PermissionTier.L2_ASSISTED.value
