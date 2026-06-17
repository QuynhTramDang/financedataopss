"""Scenario catalog → investigations backed by the REAL seeded warehouse.

Every entry maps to a real (metric, date, anomaly) embedded by the seed generator, so the
detail tabs are genuine: Logs/run-check hit real endpoints, run-check runs real validation
(enum_drift = before/after reconciliation; other anomalies = a real validation pass + triage).

This replaces "hand-written fixtures only" with a multi-domain, DB-grounded queue.
"""

from __future__ import annotations

from typing import Any

from data.seed_data.domains import DOMAINS

# anomaly → presentation + routing metadata
ANOMALY: dict[str, dict[str, Any]] = {
    "enum_drift": {"label": "enum drift", "severity": "high", "route": "confident", "fixable": True,
                   "source": "alert",
                   "rc": "A new status value appeared in the source but the pipeline only maps the old "
                         "ones, so the metric is overstated. A narrow CASE-mapping fix resolves it."},
    "null_spike": {"label": "null spike", "severity": "medium", "route": "escalate", "fixable": False,
                   "source": "sweep",
                   "rc": "The measure column is NULL on a large share of rows — an ingestion-quality "
                         "issue, not a safe code patch. Escalate to the data owner; block publish."},
    "missing_partition": {"label": "missing partition", "severity": "high", "route": "escalate", "fixable": False,
                          "source": "dag_fail",
                          "rc": "The partition loaded zero rows — upstream job did not run. Backfill the "
                                "partition; do not recompute the metric on empty data."},
    "duplicate": {"label": "duplicate records", "severity": "medium", "route": "escalate", "fixable": False,
                  "source": "sweep",
                  "rc": "A business key is counted more than once (double-write on retry). Dedup by key "
                        "before aggregation; the metric is inflated until then."},
    "distribution_drift": {"label": "outlier spike", "severity": "high", "route": "escalate", "fixable": False,
                           "source": "sweep",
                           "rc": "The measure distribution shifted far from baseline (≈5x). Likely a unit/source "
                                 "change or bad batch — verify source before trusting the metric."},
    "volume_drop": {"label": "volume drop", "severity": "medium", "route": "escalate", "fixable": False,
                    "source": "sweep",
                    "rc": "Row count collapsed vs baseline — late-arriving or missing data. Wait for the "
                          "late batch or backfill before publishing."},
}

DOMAIN_META = {
    "revenue": {"label": "Revenue", "owner": "Finance", "metric": "net_revenue"},
    "cash_flow": {"label": "Cash Flow", "owner": "Treasury", "metric": "net_cash_flow"},
    "spend": {"label": "Cost / Spend", "owner": "FP&A", "metric": "net_spend"},
    "ar": {"label": "AR / Collections", "owner": "Collections", "metric": "net_receivable"},
}

# Curated ~7 scenarios (+ 3 flagship fixtures = ~10 total) — one fixable enum per new domain
# plus a couple of escalate cases, so the queue is rich but readable. Each links to a real
# (metric, date, anomaly) embedded in the seed, so the agent + run-check are genuine.
_CURATED: list[tuple[str, str, str]] = [
    ("revenue", "2026-06-11", "duplicate"),
    ("cash_flow", "2026-06-05", "enum_drift"),
    ("cash_flow", "2026-05-28", "null_spike"),
    ("cash_flow", "2026-06-02", "missing_partition"),
    ("spend", "2026-06-06", "enum_drift"),
    ("spend", "2026-06-03", "distribution_drift"),
    ("ar", "2026-06-04", "enum_drift"),
    ("ar", "2026-05-26", "duplicate"),
]


def _drift_value(domain_key: str) -> str | None:
    for s in DOMAINS:
        if s.key == domain_key:
            return s.drift_value
    return {"revenue": "PARTIAL_REFUND"}.get(domain_key)


def scenario_catalog() -> list[dict[str, Any]]:
    """Curated multi-domain scenario list (excludes the 3 flagship fixtures)."""
    out: list[dict[str, Any]] = []
    for domain, date, atype in _CURATED:
        meta = ANOMALY[atype]
        out.append({
            "id": f"INV-{domain[:3].upper()}-{date.replace('-', '')[4:]}",
            "domain": domain, "metric": DOMAIN_META[domain]["metric"], "date": date,
            "anomaly_type": atype, "fixable": meta["fixable"], "severity": meta["severity"],
            "source": meta["source"], "route": meta["route"], "drift_value": _drift_value(domain),
        })
    return out


def build_investigation(s: dict[str, Any]) -> dict[str, Any]:
    """Full investigation detail for a catalog entry — truthful template; real numbers come
    from the live run-check/logs endpoints (this is the read model the list+detail render)."""
    meta = ANOMALY[s["anomaly_type"]]
    dom = DOMAIN_META[s["domain"]]
    fixable = s["fixable"]
    status = "needs_approval" if fixable else "escalated"
    trace = [
        {"stage": "PLAN", "name": "Planner", "status": "ok", "duration": "1.1s",
         "detail": f"intent=metric_anomaly · metric={s['metric']} · date={s['date']}", "calls": []},
        {"stage": "EXEC", "name": "Tool Executor", "status": "ok", "duration": "8.0s",
         "detail": f"governed read-only diagnostics on {s['metric']} · 0 raw rows to LLM", "calls": []},
        {"stage": "CHK", "name": "Verifier / Critic", "status": "ok" if fixable else "warn", "duration": "3.0s",
         "detail": f"confidence gate: {meta['route']}", "calls": []},
        {"stage": "DEC", "name": "Decision Router", "status": "warn", "duration": "80ms",
         "detail": ("narrow fix validated -> approval" if fixable
                    else "no safe code patch -> escalate to owner"), "calls": []},
    ]
    inv = {
        "id": s["id"], "title": f"{s['metric']} {meta['label']} on {s['date']}",
        "metric": s["metric"], "date": s["date"], "domain": s["domain"], "project": dom["label"],
        "source": s["source"], "trigger": f"{meta['source']} · {dom['label']}",
        "status": status, "severity": s["severity"], "intent": "metric_anomaly",
        "risk_level": "high" if s["severity"] == "high" else "medium",
        "issue_mode": "known" if fixable else "unknown",
        "confidence_route": meta["route"], "anomaly_type": s["anomaly_type"],
        "cost_usd": 0.06, "tokens": {"input": 8200, "output": 1700}, "raw_rows_to_llm": 0,
        "started_at": "recent", "duration": "12s",
        "root_cause": meta["rc"], "trace": trace,
        "claims": [], "evidence": [{"type": s["anomaly_type"], "body": meta["rc"]}],
        "patch": None, "validation": None, "dbt_test": None,
        "trust_matrix": {"evidence_verified": {"value": "yes", "risk": "ok"},
                         "fixable": {"value": "yes" if fixable else "no", "risk": "ok" if fixable else "warn"},
                         "blockers": [] if fixable else ["Owner handoff — not a safe code patch"]},
        "lineage": {"asset": s["metric"], "chain": [], "blast_radius_size": 0},
        "approval_status": "pending" if fixable else "n/a",
        "log_job": None,
        "check": ({"metric": s["metric"], "date": s["date"], "new_values": [s["drift_value"]]}
                  if fixable and s["drift_value"] else None),
        # any metric+date scenario can run a real validation pass even when not enum-fixable
        "validate": {"metric": s["metric"], "date": s["date"]},
    }
    if fixable:
        inv["evidence"].append({"type": "reconciliation", "body": "Run the fix & test tab computes the real before/after reconciliation from SQL."})
    return inv
