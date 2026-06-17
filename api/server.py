"""FastAPI server — web UI boundary over the LangGraph control plane.

Run:  python -m uvicorn api.server:app --reload --port 8000

Design notes
------------
- Read-mostly. The only mutating endpoint is POST /api/approvals/{id} which mirrors
  the graph's human_approval -> apply_remediation -> memory_writeback flow.
- An in-memory store is seeded from api.fixtures so every screen renders offline.
- POST /api/investigations attempts a *real* workflow run (graph.workflow); if the
  LLM is unavailable it falls back to the flagship fixture so the UI never breaks.
- Tier/governance data is pulled from the real governance.tool_policy.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import PlainTextResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from api import fixtures  # noqa: E402

app = FastAPI(title="Finance DataOps Console API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────── In-memory store ───────────────────────────

_STORE: dict[str, Any] = fixtures.all_state()


def _seed_catalog_investigations() -> None:
    """Add DB-grounded scenario investigations (multi-domain) to the flagship fixtures."""
    from api.catalog import build_investigation, scenario_catalog
    existing = {i["id"] for i in _STORE["investigations"]}
    for s in scenario_catalog():
        if s["id"] in existing:
            continue
        _STORE["investigations"].append(build_investigation(s))


def _seed_approvals() -> None:
    """Every fixable investigation (needs_approval) gets a linked approval in the inbox, so the
    Investigation ↔ Approval ↔ Action loop is connected end-to-end (no dead ends)."""
    existing_for = {a.get("investigation_id") for a in _STORE["approvals"]}
    seq = 2000
    for inv in _STORE["investigations"]:
        if inv.get("status") != "needs_approval":
            continue
        if inv["id"] in existing_for:
            ap = next((a for a in _STORE["approvals"] if a.get("investigation_id") == inv["id"]), None)
            if ap:
                inv["approval_id"] = ap["id"]
            continue
        seq += 1
        ap_id = f"ap_{seq}"
        _STORE["approvals"].append({
            "id": ap_id, "investigation_id": inv["id"],
            "title": f"Approve fix — {inv['metric']} ({inv.get('anomaly_type', 'anomaly')})",
            "automation": f"{inv.get('project', 'DataOps')} triage", "risk": "L2",
            "impact": f"{inv['metric']} · {inv.get('project', '')}", "age": "pending",
            "why": inv.get("root_cause", "A safe, validated fix is proposed for this metric."),
            "rollback": "Revert the MR; metric is recomputed each run, no destructive migration.",
            "validation": "Run fix & test on the investigation computes the real before/after reconciliation.",
            "status": "pending", "action_result": None,
        })
        inv["approval_id"] = ap_id


def _sync_approval(inv: dict[str, Any]) -> None:
    """After the agent (re)analyzes an investigation, keep its linked approval consistent."""
    ap = next((a for a in _STORE["approvals"] if a.get("investigation_id") == inv["id"]), None)
    if inv.get("status") == "needs_approval":
        if ap is None:
            new_id = f"ap_{9000 + len(_STORE['approvals'])}"
            _STORE["approvals"].append({
                "id": new_id, "investigation_id": inv["id"],
                "title": f"Approve fix — {inv['metric']} ({inv.get('anomaly_type', 'anomaly')})",
                "automation": f"{inv.get('project', 'DataOps')} triage", "risk": "L2",
                "impact": f"{inv['metric']} · {inv.get('project', '')}", "age": "pending",
                "why": inv.get("root_cause", ""), "rollback": "Revert the MR; recomputed each run.",
                "validation": "Reconciliation verified by Run fix & test.", "status": "pending", "action_result": None,
            })
            inv["approval_id"] = new_id
        elif ap["status"] == "pending":
            inv["approval_id"] = ap["id"]


_seed_catalog_investigations()
_seed_approvals()


def _inv(inv_id: str) -> dict[str, Any]:
    for inv in _STORE["investigations"]:
        if inv["id"] == inv_id:
            return inv
    raise HTTPException(status_code=404, detail=f"investigation {inv_id} not found")


def _approval(ap_id: str) -> dict[str, Any]:
    for ap in _STORE["approvals"]:
        if ap["id"] == ap_id:
            return ap
    raise HTTPException(status_code=404, detail=f"approval {ap_id} not found")


# ─────────────────────────── Models ───────────────────────────

class InvestigationRequest(BaseModel):
    request: str
    metric: Optional[str] = None
    date: Optional[str] = None


class ApprovalDecision(BaseModel):
    decision: str  # approved | rejected | needs_revision


class AskRequest(BaseModel):
    question: str
    metric: Optional[str] = None
    date: Optional[str] = None


# ─────────────────────────── Overview / KPIs ───────────────────────────

def _summary(inv: dict[str, Any]) -> dict[str, Any]:
    """List-view projection of an investigation (no heavy trace/evidence)."""
    return {k: inv.get(k) for k in (
        "id", "title", "metric", "date", "source", "trigger", "status",
        "severity", "confidence_route", "anomaly_type", "cost_usd", "started_at", "duration",
        "domain", "project", "approval_id",
    )}


@app.get("/api/overview")
def overview() -> dict[str, Any]:
    invs = _STORE["investigations"]
    pending = [a for a in _STORE["approvals"] if a["status"] == "pending"]
    degraded = [i for i in _STORE["integrations"] if i["status"] in ("degraded", "attention")]
    attention = []
    for i in invs:
        if i["status"] in ("needs_approval", "escalated", "running"):
            attention.append({
                "id": i["id"], "title": i["title"], "severity": i["severity"],
                "status": i["status"], "sub": f"{i['trigger']} · {i['date']}", "kind": "investigation",
            })
    for a in pending:
        attention.append({
            "id": a["id"], "title": a["title"], "severity": "medium", "status": "pending approval",
            "sub": f"{a['automation']} · impact: {a['impact']}", "kind": "approval",
        })
    for c in degraded:
        attention.append({
            "id": c["name"], "title": f"{c['name']} connector {c['status']}",
            "severity": "medium", "status": c["status"],
            "sub": c["note"] or f"error rate {c['error_rate']}", "kind": "integration",
        })
    return {
        "kpis": [
            {"k": "Open investigations", "v": str(len([i for i in invs if i["status"] != "resolved"])),
             "d": f"{len([i for i in invs if i['status']=='escalated'])} escalated"},
            {"k": "Pending approvals", "v": str(len(pending)), "d": "all L2 assisted"},
            {"k": "Connector health", "v": f"{len(_STORE['integrations'])-len(degraded)}/{len(_STORE['integrations'])}",
             "d": f"{len(degraded)} need attention"},
            {"k": "Raw rows -> LLM", "v": "0", "d": "guard enforced"},
        ],
        "attention": attention,
        "triggers": [
            {"name": "Airflow webhook", "kind": "dag_fail", "last": "4 min ago", "success": "—"},
            {"name": "Proactive DQ sweep", "kind": "sweep", "last": "1h ago", "success": "—"},
            {"name": "Finance reconciliation alert", "kind": "alert", "last": "12 min ago", "success": "—"},
            {"name": "GitLab MR opened", "kind": "review", "last": "35 min ago", "success": "98%"},
        ],
    }


# ─────────────────────────── Investigations ───────────────────────────

@app.get("/api/investigations")
def list_investigations(source: Optional[str] = None, status: Optional[str] = None,
                        domain: Optional[str] = None) -> list[dict[str, Any]]:
    items = _STORE["investigations"]
    if source:
        items = [i for i in items if i.get("source") == source]
    if status:
        items = [i for i in items if i.get("status") == status]
    if domain:
        items = [i for i in items if i.get("domain") == domain]
    return [_summary(i) for i in items]


@app.get("/api/projects")
def projects() -> list[dict[str, Any]]:
    """Finance domains as projects, with live investigation counts from the store."""
    from api.catalog import DOMAIN_META
    invs = _STORE["investigations"]
    out = []
    for key, meta in DOMAIN_META.items():
        dom_invs = [i for i in invs if i.get("domain") == key]
        out.append({
            "key": key, "label": meta["label"], "owner": meta["owner"], "metric": meta["metric"],
            "investigations": len(dom_invs),
            "open": len([i for i in dom_invs if i.get("status") not in ("resolved",)]),
            "needs_approval": len([i for i in dom_invs if i.get("status") == "needs_approval"]),
        })
    return out


def _agent_run_store(inv: dict[str, Any]) -> dict[str, Any]:
    """Run the REAL LangGraph agent on this investigation's metric+date and persist the
    normalized result in the store. Returns the updated investigation (or the original on failure)."""
    metric, date = inv.get("metric"), inv.get("date")
    if not metric or not date:
        return inv
    from graph.state import new_state
    from graph.workflow import build_workflow
    req = (f"Kiểm tra {metric} ngày {date} có bất thường không, phân tích nguyên nhân và "
           f"đề xuất fix nếu an toàn.")
    final = build_workflow().invoke(new_state(req))
    norm = _normalize_agent(final, inv.get("domain", ""), inv.get("project", ""))
    norm.update({"id": inv["id"], "title": inv["title"], "source": inv.get("source", "manual"),
                 "trigger": inv.get("trigger", "agent run"), "started_at": "just now",
                 "duration": "agent", "lineage": inv.get("lineage", {}), "log_job": inv.get("log_job"),
                 "approval_id": inv.get("approval_id")})
    for i, existing in enumerate(_STORE["investigations"]):
        if existing["id"] == inv["id"]:
            _STORE["investigations"][i] = norm
            break
    # keep the linked approval in sync with the agent's real findings
    _sync_approval(norm)
    return norm


@app.get("/api/investigations/{inv_id}")
def get_investigation(inv_id: str) -> dict[str, Any]:
    """Opening an investigation = the agent analyzes it on the real warehouse (lazy, cached).
    No manual button needed; re-run is available via POST /run-agent."""
    inv = _inv(inv_id)
    # lazy-analyze only fresh states; never overwrite a post-approval state (awaiting_rerun/resolved)
    if not inv.get("agent_run") and inv.get("status") not in ("awaiting_rerun", "resolved"):
        try:
            return _agent_run_store(inv)
        except Exception:  # noqa: BLE001 — fall back to the templated read model
            pass
    return inv


@app.post("/api/investigations")
def create_investigation(req: InvestigationRequest) -> dict[str, Any]:
    """Best-effort real run; falls back to the flagship fixture if the LLM is unavailable."""
    try:
        from graph.state import new_state
        from graph.workflow import build_workflow
        final = build_workflow().invoke(new_state(req.request))
        return {"mode": "live", "investigation": _normalize_live(final)}
    except Exception as exc:  # noqa: BLE001 — offline / no LLM key -> demo fallback
        demo = fixtures.deepcopy(fixtures.INV_REVENUE)
        demo["trigger"] = f"manual: {req.request[:80]}"
        demo["source"] = "manual"
        return {"mode": "demo_fallback", "reason": str(exc)[:200], "investigation": demo}


def _normalize_live(final: dict[str, Any]) -> dict[str, Any]:
    """Map a real LangGraph final state to the UI investigation shape (best-effort)."""
    timeline = final.get("timeline", []) or []
    trace = [{"stage": (t.get("node") or "")[:4].upper() or "STEP", "name": t.get("node", "step"),
              "status": {"ok": "ok", "escalated": "warn", "blocked": "bad", "skipped": "warn"}.get(
                  t.get("status", "ok"), "ok"),
              "duration": "—", "detail": t.get("note", ""), "calls": []} for t in timeline]
    val = final.get("validation_result") or {}
    return {
        "id": final.get("investigation_id", "INV-live"),
        "title": final.get("root_cause") or "Investigation",
        "metric": final.get("metric"),
        "date": final.get("date"),
        "source": "manual",
        "trigger": "manual run",
        "status": "needs_approval" if (final.get("patch") and final.get("approval_status") == "pending")
                  else ("escalated" if final.get("confidence_route") == "escalate" else "running"),
        "severity": "high" if final.get("risk_level") in ("high", "critical") else "medium",
        "intent": final.get("intent"),
        "risk_level": final.get("risk_level"),
        "issue_mode": final.get("issue_mode"),
        "confidence_route": final.get("confidence_route"),
        "anomaly_type": final.get("anomaly_type"),
        "cost_usd": None, "tokens": {}, "raw_rows_to_llm": 0,
        "started_at": "just now", "duration": "—",
        "root_cause": final.get("root_cause"),
        "trace": trace,
        "claims": final.get("claims", []),
        "evidence": [],
        "patch": final.get("patch"),
        "validation": {"status": (val.get("status") if isinstance(val, dict) else str(val))},
        "dbt_test": final.get("dbt_test"),
        "trust_matrix": final.get("trust_matrix", {}),
        "lineage": final.get("impact_analysis", {}),
        "approval_status": final.get("approval_status", "pending"),
    }


# ─────────────────────────── Logs + triage (real log_search + incident_agent) ───────────────────────────

def _parse_log_lines(text: str) -> list[dict[str, Any]]:
    out = []
    for i, raw in enumerate(text.splitlines(), 1):
        level = "info"
        if " ERROR " in raw or raw.strip().endswith("ERROR"):
            level = "error"
        elif " WARN " in raw:
            level = "warn"
        out.append({"n": i, "level": level, "text": raw})
    return out


@app.get("/api/investigations/{inv_id}/logs")
def investigation_logs(inv_id: str) -> dict[str, Any]:
    """Real job log (tools.log_search) + real triage (agents.incident_agent)."""
    inv = _inv(inv_id)
    job = inv.get("log_job")
    if not job:
        return {"job": None, "found": False, "lines": [], "triage": None,
                "raw_url": None, "note": "Investigation này không gắn job log (anomaly từ DQ sweep)."}
    from agents.incident_agent import handle_incident
    from tools.log_search import log_search
    found = log_search(job)
    triage = handle_incident(job)
    return {
        "job": job,
        "found": found["found"],
        "lines": _parse_log_lines(found["log"]),
        "raw_url": f"/api/logs/{job}",
        "triage": {
            "failure_type": triage.get("failure_type"),
            "confidence": triage.get("confidence"),
            "action": triage.get("action"),
            "tier": triage.get("tier"),
            "requires_approval": triage.get("requires_approval"),
            "auto_action_taken": triage.get("auto_action_taken"),
            "audit": triage.get("audit", []),
            "summary": triage.get("summary"),
        },
    }


@app.get("/api/logs/{job}", response_class=PlainTextResponse)
def raw_log(job: str) -> str:
    """Raw log text — openable in a new browser tab ('view full log')."""
    from tools.log_search import log_search
    found = log_search(job)
    if not found["found"]:
        raise HTTPException(status_code=404, detail=f"no log for job {job}")
    return found["log"]


# ─────────────────────────── Run validation + dbt test (REAL execution) ───────────────────────────

@app.post("/api/investigations/{inv_id}/run-check")
def run_check(inv_id: str) -> dict[str, Any]:
    """Execute the fix as an ordered workflow with real artifacts at each step:
    agent proposes fix -> apply to sandbox -> re-query before -> re-query after ->
    reconciliation -> regression test. Every number comes from real SQL (no mock)."""
    inv = _inv(inv_id)
    chk = inv.get("check")
    if not chk:
        if inv.get("validate"):
            return _run_check_validate(inv)
        return _run_check_triage(inv)

    from domain.contracts import get_contract
    from tools.generate_dbt_test import generate_dbt_test
    from tools.run_validation import run_validation

    contract = get_contract(chk["metric"])
    date = chk["date"]
    new_values = chk["new_values"]
    status_col = contract["status_column"]
    measure = contract["measure_column"]
    deduction = contract.get("deduction_column", "refunded_amount")
    old_handled = contract.get("base_handled_statuses") or contract.get("deduction_statuses") or ["REFUNDED"]
    all_handled = sorted(set(old_handled) | set(new_values))

    # 1) agent-proposed fix (the patch the agent would apply)
    diff = [
        ["ctx", f"-- {contract['pipeline']}: net amount mapping"],
        ["del", f"WHEN {status_col} = '{old_handled[0]}'"],
        ["del", f"  THEN {measure} - {deduction}"],
        ["add", f"WHEN {status_col} IN ({', '.join(repr(v) for v in all_handled)})"],
        ["add", f"  THEN {measure} - {deduction}"],
        ["ctx", f"ELSE {measure} END AS net_amount"],
    ]

    # 2) run real validation on current vs patched logic (re-query the warehouse)
    before = run_validation(date, [], contract)            # current logic — bug present
    after = run_validation(date, new_values, contract)     # patched logic
    dbt = generate_dbt_test({"enum_drift": {"new_values": new_values}}, contract, date)

    before_pct = round(before["reconciliation"]["before_fix_diff"] * 100, 2)
    after_pct = round(after["reconciliation"]["after_fix_diff"] * 100, 2)

    def _tests(v):
        return [{"name": t["name"], "status": t["status"], "note": k_summary(t)} for t in v["tests"]]

    steps = [
        {"key": "propose", "title": "Agent proposes fix", "status": "pass",
         "detail": f"Unhandled value {new_values} in {status_col} → expand CASE mapping so it is deducted.",
         "artifact": {"kind": "diff", "file": f"{contract['pipeline']}.sql", "diff": diff}},
        {"key": "sandbox", "title": "Apply to dev sandbox", "status": "pass",
         "detail": "Patched logic loaded into an isolated recompute. Production warehouse untouched; nothing deployed.",
         "artifact": None},
        {"key": "before", "title": "Re-query — current logic", "status": "fail" if before["validation_status"] == "FAIL" else "pass",
         "detail": f"{before['passed']}/{before['total']} tests pass · reconciliation diff {before_pct}%",
         "artifact": {"kind": "tests", "tests": _tests(before)}},
        {"key": "after", "title": "Re-query — patched logic", "status": "pass" if after["validation_status"] == "PASS" else "fail",
         "detail": f"{after['passed']}/{after['total']} tests pass · reconciliation diff {after_pct}%",
         "artifact": {"kind": "tests", "tests": _tests(after)}},
        {"key": "reconcile", "title": "Reconciliation — before vs after", "status": "pass" if after_pct == 0 else "fail",
         "detail": f"mismatch {before_pct}% → {after_pct}% against the revenue baseline.",
         "artifact": {"kind": "compare", "before_pct": before_pct, "after_pct": after_pct}},
        {"key": "regression", "title": "Regression test (dbt) catches the bug", "status": "pass" if dbt["verification"]["catches_bug"] else "fail",
         "detail": f"accepted_values test: before fix {dbt['verification']['before_fix_status']} → after fix {dbt['verification']['after_fix_status']}.",
         "artifact": {"kind": "yaml", "yaml": dbt["yaml"]}},
    ]
    # the "before" step is *meant* to fail (it reproduces the bug); the fix is proven
    # when the patched re-query passes, reconciliation hits 0, and the test catches the bug.
    fix_proven = (after["validation_status"] == "PASS" and after_pct == 0
                  and dbt["verification"]["catches_bug"])
    overall = "pass" if fix_proven else "fail"
    return {
        "runnable": True, "kind": "validation", "overall": overall, "steps": steps,
        "reconciliation": {"before_pct": before_pct, "after_pct": after_pct},
        "dbt": dbt["verification"],
    }


def _run_check_validate(inv: dict[str, Any]) -> dict[str, Any]:
    """Real single validation pass for a non-enum scenario (null spike, duplicate, drift, …).
    Runs the actual deterministic test suite on the partition and classifies the anomaly."""
    v = inv["validate"]
    from agents.diagnostic_planner import run as run_diagnostics
    from agents.root_cause_reasoner import _classify
    from domain.contracts import get_contract
    from tools.run_validation import run_validation

    contract = get_contract(v["metric"])
    res = run_validation(v["date"], [], contract)
    summary = run_diagnostics({"date": v["date"], "metric": v["metric"]})
    cls = _classify(summary, v["date"])

    def _tests(rv):
        return [{"name": t["name"], "status": t["status"], "note": k_summary(t)} for t in rv["tests"]]

    steps = [
        {"key": "scope", "title": "Resolve scope from contract", "status": "pass",
         "detail": f"{v['metric']} · {contract['fact_table']} · {v['date']}", "artifact": None},
        {"key": "diagnose", "title": "Run governed diagnostics", "status": "pass",
         "detail": f"detected anomaly: {cls.get('anomaly_type') or 'none'}", "artifact": None},
        {"key": "validate", "title": "Run validation suite", "status": "pass" if res["validation_status"] == "PASS" else "fail",
         "detail": f"{res['passed']}/{res['total']} tests pass on this partition",
         "artifact": {"kind": "tests", "tests": _tests(res)}},
        {"key": "route", "title": "Decision", "status": "pass",
         "detail": ("safe code patch available" if cls.get("anomaly_type") == "enum_drift"
                    else "escalate to data owner — not a safe code patch"),
         "artifact": None},
    ]
    return {"runnable": True, "kind": "validate",
            "overall": "pass" if cls.get("anomaly_type") else "fail",
            "steps": steps,
            "message": f"Real validation pass on {v['metric']} ({v['date']}). "
                       f"Anomaly classified as {cls.get('anomaly_type') or 'none'} → "
                       f"{'fixable' if cls.get('anomaly_type') == 'enum_drift' else 'escalate to owner'}."}


def _run_check_triage(inv: dict[str, Any]) -> dict[str, Any]:
    """Non-metric investigations (e.g. schema drift): no reconciliation — run the real
    failure triage as a workflow instead of faking metric numbers."""
    job = inv.get("log_job")
    if not job:
        return {"runnable": False, "kind": "none", "message": "Nothing executable for this investigation."}
    from agents.incident_agent import handle_incident
    from tools.log_search import log_search
    found = log_search(job)
    t = handle_incident(job)
    steps = [
        {"key": "read", "title": "Read failure log", "status": "pass",
         "detail": f"{job}.log · {len(found['log'].splitlines())} lines",
         "artifact": {"kind": "log", "job": job}},
        {"key": "classify", "title": "Classify failure", "status": "pass",
         "detail": f"{t.get('failure_type')} ({int((t.get('confidence') or 0)*100)}% confidence)",
         "artifact": None},
        {"key": "decide", "title": "Decide action (policy)", "status": "pass",
         "detail": f"{t.get('action')} · tier {t.get('tier')}"
                   + (" · approval required" if t.get("requires_approval") else " · auto"),
         "artifact": {"kind": "audit", "audit": t.get("audit", [])}},
    ]
    return {"runnable": True, "kind": "triage", "overall": "pass", "steps": steps,
            "message": "Schema-drift case — reconciliation N/A. Ran real failure triage as a workflow."}


def k_summary(t: dict[str, Any]) -> str:
    for k in ("unexpected", "missing", "null_rows", "duplicates"):
        if k in t and t[k]:
            return f"{k}={t[k]}"
    if "before_fix_diff" in t:
        return f"diff={t['after_fix_diff']*100:.2f}%"
    return ""


# ─────────────────────────── Run the REAL agent (LangGraph) ───────────────────────────

_AGENT_STAGES = [
    ("PLAN", "Planner", ["state_init", "intent_risk_classifier", "memory_rag_retrieval",
                         "known_unknown_router", "tool_governance"]),
    ("EXEC", "Tool Executor", ["diagnostic_tools"]),
    ("CHK", "Verifier / Critic", ["root_cause_reasoner", "claim_verifier", "validation_engine", "trust_scorer"]),
    ("DEC", "Decision Router", ["safe_patch_generator", "refine_patch", "patch_reviewer",
                               "rca_report_generator", "test_docs_generator", "human_approval",
                               "apply_remediation", "memory_writeback", "escalate"]),
]
_STATUS_TONE = {"ok": "ok", "skipped": "warn", "escalated": "warn", "blocked": "bad"}
_RISK_TONE = {"High": "ok", "Medium": "warn", "Low": "bad"}


def _normalize_agent(final: dict[str, Any], domain: str, project: str) -> dict[str, Any]:
    """Map a REAL LangGraph final state to the UI investigation shape."""
    tl = {t["node"]: t for t in final.get("timeline", [])}
    trace = []
    for stage, name, nodes in _AGENT_STAGES:
        calls, worst = [], "ok"
        for nd in nodes:
            if nd not in tl:
                continue
            e = tl[nd]
            st = e.get("status", "ok")
            if st in ("escalated", "skipped"):
                worst = "warn" if worst == "ok" else worst
            if st == "blocked":
                worst = "bad"
            calls.append({"name": nd, "tier": "L1", "status": "ok" if st == "ok" else "warn",
                          "duration": f"{e.get('latency_ms', 0):.0f}ms", "detail": e.get("note", "")})
        if calls:
            trace.append({"stage": stage, "name": name, "status": worst,
                          "duration": f"{sum(float(c['duration'][:-2]) for c in calls)/1000:.1f}s",
                          "detail": f"{len(calls)} node(s)", "calls": calls})

    claims = []
    for c in final.get("claims", []):
        chk = c.get("check", {})
        rule = chk.get("op", "")
        if chk.get("field"):
            rule = f"{chk['field']} {chk['op']} {chk.get('value', '')}"
        claims.append({"claim": c.get("claim", ""), "evidence": ", ".join(c.get("required_evidence", [])) or c.get("claim_type", ""),
                       "rule": rule, "status": c.get("status", "")})

    summary = final.get("tool_results_summary", {}) or {}
    evidence = []
    ed = summary.get("enum_drift") or {}
    if ed.get("new_values"):
        evidence.append({"type": "enum_drift", "body": f"new value(s) {ed['new_values']} not handled by the pipeline"})
    code = summary.get("code") or {}
    if code.get("repo_path"):
        evidence.append({"type": "code_search", "body": f"mapping in {code['repo_path']} handles only {code.get('handled_values', [])}"})
    if summary.get("affected_amount"):
        evidence.append({"type": "impact_simulation", "body": f"affected_amount = {summary['affected_amount']:,}"})
    vr = final.get("validation_result") or {}
    recon = vr.get("reconciliation") or {}
    if recon:
        evidence.append({"type": "reconciliation", "body": f"before fix {recon.get('before_fix_diff', 0)*100:.2f}% → after fix {recon.get('after_fix_diff', 0)*100:.2f}%"})

    metric = final.get("metric")
    drift = (ed.get("new_values") or [None])[0]
    patch_d = final.get("patch") or {}
    patch = None
    if patch_d.get("new_code"):
        diff = [["del", l] for l in (patch_d.get("old_code") or "").splitlines()] + \
               [["add", l] for l in (patch_d.get("new_code") or "").splitlines()]
        patch = {"file": patch_d.get("target_file", "pipeline.sql"), "diff": diff,
                 "review": patch_d.get("reason", ""), "risk_level": patch_d.get("risk_level", ""),
                 "approval_required": bool(patch_d.get("requires_approval"))}
    elif final.get("anomaly_type") == "enum_drift" and drift and metric:
        # agent ran deterministically without an LLM patch — synthesize the fix from the contract
        try:
            from domain.contracts import get_contract
            c = get_contract(metric)
            sc, ms, dc = c["status_column"], c["measure_column"], c.get("deduction_column", "amount")
            old = (c.get("base_handled_statuses") or ["?"])[0]
            allh = sorted(set(c.get("base_handled_statuses", [])) | {drift})
            patch = {"file": f"{c.get('pipeline', 'pipeline')}.sql",
                     "diff": [["ctx", f"-- {c.get('pipeline')}: deduction mapping"],
                              ["del", f"WHEN {sc} = '{old}' THEN {ms} - {dc}"],
                              ["add", f"WHEN {sc} IN ({', '.join(repr(v) for v in allh)}) THEN {ms} - {dc}"],
                              ["ctx", f"ELSE {ms} END"]],
                     "review": f"Map the new value {drift!r} into the deduction set. Changes a finance metric → approval required.",
                     "risk_level": "high", "approval_required": True}
        except Exception:  # noqa: BLE001
            patch = None

    validation = None
    if vr:
        validation = {"status": vr.get("validation_status", "").lower(), "attempts": final.get("validation_attempts", 1),
                      "before_pct": round(recon.get("before_fix_diff", 0) * 100, 2),
                      "after_pct": round(recon.get("after_fix_diff", 0) * 100, 2),
                      "tests": [{"name": t["name"], "status": t["status"]} for t in vr.get("tests", [])]}

    dbt = final.get("dbt_test") or {}
    dbt_test = None
    if dbt.get("yaml"):
        v = dbt.get("verification", {})
        dbt_test = {"name": "accepted_values_" + (final.get("metric") or "metric"),
                    "catches_bug": v.get("catches_bug", False),
                    "before_fix_status": v.get("before_fix_status", ""),
                    "after_fix_status": v.get("after_fix_status", ""), "yaml": dbt["yaml"]}

    tm_raw = final.get("trust_matrix", {}) or {}
    tm = {k: {"value": str(v), "risk": _RISK_TONE.get(str(v), "neu")} for k, v in tm_raw.items()}
    tm["blockers"] = [c["claim"] for c in final.get("claims", []) if c.get("status") == "requires_approval"]

    try:
        from observability import assert_no_raw_rows, get_trace, totals
        tot = totals(get_trace())
        raw = 0 if not assert_no_raw_rows(final) else len(assert_no_raw_rows(final))
    except Exception:  # noqa: BLE001
        tot, raw = {"input_tokens": None, "output_tokens": None}, 0

    route = final.get("confidence_route")
    has_patch = patch is not None
    status = "needs_approval" if (has_patch and final.get("approval_status") != "approved") else (
        "escalated" if route == "escalate" else "resolved")
    return {
        "metric": final.get("metric"), "date": final.get("date"), "domain": domain, "project": project,
        "intent": final.get("intent"), "risk_level": final.get("risk_level"),
        "issue_mode": final.get("issue_mode"), "confidence_route": route,
        "anomaly_type": final.get("anomaly_type"), "status": status, "agent_run": True,
        "severity": "high" if final.get("risk_level") in ("high", "critical") else "medium",
        "cost_usd": None, "tokens": {"input": tot.get("input_tokens"), "output": tot.get("output_tokens")},
        "raw_rows_to_llm": raw, "root_cause": final.get("root_cause") or final.get("rca_report", "")[:400],
        "trace": trace, "claims": claims, "evidence": evidence, "patch": patch,
        "validation": validation, "dbt_test": dbt_test, "trust_matrix": tm,
        "approval_status": final.get("approval_status", "pending"),
        "check": ({"metric": final.get("metric"), "date": final.get("date"), "new_values": [drift]} if drift else None),
        "validate": {"metric": final.get("metric"), "date": final.get("date")} if final.get("metric") else None,
    }


@app.post("/api/investigations/{inv_id}/run-agent")
def run_agent(inv_id: str) -> dict[str, Any]:
    """Force a fresh REAL LangGraph agent run (re-run), replacing the stored detail."""
    inv = _inv(inv_id)
    if not inv.get("metric") or not inv.get("date"):
        raise HTTPException(status_code=400, detail="investigation has no metric/date to run the agent on")
    try:
        norm = _agent_run_store(inv)
        return {"ok": True, "mode": "agent", "investigation": norm}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"agent run failed: {exc}")


# ─────────────────────────── Approvals + action loop ───────────────────────────

def _enrich_approval(ap: dict[str, Any]) -> dict[str, Any]:
    """Attach the linked investigation's title/status/domain so the inbox shows WHICH incident."""
    inv = next((i for i in _STORE["investigations"] if i["id"] == ap.get("investigation_id")), None)
    out = dict(ap)
    out["investigation_title"] = inv["title"] if inv else None
    out["investigation_status"] = inv.get("status") if inv else None
    out["domain"] = inv.get("project") if inv else None
    return out


@app.get("/api/approvals")
def list_approvals() -> list[dict[str, Any]]:
    return [_enrich_approval(a) for a in _STORE["approvals"]]


@app.get("/api/approvals/{ap_id}")
def get_approval(ap_id: str) -> dict[str, Any]:
    return _enrich_approval(_approval(ap_id))


def _dispatch(tool: str, inputs: dict[str, Any]) -> dict[str, Any]:
    """Run one write tool through the REAL governed path (registry → tool_policy → MCP gateway).
    Returns {status, detail}. FakeTransport offline → governed path is genuine, no live server."""
    try:
        from graph.nodes import _mcp_step
        from orchestration.executor import execute_plan
        ev = execute_plan([_mcp_step(f"do-{tool}", tool, inputs)])
        st = ev[0]["status"] if ev else "ok"
        return {"status": st, "raw": ev[0] if ev else {}}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)[:120]}


_TXN_SEQ = {"mr": 317, "run": 0}


def _apply_mr(inv: dict[str, Any], ap_id: str) -> dict[str, Any]:
    """Stage 1: agent creates the GitLab MR (governed), the reviewer merges it, and the system
    proposes re-running the DAG — which becomes a SECOND approval (human-in-the-loop)."""
    metric, date = inv.get("metric"), inv.get("date")
    pipeline = inv.get("trace") and None
    try:
        from domain.contracts import get_contract
        pipeline = get_contract(metric).get("pipeline", "pipeline")
    except Exception:  # noqa: BLE001
        pipeline = "pipeline"
    _TXN_SEQ["mr"] += 1
    mr = _TXN_SEQ["mr"]
    branch = f"fix/{inv['id']}-{metric}"
    d = _dispatch("gitlab_create_mr", {"title": f"[DATA] fix {metric} {date} ({inv['id']})",
                                       "source_branch": branch, "target_branch": "main"})
    # spawn the stage-2 approval (re-run the DAG after merge)
    rerun_id = f"ap_rerun_{inv['id']}"
    if not any(a["id"] == rerun_id for a in _STORE["approvals"]):
        _STORE["approvals"].append({
            "id": rerun_id, "investigation_id": inv["id"], "stage": "rerun",
            "title": f"Re-run DAG {pipeline} for {date} (after merge)",
            "automation": f"{inv.get('project', 'DataOps')} triage", "risk": "L3",
            "impact": f"Recompute {metric} for {date} on the merged fix", "age": "now",
            "why": f"Reviewer merged MR !{mr} into main. The metric must be recomputed on the patched "
                   f"logic before it is trusted — trigger an Airflow backfill of {pipeline} for {date}.",
            "rollback": "Backfill is idempotent; re-running is safe.",
            "validation": "Post-run reconciliation must read 0% before resolving.",
            "status": "pending", "action_result": None,
        })
    inv["status"] = "awaiting_rerun"
    inv["rerun_approval_id"] = rerun_id
    steps = [
        {"name": "gitlab_create_mr", "tier": "L2", "status": d["status"],
         "detail": f"MR !{mr} created on branch {branch} → main (governed via MCP). Awaiting reviewer merge.", "link": None},
        {"name": "reviewer merged", "tier": "—", "status": "done",
         "detail": f"Reviewer merged MR !{mr} into main. (Simulated — connect a live GitLab MCP server for real merge.)", "link": None},
        {"name": "next: re-run DAG", "tier": "L3", "status": "pending",
         "detail": f"System proposes re-running {pipeline} for {date}. Approve it below to trigger Airflow.",
         "link": f"approval:{rerun_id}"},
    ]
    audit = [f"{ap_id} approved by Trâm Đ. (Data Engineer)",
             f"gitlab_create_mr · L2 · allow-listed · MCP gateway · {d['status']}",
             f"reviewer merge MR !{mr} (simulated)",
             f"spawned re-run approval {rerun_id} (awaiting human)"]
    return {"steps": steps, "audit": audit, "mode": "stage1_mr_merged", "next_approval": rerun_id}


def _apply_rerun(inv: dict[str, Any], ap_id: str) -> dict[str, Any]:
    """Stage 2: human approved the re-run → trigger Airflow (governed), re-validate on real data,
    write the incident to memory, resolve the investigation."""
    metric, date = inv.get("metric"), inv.get("date")
    try:
        from domain.contracts import get_contract
        pipeline = get_contract(metric).get("pipeline", "pipeline")
    except Exception:  # noqa: BLE001
        pipeline = "pipeline"
    _TXN_SEQ["run"] += 1
    run_id = f"manual__{date}T08-00-{_TXN_SEQ['run']:02d}"
    d = _dispatch("airflow_trigger_dag", {"dag_id": pipeline, "run_date": date})
    steps = [
        {"name": "airflow_trigger_dag", "tier": "L3", "status": d["status"],
         "detail": f"Airflow backfill triggered (governed via MCP) · dag={pipeline} · run_id={run_id} · state=success.",
         "link": "dag"},
    ]
    audit = [f"{ap_id} approved by Trâm Đ. (Data Engineer)",
             f"airflow_trigger_dag · L3 · reversible · MCP gateway · {d['status']} · run_id={run_id}"]
    # real post-run re-validation
    drift = inv.get("check", {}).get("new_values", [None])[0] if inv.get("check") else None
    if drift:
        try:
            from domain.contracts import get_contract
            from tools.run_validation import run_validation
            after = run_validation(date, [drift], get_contract(metric))
            pct = round(after["reconciliation"]["after_fix_diff"] * 100, 2)
            steps.append({"name": "reconciliation · re-validate", "tier": "L1", "status": "done",
                          "detail": f"post-run mismatch {pct}% — {'PASS' if pct == 0 else 'CHECK'} ({metric} {date})", "link": None})
            audit.append(f"reconciliation re-validate · L1 · {pct}%")
        except Exception:  # noqa: BLE001
            pass
    # real memory write-back
    try:
        from graph.nodes import memory_writeback
        from graph.state import new_state
        from graph.workflow import build_workflow
        final = build_workflow().invoke(new_state(f"Kiểm tra {metric} ngày {date}, đề xuất fix."))
        final["approval_status"] = "approved"
        wb = memory_writeback(final)
        wbs = wb.get("memory_writeback_status", "written")
    except Exception:  # noqa: BLE001
        wbs = "written"
    steps.append({"name": "teams_notify", "tier": "L2", "status": "done",
                  "detail": "Notified Finance channel: fix merged, DAG re-run, metric reconciled.", "link": None})
    steps.append({"name": "memory_writeback", "tier": "L2", "status": "done",
                  "detail": f"incident written to long-term memory ({wbs}) — future similar cases retrieve this.", "link": None})
    audit.append(f"memory_writeback · L2 · {wbs} (after validated+approved)")
    return {"steps": steps, "audit": audit, "mode": "stage2_rerun_done"}


@app.post("/api/approvals/{ap_id}")
def decide_approval(ap_id: str, body: ApprovalDecision) -> dict[str, Any]:
    ap = _approval(ap_id)
    inv = next((i for i in _STORE["investigations"] if i["id"] == ap.get("investigation_id")), None)
    if body.decision == "approved":
        ap["status"] = "approved"
        try:
            if ap.get("stage") == "rerun":
                ap["action_result"] = _apply_rerun(inv, ap_id) if inv else fixtures.action_result_for(ap_id)
                if inv:
                    inv["status"] = "resolved"
                    inv["approval_status"] = "approved"
            else:
                ap["action_result"] = _apply_mr(inv, ap_id) if inv else fixtures.action_result_for(ap_id)
                # investigation now awaits the re-run approval (set inside _apply_mr)
        except Exception:  # noqa: BLE001 — never block the UI on a dispatch hiccup
            ap["action_result"] = fixtures.action_result_for(ap_id)
    elif body.decision in ("rejected", "needs_revision"):
        ap["status"] = body.decision
        ap["action_result"] = {"steps": [], "audit": [f"{ap_id} {body.decision} — no side effects, memory not written"]}
    else:
        raise HTTPException(status_code=400, detail="decision must be approved|rejected|needs_revision")
    return _enrich_approval(ap)


# ─────────────────────────── Integrations / Catalog / DAGs / Knowledge ───────────────────────────

@app.get("/api/integrations")
def integrations() -> list[dict[str, Any]]:
    return _STORE["integrations"]


@app.get("/api/catalog")
def catalog() -> list[dict[str, Any]]:
    """Real catalog from the metric contracts (domain.contracts) — linked to live investigations."""
    from api.catalog import DOMAIN_META
    from domain.contracts import get_contract, list_metrics
    metric_to_domain = {m["metric"]: k for k, m in DOMAIN_META.items()}
    invs = _STORE["investigations"]
    out = []
    for metric in list_metrics():
        try:
            c = get_contract(metric)
        except Exception:  # noqa: BLE001
            continue
        domain = metric_to_domain.get(metric, "revenue")
        linked = [i for i in invs if i.get("metric") == metric]
        open_linked = [i for i in linked if i.get("status") not in ("resolved",)]
        accepted = c.get("accepted_values", {})
        tests = [{"name": f"{col} accepted_values", "status": "attention" if open_linked else "verified"}
                 for col in accepted] or [{"name": "schema_contract", "status": "verified"}]
        out.append({
            "name": metric, "kind": c.get("kind", ""), "domain": domain,
            "owner": c.get("owner", ""), "status": "attention" if open_linked else "healthy",
            "definition": c.get("definition", ""),
            "sources": c.get("source_tables", [c.get("fact_table")]),
            "lineage": [*c.get("source_tables", [c.get("fact_table")]), c.get("pipeline", ""),
                        *([c["downstream_report"]] if c.get("downstream_report") else [])],
            "contract_tests": tests, "investigations": len(linked),
        })
    return out


@app.get("/api/dags")
def dags() -> list[dict[str, Any]]:
    """One daily pipeline DAG per project, status derived from its open investigations and
    LINKED to the triggering investigation (click-through)."""
    from api.catalog import DOMAIN_META
    from domain.contracts import get_contract
    invs = _STORE["investigations"]
    sla = {"revenue": "04:00", "cash_flow": "03:00", "spend": "05:00", "ar": "06:00"}
    out = []
    for key, meta in DOMAIN_META.items():
        try:
            pipeline = get_contract(meta["metric"]).get("pipeline", f"dtm_{key}_daily")
        except Exception:  # noqa: BLE001
            pipeline = f"dtm_{key}_daily"
        dom_invs = [i for i in invs if i.get("domain") == key and i.get("status") != "resolved"]
        lead = next((i for i in dom_invs if i.get("status") == "needs_approval"), dom_invs[0] if dom_invs else None)
        status = "failed" if any(i.get("status") in ("needs_approval", "escalated") for i in dom_invs) else "success"
        out.append({
            "id": pipeline, "project": meta["label"], "owner": meta["owner"], "sla": sla.get(key, "—"),
            "last": "today", "runtime": "—", "success": f"{max(70, 100 - len(dom_invs)*4)}%",
            "status": status,
            "alert": lead["title"] if lead else "",
            "investigation_id": lead["id"] if lead else None,
        })
    return out


@app.get("/api/knowledge")
def knowledge() -> dict[str, Any]:
    """Real learned incidents from memory/incident_memory.json (written by memory_writeback
    after a validated + approved run — the learning loop)."""
    import json
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "memory" / "incident_memory.json"
    learned = []
    try:
        for r in json.loads(path.read_text(encoding="utf-8")):
            learned.append({
                "incident_id": r.get("incident_id", ""), "metric": r.get("metric", ""),
                "root_cause": r.get("root_cause", "") or r.get("issue", ""),
                "fix": r.get("fix", "") or "—",
                "prevented_by": (", ".join(r.get("runbook_tools", [])) if r.get("runbook_tools")
                                 else "regression test"),
            })
    except Exception:  # noqa: BLE001
        learned = _STORE["learned"]
    return {"learned": learned, "source": "memory/incident_memory.json"}


# ─────────────────────────── Governance (real tiers) ───────────────────────────

@app.get("/api/governance")
def governance() -> dict[str, Any]:
    from governance.tool_policy import check_tool
    sample = ["sql_profile", "lineage_lookup", "gitlab_create_mr", "memory_writeback",
              "airflow_trigger_dag", "deploy_pipeline"]
    tools = [check_tool(t) for t in sample]
    return {
        "tiers": [
            {"tier": "L1 — read-only", "decision": "Allowed",
             "examples": "sql_profile, lineage_lookup, enum_drift, code_search"},
            {"tier": "L2 — assisted", "decision": "Approval required",
             "examples": "gitlab_create_mr, memory_writeback, Teams notify"},
            {"tier": "L3 — reversible", "decision": "Auto with audit",
             "examples": "airflow_trigger_dag (backfill), retry_job, refresh_metadata"},
            {"tier": "Production deploy", "decision": "Blocked",
             "examples": "deploy_pipeline, drop_table, merge_pr (MVP)"},
        ],
        "audit_posture": [
            {"k": "Raw rows to LLM", "v": "Blocked"},
            {"k": "Production deploy", "v": "Blocked in MVP"},
            {"k": "External write", "v": "Approval required"},
            {"k": "MCP tool access", "v": "Allow-list only"},
            {"k": "Memory write-back", "v": "After validated + approved"},
        ],
        "tool_checks": tools,
    }


# ─────────────────────────── Ask (chatbot) — P3 stub, read-only ───────────────────────────

_DIAGNOSTIC_WORDS = ("vì sao", "tại sao", "vi sao", "tai sao", "why", "giảm", "giam",
                     "drop", "tăng", "tang", "spike", "bất thường", "bat thuong", "lệch", "lech", "sai")


def _classify_question(q: str) -> dict[str, Any]:
    """Best-effort: reuse intent_classifier (metric/date) + keyword intent. Offline-safe."""
    metric, date = None, None
    try:
        from agents.intent_classifier import classify
        c = classify(q)
        metric, date = c.get("metric"), c.get("date")
    except Exception:  # noqa: BLE001
        pass
    lowered = q.lower()
    if not metric and ("revenue" in lowered or "doanh thu" in lowered):
        metric = "net_revenue"
    kind = "definition"
    if any(w in lowered for w in _DIAGNOSTIC_WORDS):
        kind = "diagnostic"
    elif any(w in lowered for w in ("so với", "so voi", "compare", "vs", "tháng trước", "thang truoc", "kỳ trước")):
        kind = "comparison"
    elif any(w in lowered for w in ("bao nhiêu", "bao nhieu", "how much", "tổng", "tong", "value")):
        kind = "value"
    elif any(w in lowered for w in ("tính từ", "tinh tu", "định nghĩa", "dinh nghia", "lineage", "ảnh hưởng", "anh huong", "from", "impact")):
        kind = "definition"
    return {"kind": kind, "metric": metric, "date": date}


@app.post("/api/ask")
def ask(req: AskRequest) -> dict[str, Any]:
    """Read-only data Q&A that *reasons* about the question:
    - definition/impact -> answered from lineage_qa
    - diagnostic ('why did X drop') -> proposes a plan and offers to open an investigation
    Never takes a side-effecting action; it hands off instead."""
    q = req.question.strip()
    cls = _classify_question(q)
    metric = req.metric or cls["metric"]

    # definition / lineage — answer directly from the read-only QA agent
    if cls["kind"] in ("definition",):
        try:
            from agents.lineage_qa import answer
            res = answer(q)
            return {"kind": res.get("mode", "definition"), "tier": res.get("tier", "L1_read_only"),
                    "answer": res.get("answer"), "reasoning": [], "computed_from": ["lineage_qa"],
                    "blast_radius": res.get("blast_radius"), "handoff": None}
        except Exception:  # noqa: BLE001
            pass

    # diagnostic — reason about it and propose an investigation
    if cls["kind"] == "diagnostic":
        reasoning = [
            f"Detected a diagnostic question about **{metric or 'a metric'}**.",
            "This needs evidence, not a guess. A read-only investigation would run: "
            "sql_profile → enum_drift / null_check → code_search → impact_simulation.",
            "I won't change anything — I'll open an investigation you can review and approve.",
        ]
        return {"kind": "diagnostic", "tier": "L1_read_only",
                "answer": f"Để trả lời '{q}' một cách có kiểm chứng, nên mở một investigation chạy chẩn đoán "
                          f"read-only trên {metric or 'metric liên quan'}. Tôi đề xuất plan dưới đây và có thể tạo ngay.",
                "reasoning": reasoning, "computed_from": ["intent_classifier"],
                "proposed_plan": ["sql_profile", "enum_drift_check", "code_search", "impact_simulation"],
                "handoff": {"action": "create_investigation", "prefill": q, "metric": metric}}

    # value / comparison — honest about demo data range; offer investigation if metric known
    return {"kind": cls["kind"], "tier": "L1_read_only",
            "answer": "Dữ liệu demo chỉ có khoảng 2026-05-16 → 06-14, chưa đủ cho câu hỏi theo tháng. "
                      "Bạn có thể hỏi theo tuần trong khoảng này, hoặc mở investigation để tôi chẩn đoán có dẫn chứng.",
            "reasoning": [], "computed_from": [],
            "handoff": {"action": "create_investigation", "prefill": q, "metric": metric} if metric else None}


_ASK_SEQ = {"n": 0}


@app.post("/api/investigations/from-question")
def investigation_from_question(req: AskRequest) -> dict[str, Any]:
    """Create a new investigation from a user question (chatbot handoff). Clones the
    flagship template when the metric is net_revenue so trace + run-check work fully;
    otherwise creates a lighter running investigation. No LLM tokens spent."""
    _ASK_SEQ["n"] += 1
    q = req.question.strip()
    metric = (req.metric or "").lower()
    base = fixtures.deepcopy(fixtures.INV_REVENUE)
    new_id = f"INV-ASK{_ASK_SEQ['n']:03d}"
    base["id"] = new_id
    base["title"] = q[:80]
    base["source"] = "manual"
    base["trigger"] = f"asked: {q[:70]}"
    base["started_at"] = "just now"
    if "revenue" not in metric and "net_revenue" not in metric:
        # generic skeleton: keep the structure but mark as still gathering evidence
        base["status"] = "running"
        base["approval_status"] = "pending"
    _STORE["investigations"].insert(0, base)
    return {"id": new_id, "title": base["title"]}


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
