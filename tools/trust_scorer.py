"""trust_scorer — dựng Trust Matrix + quyết định có được final report hay phải human review (§14.4).

Trust Matrix phân biệt phần chắc chắn (technical) vs phần cần approval (business).
ready_for_report = validation PASS AND không có critical unsupported claim AND không contradiction.
"""

from __future__ import annotations

from typing import Any

from tools.contradiction_checker import check_contradictions


def _claim_status(claims: list[dict], claim_id: str) -> str:
    for c in claims:
        if c.get("claim_id") == claim_id:
            return c.get("status", "pending")
    return "missing"


def score(state: dict) -> dict[str, Any]:
    claims = state.get("claims", []) or []
    cvr = state.get("claim_verification_result", {}) or {}
    validation = state.get("validation_result", {}) or {}
    pack = state.get("context_pack", {}) or {}
    impact = state.get("impact_analysis", {}) or {}

    validation_pass = validation.get("validation_status") == "PASS"
    has_critical_unsupported = cvr.get("has_critical_unsupported", False)

    # contradiction: số trong impact_analysis vs validation reconciliation phải khớp
    contra = check_contradictions(
        {"after_fix_diff": impact.get("after_fix_diff", 0)},
        {"after_fix_diff": validation.get("reconciliation", {}).get("after_fix_diff", 0)},
        tolerance=1e-6,
    )

    def hi(cond: bool) -> str:
        return "High" if cond else "Low"

    trust_matrix = {
        "metric_definition": hi(bool(pack.get("metric_definition"))),
        "data_anomaly": hi(_claim_status(claims, "C1") == "verified"),
        "code_root_cause": hi(_claim_status(claims, "C2") == "verified"),
        "business_interpretation": "Medium",   # cần Finance approval
        "patch_correctness": hi(validation_pass),
        "deployment_safety": "Medium",          # không auto-deploy
    }

    blockers = []
    if not validation_pass:
        blockers.append("validation chưa PASS")
    if has_critical_unsupported:
        blockers.append("có critical unsupported claim")
    if contra["contradiction_found"]:
        blockers.append("contradiction giữa report và tool result")

    return {
        "trust_matrix": trust_matrix,
        "ready_for_report": not blockers,
        "blockers": blockers,
        "contradiction": contra,
    }
