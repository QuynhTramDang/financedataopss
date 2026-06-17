"""Node của LangGraph workflow.

Step 2 (skeleton): mỗi node là pass-through — ghi một entry vào timeline và set marker tối thiểu
để state chảy qua đủ các bước. Logic thật sẽ được cắm dần vào từng node ở các step sau:
  - intent_risk_classifier   → Step 4
  - memory_rag_retrieval     → Step 3
  - tool_governance          → Step 5
  - diagnostic_tools         → Step 6
  - root_cause_reasoner      → Step 7
  - claim_verifier           → Step 8
  - safe_patch / patch_review→ Step 9
  - validation_engine        → Step 10
  - trust_scorer / rca / writeback → Step 11
"""

from __future__ import annotations

from .state import InvestigationState


def _entry(node: str, note: str, status: str = "ok") -> dict:
    return {"timeline": [{"node": node, "status": status, "note": note}]}


def intent_risk_classifier(state: InvestigationState) -> dict:
    # Step 4: phân loại intent/metric/date/risk (model nhỏ + rule override; fallback heuristic).
    from agents.intent_classifier import classify

    data = classify(state["user_request"])
    note = f"intent={data['intent']} · metric={data.get('metric')} · risk={data['risk_level']}"
    if data.get("_fallback"):
        note += f" · {data['_fallback']}"
    return {
        "intent": data["intent"],
        "metric": data.get("metric"),
        "date": data.get("date"),
        "risk_level": data["risk_level"],
        **_entry("intent_risk_classifier", note),
    }


def memory_rag_retrieval(state: InvestigationState) -> dict:
    # Step 3: retrieve memory + RAG thật → Runtime Context Pack + quyết known/unknown.
    from agents.context_retriever import build_context

    result = build_context(dict(state))
    pack = result["context_pack"]
    n_ctx = len(result["retrieved_context"])
    note = f"retrieved {n_ctx} ngữ cảnh · mode={result['issue_mode']}"
    if pack.get("similar_incident"):
        note += f" · {pack['similar_incident']}"
    return {
        "context_pack": pack,
        "retrieved_context": result["retrieved_context"],
        "issue_mode": result["issue_mode"],
        **_entry("memory_rag_retrieval", note),
    }


def known_unknown_router(state: InvestigationState) -> dict:
    # Node chỉ log; quyết định nhánh nằm ở conditions.route_known_unknown.
    mode = state.get("issue_mode") or "known"
    return {"issue_mode": mode, **_entry("known_unknown_router", f"mode={mode}")}


def tool_governance(state: InvestigationState) -> dict:
    # Step 5: rule engine — map risk→action+tier (SQL bị enforce ở diagnostic node, Step 6).
    from governance import decide_risk_action

    decision = decide_risk_action(state.get("risk_level") or "medium")
    note = (f"action={decision['allowed_action']} · tier={decision['tier']} · "
            f"approval={'required' if decision['requires_approval'] else 'no'}")
    return {"governance": decision, **_entry("tool_governance", note)}


def diagnostic_tools(state: InvestigationState) -> dict:
    # Step 6: chạy diagnostic thật (sql_profile qua governance, enum_drift, code_search, lineage).
    from agents import diagnostic_planner

    summary = diagnostic_planner.run(dict(state))
    drift = summary.get("enum_drift", {})
    new_vals = drift.get("new_values", [])
    note = (f"profile {len(summary.get('group_profile', {}))} nhóm · "
            f"enum_drift={new_vals or 'none'} · "
            f"missing_in_code={summary['code'].get('missing_values') or 'none'}")
    return {
        "tool_plan": summary.get("tools_used", []),
        "plan_steps": summary.get("plan_steps", []),
        "evidence": summary.get("evidence", []),
        "tool_results_summary": summary,
        **_entry("diagnostic_tools", note),
    }


def root_cause_reasoner(state: InvestigationState) -> dict:
    # Step 7: confidence/route từ evidence (deterministic); narrative do LLM/template.
    from agents.root_cause_reasoner import reason

    # cho phép test ép escalate qua state; mặc định suy luận từ evidence
    if state.get("confidence_route") == "escalate" and not state.get("tool_results_summary"):
        return _entry("root_cause_reasoner", "forced escalate (no evidence)", status="escalated")

    result = reason(dict(state))
    note = (f"anomaly={result['anomaly_type']} · confidence={result['confidence']} · "
            f"route={result['confidence_route']}")
    if result["root_cause"]:
        note += f" · {result['root_cause'][:50]}"
    return {
        "hypotheses": result["hypotheses"],
        "root_cause": result["root_cause"],
        "anomaly_type": result["anomaly_type"],
        "candidate_issue": result.get("candidate_issue"),
        "confidence_route": result["confidence_route"],
        **_entry("root_cause_reasoner", note),
    }


def claim_verifier(state: InvestigationState) -> dict:
    # Step 8: tách claim (claim_verifier) + rule engine so khớp (claim_policy).
    from governance.claim_policy import verify_claims
    from tools.claim_verifier import build_claims

    claims = build_claims(dict(state))
    result = verify_claims(claims, state.get("tool_results_summary", {}) or {})
    note = (f"verified={result['verified']} · unsupported={result['unsupported']} · "
            f"requires_approval={result['requires_approval']}")
    return {
        "claims": result["claims"],
        "claim_verification_result": {k: v for k, v in result.items() if k != "claims"},
        **_entry("claim_verifier", note),
    }


def safe_patch_generator(state: InvestigationState) -> dict:
    # Step 9: impact simulation (SQL thật) + sinh remediation theo fix-strategy registry.
    from domain.contracts import get_contract
    from remediation.strategies import build_remediation
    from tools.generate_patch import generate_patch
    from tools.impact_simulation import simulate_impact

    summary = state.get("tool_results_summary", {}) or {}
    new_values = summary.get("enum_drift", {}).get("new_values", [])
    txn_date = state["date"]
    contract = get_contract(state.get("metric"))

    impact = simulate_impact(txn_date, new_values, contract)
    # patch do strategy của anomaly sinh ra (pluggable); fallback generate_patch nếu chưa có
    rem = build_remediation(state) or {}
    patch = rem.get("details", {}).get("patch") if rem.get("kind") == "code_patch" else None
    if not patch:
        patch = generate_patch(summary)
    note = (f"strategy={rem.get('strategy', 'expand_mapping')} · "
            f"before={impact['before_fix_diff']:.4f} → after={impact['after_fix_diff']:.4f}")
    return {
        "impact_analysis": impact,
        "patch": patch,
        "remediation": rem,
        "fix_values": new_values,          # tập fix ban đầu (reflection có thể broaden)
        **_entry("safe_patch_generator", note),
    }


def refine_patch(state: InvestigationState) -> dict:
    # Reflection: validation FAIL → critique + broaden tập fix tới mọi status cần xử lý, regenerate patch.
    from domain.contracts import get_contract
    from tools.generate_patch import generate_patch
    from tools.impact_simulation import simulate_impact

    summary = state.get("tool_results_summary", {}) or {}
    contract = get_contract(state.get("metric"))
    base = set(contract.get("base_handled_statuses", []))
    profile = summary.get("group_profile", {}) or {}
    # broaden: mọi status quan sát được, trừ base đã xử lý và giá trị "không hoàn" (NONE)
    observed = sorted({v for v in profile if v and v not in base and str(v).upper() != "NONE"})
    attempts = state.get("validation_attempts", 0) + 1

    code = dict(summary.get("code", {}))
    handled = set(code.get("handled_values", []))
    code["missing_values"] = sorted(set(observed) - handled)
    patch = generate_patch({**summary, "code": code})
    impact = simulate_impact(state["date"], observed, contract)
    note = f"reflection #{attempts}: broaden fix → {observed} (re-validate)"
    return {
        "fix_values": observed,
        "validation_attempts": attempts,
        "patch": patch,
        "impact_analysis": impact,
        **_entry("refine_patch", note),
    }


def patch_reviewer(state: InvestigationState) -> dict:
    # Step 9: review business risk + approval requirement (deterministic + LLM comment).
    from agents.patch_reviewer import review_patch

    from domain.contracts import get_contract
    review = review_patch(state.get("patch") or {}, get_contract(state.get("metric")))
    note = f"risk={review['business_risk']} · approval={review['requires_approval']}"
    return {"patch_review": review, **_entry("patch_reviewer", note)}


def validation_engine(state: InvestigationState) -> dict:
    # Step 10: chạy validation deterministic (reconciliation từ SQL thật).
    from domain.contracts import get_contract
    from tools.run_validation import run_validation

    summary = state.get("tool_results_summary", {}) or {}
    # dùng fix_values (reflection có thể đã broaden); fallback enum_drift cho lần đầu
    new_values = state.get("fix_values") or summary.get("enum_drift", {}).get("new_values", [])
    txn_date = state["date"]

    result = run_validation(txn_date, new_values, get_contract(state.get("metric")))
    note = (f"{result['validation_status']} {result['passed']}/{result['total']} · "
            f"recon {result['reconciliation']['before_fix_diff']:.4f}→"
            f"{result['reconciliation']['after_fix_diff']:.4f}")
    return {"validation_result": result, **_entry("validation_engine", note)}


def trust_scorer(state: InvestigationState) -> dict:
    # Step 11: dựng Trust Matrix + check ready/blockers.
    from tools.trust_scorer import score

    result = score(dict(state))
    note = f"ready={result['ready_for_report']} · blockers={result['blockers'] or 'none'}"
    return {"trust_matrix": result["trust_matrix"], **_entry("trust_scorer", note)}


def rca_report_generator(state: InvestigationState) -> dict:
    # Step 11: sinh RCA markdown từ evidence/validation đã verify.
    from tools.generate_rca_report import generate_rca_report

    rca = generate_rca_report(dict(state))
    return {"rca_report": rca, **_entry("rca_report_generator", f"RCA {len(rca)} ký tự")}


def test_docs_generator(state: InvestigationState) -> dict:
    # Step 11A: sinh dbt test (chặn tái diễn) + docs đề xuất; chứng minh fail-then-pass.
    from domain.contracts import get_contract
    from tools.generate_dbt_test import generate_dbt_test
    from tools.generate_docs import generate_docs

    summary = state.get("tool_results_summary", {}) or {}
    txn_date = state["date"]
    dbt_test = generate_dbt_test(summary, get_contract(state.get("metric")), txn_date)
    docs = generate_docs(dict(state))
    v = dbt_test["verification"]
    note = (f"dbt test catches_bug={v['catches_bug']} "
            f"({v['before_fix_status']}→{v['after_fix_status']})")
    return {"dbt_test": dbt_test, "docs_update": docs, **_entry("test_docs_generator", note)}


def _mcp_step(step_id: str, tool: str, inputs: dict) -> dict:
    from orchestration.registry import get_registry
    return {"id": step_id, "tool": tool, "capability": get_registry().get(tool).capability,
            "reason": "apply remediation", "inputs": inputs, "depends_on": [],
            "expected_evidence": get_registry().get(tool).evidence_type}


def apply_remediation(state: InvestigationState) -> dict:
    # M2: SAU approval → thực thi remediation qua MCP (write tool). Chỉ ở nhánh approved.
    from orchestration.executor import execute_plan
    from tools.notify_teams import notify_teams

    rem = state.get("remediation") or {}
    inv = state.get("investigation_id", "INV-?")
    kind = rem.get("kind")
    details = rem.get("details", {}) or {}
    steps = []

    if kind == "code_patch":
        steps.append(_mcp_step("apply-mr", "gitlab_create_mr", {
            "title": f"[DATA] fix {state.get('metric')} {state.get('date')} ({inv})",
            "description": (state.get("rca_report") or "")[:4000],
            "source_branch": f"fix/{inv}", "target_branch": "main",
        }))
    elif kind == "operational" and details.get("action") == "backfill":
        steps.append(_mcp_step("apply-backfill", "airflow_trigger_dag", {
            "dag_id": details.get("pipeline") or "revenue_daily",
            "run_date": details.get("partition") or state.get("date"),
        }))

    ev = execute_plan(steps) if steps else []
    teams = notify_teams(f"[{inv}] remediation '{rem.get('strategy', 'none')}' dispatched after approval.")
    actions = [{"tool": e["source_tool"], "status": e["status"]} for e in ev]
    note = f"dispatched {len(actions)} action(s) · teams={teams['status']}"
    return {
        "dispatch_result": {"actions": actions, "evidence": ev, "teams": teams},
        **_entry("apply_remediation", note),
    }


def human_approval(state: InvestigationState) -> dict:
    # Không tự deploy: giữ approval_status hiện tại (mặc định 'pending' → chờ human).
    status = state.get("approval_status", "pending")
    return _entry("human_approval", f"approval_status={status}")


def memory_writeback(state: InvestigationState) -> dict:
    # Step 11: CHỈ ghi memory sau approve (§8.3).
    from tools.memory_writeback import write_incident

    res = write_incident(dict(state), state.get("approval_status", ""))
    return {
        "memory_writeback_status": res["status"],
        **_entry("memory_writeback", res["status"]),
    }


def escalate(state: InvestigationState) -> dict:
    # Nhánh không code-fix (low-confidence / data-quality): evidence pack + ĐỀ XUẤT remediation vận hành.
    from remediation.strategies import build_remediation

    rc = state.get("root_cause")
    anomaly = state.get("anomaly_type")
    candidate = state.get("candidate_issue") or {}
    q = (state.get("tool_results_summary", {}) or {}).get("quality_checks", {})
    rem = build_remediation(state)
    rem_line = (f"Đề xuất remediation: {rem['summary']} (kind={rem['kind']}, cần approval)"
                if rem else "Đề xuất remediation: chưa có strategy — cần human điều tra thêm.")
    candidate_line = ""
    if candidate:
        candidate_line = (
            f"Candidate issue definition: {candidate.get('candidate_issue_type')}\n"
            f"Description: {candidate.get('description')}\n"
            f"Evidence pattern: {candidate.get('evidence_pattern')}\n"
            f"Suggested tools: {candidate.get('suggested_tools')}\n"
            "Status: proposed only; human approval required before adding a detector/runbook.\n\n"
        )
    finding = (
        f"# Escalation — {state.get('investigation_id', '?')}\n\n"
        f"Anomaly: {anomaly or 'chưa xác định'}\n"
        f"Finding: {rc or 'Chưa đủ evidence để kết luận root cause.'}\n"
        f"Evidence (quality_checks): {q}\n\n"
        f"{candidate_line}"
        f"{rem_line}\n"
        "KHÔNG tự áp dụng — chờ human approval."
    )
    note = f"anomaly={anomaly or 'unknown'} → escalate · remediation={rem['strategy'] if rem else 'none'}"
    return {
        "approval_status": "needs_revision",
        "rca_report": finding,
        "remediation": rem,
        **_entry("escalate", note, status="escalated"),
    }
