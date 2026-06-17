"""Demo fixtures for the web UI.

These mirror the shape produced by the real LangGraph workflow (graph/state.py)
so the React frontend can render every screen — Investigation Detail (trace,
claims, RCA/patch/validation/dbt, trust matrix), Approvals + action loop,
Integrations, Catalog, Governance — without invoking the LLM. The flagship case
is the net_revenue 2.1% mismatch caused by an unhandled PARTIAL_REFUND enum,
which is the project's golden investigation.

Numbers here match the project's golden reconciliation (2.10% -> 0.00%).
When the real workflow runs (POST /investigations with a working LLM), its
normalized state replaces these for that investigation id.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

# ─────────────────────────── Investigations ───────────────────────────

INV_REVENUE: dict[str, Any] = {
    "id": "INV-0607revn",
    "title": "net_revenue overstated by 2.1%",
    "metric": "net_revenue",
    "date": "2026-06-07",
    "domain": "revenue", "project": "Revenue",
    "source": "alert",                # alert | sweep | dag_fail | manual
    "trigger": "Finance reconciliation alert",
    "status": "needs_approval",       # running | needs_approval | escalated | resolved
    "severity": "high",
    "intent": "investigate_revenue_mismatch",
    "risk_level": "high",
    "issue_mode": "known",
    "confidence_route": "confident",
    "anomaly_type": "enum_drift",
    "cost_usd": 0.11,
    "tokens": {"input": 14210, "output": 3980},
    "raw_rows_to_llm": 0,
    "started_at": "12 min ago",
    "duration": "42s",
    "log_job": "revenue_daily",
    "check": {"metric": "net_revenue", "date": "2026-06-07", "new_values": ["PARTIAL_REFUND"]},
    "root_cause": (
        "revenue_daily.sql subtracts refunded_amount only WHEN refund_status='REFUNDED'. "
        "The source added a new value PARTIAL_REFUND (4.2% of 2026-06-07 rows) which is "
        "never subtracted, so net_revenue is overstated by 2.10%."
    ),
    # ── Trace (Planner -> Executor -> Verifier -> Decision), incl. confidence + validation loop
    "trace": [
        {"stage": "PLAN", "name": "Planner", "status": "ok", "duration": "1.8s",
         "detail": "intent=metric_mismatch · risk=L2 · scope=net_revenue 2026-06-07",
         "calls": [
             {"name": "intent_classifier", "tier": "L1", "status": "ok", "duration": "320ms",
              "detail": "intent=investigate_revenue_mismatch · confidence 0.93"},
             {"name": "context_retriever", "tier": "L1", "status": "ok", "duration": "540ms",
              "detail": "hybrid RAG: runbook_revenue_mismatch + 2 prior incidents (INC-2026-0520)"},
             {"name": "plan_generated", "tier": "L1", "status": "ok", "duration": "940ms",
              "detail": "4 steps: sql_profile · enum_drift · code_search · impact_simulation"},
         ]},
        {"stage": "EXEC", "name": "Tool Executor", "status": "ok", "duration": "12.4s",
         "detail": "governed registry · 4/4 tools ok · 0 raw rows to LLM",
         "calls": [
             {"name": "sql_profile · revenue_daily", "tier": "L1", "status": "ok", "duration": "3.1s",
              "detail": "measured mismatch 2.10% vs payment dashboard"},
             {"name": "enum_drift_check · refund_status", "tier": "L1", "status": "ok", "duration": "2.0s",
              "detail": "new value PARTIAL_REFUND — 4.2% of rows"},
             {"name": "code_search · revenue_daily.sql (GitLab MCP)", "tier": "L1", "status": "ok", "duration": "4.6s",
              "detail": "mapping subtracts only WHEN refund_status='REFUNDED' (line 118)"},
             {"name": "impact_simulation", "tier": "L1", "status": "ok", "duration": "2.7s",
              "detail": "affected_amount 210,000,000 VND"},
         ]},
        {"stage": "CHK", "name": "Verifier / Critic", "status": "ok", "duration": "4.9s",
         "detail": "confidence gate: confident (>=0.6) · 4 claims · 4 verified · 0 contradictions",
         "calls": [
             {"name": "claim_verifier", "tier": "L1", "status": "ok", "duration": "3.2s",
              "detail": "3/3 numeric claims reconcile with measured values"},
             {"name": "contradiction_check", "tier": "L1", "status": "ok", "duration": "1.7s",
              "detail": "no conflict with prior incidents in memory"},
         ]},
        {"stage": "VAL", "name": "Validation Engine", "status": "ok", "duration": "5.2s",
         "detail": "reconciliation test on proposed fix · attempt 1/2 PASS",
         "calls": [
             {"name": "reconciliation · before fix", "tier": "L1", "status": "ok", "duration": "2.4s",
              "detail": "mismatch 2.10%"},
             {"name": "reconciliation · after fix", "tier": "L1", "status": "ok", "duration": "2.8s",
              "detail": "mismatch 0.00% — PASS"},
         ]},
        {"stage": "DEC", "name": "Decision Router", "status": "warn", "duration": "90ms",
         "detail": "patch narrow & validated, but changes a revenue metric -> gate for approval",
         "calls": [
             {"name": "action_policy.check", "tier": "L2", "status": "warn", "duration": "40ms",
              "detail": "create_gitlab_mr -> tier L2 -> APPROVAL REQUIRED"},
         ]},
    ],
    "claims": [
        {"claim": "net_revenue mismatch is 2.1%", "evidence": "reconciliation",
         "rule": "abs_diff_lt(measured, 2.10, 0.01)", "status": "verified"},
        {"claim": "refund_status has new value PARTIAL_REFUND", "evidence": "enum_drift",
         "rule": "contains(new_values, 'PARTIAL_REFUND')", "status": "verified"},
        {"claim": "mapping handles only REFUNDED", "evidence": "code_search",
         "rule": "eq(handled_values, ['REFUNDED'])", "status": "verified"},
        {"claim": "affected_amount = 210,000,000 VND", "evidence": "impact_simulation",
         "rule": "eq(affected_amount, 210000000)", "status": "verified"},
    ],
    "evidence": [
        {"type": "enum_drift", "body": "refund_status gained value PARTIAL_REFUND — 4.2% of 2026-06-07 rows"},
        {"type": "code_search", "body": "revenue_daily.sql:118 subtracts refunded_amount only WHEN refund_status='REFUNDED'"},
        {"type": "impact_simulation", "body": "affected_amount = 210,000,000 VND on net_revenue"},
        {"type": "reconciliation", "body": "measured mismatch 2.10% vs payment dashboard"},
    ],
    "patch": {
        "file": "revenue_daily.sql",
        "diff": [
            ["ctx", "-- revenue_daily.sql"],
            ["del", "WHEN refund_status = 'REFUNDED'"],
            ["del", "  THEN amount - refunded_amount"],
            ["add", "WHEN refund_status IN ('REFUNDED','PARTIAL_REFUND')"],
            ["add", "  THEN amount - refunded_amount"],
            ["ctx", "ELSE amount END AS net_amount"],
        ],
        "review": "Patch is narrow (single CASE branch). Requires Finance approval because it changes a revenue metric.",
        "risk_level": "high",
        "approval_required": True,
    },
    "validation": {
        "status": "pass",
        "attempts": 1,
        "before_pct": 2.10,
        "after_pct": 0.00,
        "tests": [{"name": "reconciliation_net_revenue", "status": "pass"}],
    },
    "dbt_test": {
        "name": "accepted_values_refund_status",
        "catches_bug": True,
        "before_fix_status": "fail",
        "after_fix_status": "pass",
        "yaml": (
            "models:\n"
            "  - name: revenue_daily\n"
            "    columns:\n"
            "      - name: refund_status\n"
            "        tests:\n"
            "          - accepted_values:\n"
            "              values: ['NONE','REFUNDED','PARTIAL_REFUND']\n"
        ),
    },
    "trust_matrix": {
        "evidence_verified": {"value": "4/4", "risk": "ok"},
        "numbers_from_sql": {"value": "yes", "risk": "ok"},
        "validation_passed": {"value": "2.10% -> 0.00%", "risk": "ok"},
        "regression_test": {"value": "dbt catches bug", "risk": "ok"},
        "changes_revenue_metric": {"value": "yes -> approval", "risk": "warn"},
        "blockers": ["Finance approval required before MR"],
    },
    "lineage": {
        "asset": "net_revenue",
        "chain": ["payment_txn", "stg_payment", "revenue_daily", "net_revenue", "finance_revenue_report"],
        "affected_reports": ["finance_revenue_report"],
        "blast_radius_size": 5,
    },
    "approval_status": "pending",
}

INV_NULL = {
    "id": "INV-0608null",
    "title": "amount null spike on stg_payment",
    "metric": "amount",
    "date": "2026-06-08",
    "domain": "revenue", "project": "Revenue",
    "source": "sweep",
    "trigger": "Proactive DQ sweep (null-rate monitor)",
    "status": "escalated",
    "severity": "medium",
    "intent": "data_quality_anomaly",
    "risk_level": "medium",
    "issue_mode": "unknown",
    "confidence_route": "escalate",
    "anomaly_type": "null_spike",
    "cost_usd": 0.05,
    "tokens": {"input": 6100, "output": 1400},
    "raw_rows_to_llm": 0,
    "started_at": "1h ago",
    "duration": "18s",
    "log_job": None,
    "check": None,
    "root_cause": (
        "amount null_rate jumped to 40% on the 2026-06-08 partition. This is an ingestion "
        "quality issue, not a safe code patch — escalated to data-platform; downstream publish blocked."
    ),
    "trace": [
        {"stage": "PLAN", "name": "Planner", "status": "ok", "duration": "1.1s",
         "detail": "intent=data_quality_anomaly · scope=amount 2026-06-08",
         "calls": [{"name": "context_retriever", "tier": "L1", "status": "ok", "duration": "420ms",
                    "detail": "no matching runbook -> unknown mode"}]},
        {"stage": "EXEC", "name": "Tool Executor", "status": "ok", "duration": "6.0s",
         "detail": "null_check · freshness_check · volume_check",
         "calls": [
             {"name": "null_check · amount", "tier": "L1", "status": "ok", "duration": "2.1s",
              "detail": "null_rate 40% (80/200 rows)"},
             {"name": "freshness_check", "tier": "L1", "status": "ok", "duration": "1.6s",
              "detail": "partition loaded"},
             {"name": "volume_check", "tier": "L1", "status": "ok", "duration": "1.4s",
              "detail": "row count normal"},
         ]},
        {"stage": "CHK", "name": "Verifier / Critic", "status": "warn", "duration": "2.0s",
         "detail": "confidence gate: escalate (<0.6) — no safe deterministic patch",
         "calls": [{"name": "root_cause_reasoner", "tier": "L1", "status": "warn", "duration": "1.8s",
                    "detail": "ingestion-quality issue, not code -> escalate"}]},
        {"stage": "DEC", "name": "Decision Router", "status": "warn", "duration": "60ms",
         "detail": "escalate to data-platform owner; block downstream publish",
         "calls": [{"name": "escalate", "tier": "L1", "status": "warn", "duration": "30ms",
                    "detail": "no patch proposed"}]},
    ],
    "claims": [
        {"claim": "amount null_rate is 40%", "evidence": "null_check",
         "rule": "abs_diff_lt(null_rate, 0.40, 0.02)", "status": "verified"},
    ],
    "evidence": [
        {"type": "null_check", "body": "amount null_rate 40% (80/200 rows) on 2026-06-08"},
        {"type": "freshness", "body": "partition loaded — not a missing-partition issue"},
        {"type": "volume", "body": "row count within baseline"},
    ],
    "patch": None,
    "validation": None,
    "dbt_test": None,
    "trust_matrix": {
        "evidence_verified": {"value": "1/1", "risk": "ok"},
        "safe_patch_available": {"value": "no", "risk": "bad"},
        "owner_handoff": {"value": "data-platform", "risk": "warn"},
        "blockers": ["Upstream source replay required — outside agent's safe scope"],
    },
    "lineage": {"asset": "amount", "chain": ["raw_payment", "stg_payment", "revenue_daily"],
                "affected_reports": ["finance_revenue_report"], "blast_radius_size": 3},
    "approval_status": "n/a",
}

INV_ORDERS = {
    "id": "INV-0616schm",
    "title": "daily_orders_pipeline schema drift",
    "metric": "order_channel",
    "date": "2026-06-16",
    "domain": "revenue", "project": "Revenue",
    "source": "dag_fail",
    "trigger": "Airflow task_failed (compile_stg_orders)",
    "status": "running",
    "severity": "high",
    "intent": "pipeline_failure",
    "risk_level": "medium",
    "issue_mode": "known",
    "confidence_route": "confident",
    "anomaly_type": "schema_drift",
    "cost_usd": 0.08,
    "tokens": {"input": 9800, "output": 2100},
    "raw_rows_to_llm": 0,
    "started_at": "4 min ago",
    "duration": "running",
    "log_job": "daily_orders_pipeline",
    "check": None,
    "root_cause": (
        "Upstream raw.orders added a required column order_channel; the staging contract was not "
        "updated. Draft GitLab MR adds the column + a not_null test, pending data-owner review."
    ),
    "trace": [
        {"stage": "PLAN", "name": "Planner", "status": "ok", "duration": "1.0s",
         "detail": "intent=pipeline_failure · DAG daily_orders_pipeline",
         "calls": [{"name": "log_search", "tier": "L1", "status": "ok", "duration": "600ms",
                    "detail": "compile error: required column order_channel missing in stg_orders"}]},
        {"stage": "EXEC", "name": "Tool Executor", "status": "running", "duration": "—",
         "detail": "schema_diff · code_search in progress",
         "calls": [{"name": "schema_diff · raw.orders", "tier": "L1", "status": "ok", "duration": "1.9s",
                    "detail": "+ order_channel (required)"}]},
    ],
    "claims": [],
    "evidence": [
        {"type": "schema_diff", "body": "raw.orders added required column order_channel"},
        {"type": "log", "body": "compile_stg_orders failed: missing column order_channel"},
    ],
    "patch": {
        "file": "stg_orders.sql",
        "diff": [
            ["ctx", "SELECT order_id, customer_id, order_amount"],
            ["add", "     , order_channel"],
            ["ctx", "FROM raw.orders"],
        ],
        "review": "Draft only. Changes a published staging schema -> data-owner review required.",
        "risk_level": "medium",
        "approval_required": True,
    },
    "validation": {"status": "pending", "attempts": 0, "before_pct": None, "after_pct": None, "tests": []},
    "dbt_test": None,
    "trust_matrix": {
        "evidence_verified": {"value": "2/2", "risk": "ok"},
        "changes_published_schema": {"value": "yes -> review", "risk": "warn"},
        "blockers": ["Data-owner review for staging contract change"],
    },
    "lineage": {"asset": "stg_orders", "chain": ["raw.orders", "stg_orders", "orders_dashboard"],
                "affected_reports": ["orders_dashboard"], "blast_radius_size": 3},
    "approval_status": "pending",
}

INVESTIGATIONS = [INV_REVENUE, INV_NULL, INV_ORDERS]

# ─────────────────────────── Approvals ───────────────────────────

APPROVALS = [
    {
        "id": "ap_1042",
        "investigation_id": "INV-0607revn",
        "title": "Create GitLab MR — refund mapping fix",
        "automation": "Revenue mismatch triage",
        "risk": "L2",
        "impact": "net_revenue · finance_revenue_report",
        "age": "12 min",
        "why": ("revenue_daily.sql subtracts refunded_amount only WHEN refund_status='REFUNDED'. "
                "Source added PARTIAL_REFUND (4.2% of rows), never subtracted -> net_revenue overstated 2.1%."),
        "rollback": "Revert MR; revenue_daily is recomputed each run, no destructive migration.",
        "validation": "Reconciliation 2.10% -> 0.00%. dbt accepted_values test catches the old bug, passes after patch.",
        "status": "pending",
        # one approval per incident; approving runs MR + Teams + memory together (action loop)
        "action_result": None,
    },
]


def action_result_for(approval_id: str) -> dict[str, Any]:
    """What apply_remediation + memory_writeback report after an approve (demo)."""
    return {
        "steps": [
            {"name": "gitlab_create_mr", "tier": "L2", "status": "done",
             "detail": "MR !318 drafted: fix(revenue): handle PARTIAL_REFUND",
             "link": "https://gitlab.example/finance/dbt/-/merge_requests/318"},
            {"name": "airflow_trigger_dag", "tier": "L3", "status": "done",
             "detail": "revenue_daily_dag backfill 2026-06-07 queued"},
            {"name": "reconciliation · re-validate", "tier": "L1", "status": "done",
             "detail": "post-fix mismatch 0.00% — PASS"},
            {"name": "teams_notify", "tier": "L2", "status": "done",
             "detail": "RCA summary sent to Finance channel"},
            {"name": "memory_writeback", "tier": "L2", "status": "done",
             "detail": "incident INC-2026-06-07-net_revenue written to memory"},
        ],
        "audit": [
            "ap_1042 approved by Trâm Đ. (Data Engineer)",
            "gitlab_create_mr · L2 · allow-listed · 320ms",
            "airflow_trigger_dag · L3 · reversible · 210ms",
            "memory_writeback · L2 · after validated+approved",
        ],
    }


# ─────────────────────────── Integrations ───────────────────────────

INTEGRATIONS = [
    {"name": "Airflow", "type": "MCP", "status": "healthy", "auth": "service account",
     "scopes": "read, retry (L3)", "calls": "1,283", "error_rate": "0.4%", "note": ""},
    {"name": "GitLab", "type": "MCP", "status": "healthy", "auth": "project token",
     "scopes": "read, draft MR (L2)", "calls": "342", "error_rate": "0.2%", "note": ""},
    {"name": "Microsoft Teams", "type": "MCP", "status": "attention", "auth": "OAuth",
     "scopes": "send draft, notify (L2)", "calls": "97", "error_rate": "2.1%",
     "note": "token expires in 3 days"},
    {"name": "Google Sheets", "type": "MCP", "status": "degraded", "auth": "OAuth",
     "scopes": "read ranges (L1)", "calls": "211", "error_rate": "8.7%",
     "note": "credential missing — re-auth required"},
    {"name": "Email", "type": "MCP", "status": "healthy", "auth": "OAuth",
     "scopes": "read inbox (L1)", "calls": "423", "error_rate": "0.5%", "note": ""},
]

# ─────────────────────────── Catalog ───────────────────────────

CATALOG = [
    {"name": "net_revenue", "kind": "metric", "owner": "Finance", "status": "attention",
     "definition": "paid_amount - refunded_amount (refunded only for REFUNDED/PARTIAL_REFUND)",
     "sources": ["payment_txn", "order_fact"],
     "lineage": ["payment_txn", "stg_payment", "revenue_daily", "net_revenue", "finance_revenue_report"],
     "contract_tests": [{"name": "refund_status accepted_values", "status": "attention"}]},
    {"name": "gross_revenue", "kind": "metric", "owner": "Finance", "status": "healthy",
     "definition": "sum(amount) before refunds", "sources": ["payment_txn"],
     "lineage": ["payment_txn", "revenue_daily", "gross_revenue"],
     "contract_tests": [{"name": "amount not_null", "status": "verified"}]},
    {"name": "payment_txn", "kind": "table", "owner": "data-platform", "status": "healthy",
     "definition": "Source fact table, 1.27M rows, partition key txn_date",
     "sources": [], "lineage": ["payment_txn", "stg_payment"],
     "contract_tests": [{"name": "txn_id unique", "status": "verified"}]},
    {"name": "revenue_daily", "kind": "table", "owner": "Finance", "status": "attention",
     "definition": "Daily revenue mart computed from stg_payment", "sources": ["stg_payment"],
     "lineage": ["stg_payment", "revenue_daily", "finance_revenue_report"],
     "contract_tests": [{"name": "reconciliation", "status": "attention"}]},
]

# ─────────────────────────── DAG monitor / sweep ───────────────────────────

DAGS = [
    {"id": "revenue_daily_dag", "status": "failed", "owner": "finance-data", "sla": "04:00",
     "last": "today 04:01", "runtime": "0/80m", "success": "86%", "alert": "net_revenue overstated 2.1%"},
    {"id": "load_stripe_payments", "status": "failed", "owner": "data-platform", "sla": "03:00",
     "last": "today 03:02", "runtime": "0/120m", "success": "71%", "alert": "HTTP 429 after 3 retries"},
    {"id": "stg_payment_dag", "status": "running", "owner": "data-platform", "sla": "03:30",
     "last": "running", "runtime": "45/90m", "success": "95%", "alert": ""},
    {"id": "daily_orders_pipeline", "status": "failed", "owner": "orders-data", "sla": "02:30",
     "last": "today 02:31", "runtime": "0/60m", "success": "80%", "alert": "required column order_channel added"},
    {"id": "export_finance_report", "status": "success", "owner": "bi-team", "sla": "05:00",
     "last": "today 05:03", "runtime": "18/20m", "success": "98%", "alert": ""},
]

# ─────────────────────────── Knowledge ───────────────────────────

LEARNED_INCIDENTS = [
    {"incident_id": "INC-2026-0520-net_revenue", "metric": "net_revenue",
     "root_cause": "refund_status mapping missed a new enum value",
     "fix": "expand CASE mapping + accepted_values dbt test",
     "prevented_by": "accepted_values_refund_status (catches recurrence)"},
    {"incident_id": "INC-2026-0512-orders", "metric": "order_count",
     "root_cause": "duplicate order_id from retry double-write",
     "fix": "dedup by business key",
     "prevented_by": "unique(order_id) dbt test"},
]


def all_state() -> dict[str, Any]:
    """Deep copy so the in-memory store can mutate approvals without touching fixtures."""
    return {
        "investigations": deepcopy(INVESTIGATIONS),
        "approvals": deepcopy(APPROVALS),
        "integrations": deepcopy(INTEGRATIONS),
        "catalog": deepcopy(CATALOG),
        "dags": deepcopy(DAGS),
        "learned": deepcopy(LEARNED_INCIDENTS),
    }
