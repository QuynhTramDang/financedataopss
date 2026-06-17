"""claim_verifier — tách kết luận thành các claim có schema kiểm chứng được (§14.2).

Mỗi claim mang sẵn `check` (field/op/value) để rule engine (governance.claim_policy) so khớp
DETERMINISTIC với evidence. Nội dung claim suy từ metric contract (không hardcode payment_txn/net_revenue);
check field giữ generic. LLM (nếu có) chỉ diễn đạt; KHÔNG được tự gán 'verified'.
"""

from __future__ import annotations

from typing import Any

from domain.contracts import ContractError, get_contract


def build_claims(state: dict) -> list[dict[str, Any]]:
    """Sinh danh sách claim từ root_cause + evidence (text theo contract của metric)."""
    summary = state.get("tool_results_summary", {}) or {}
    new_values = summary.get("enum_drift", {}).get("new_values", [])
    target = new_values[0] if new_values else "NEW_VALUE"
    repo = summary.get("code", {}).get("repo_path", "pipeline")

    metric = state.get("metric")
    try:
        contract = get_contract(metric) if metric else {}
    except ContractError:
        contract = {}
    fact_table = contract.get("fact_table", "source table")
    deduction_col = contract.get("deduction_column", "deduction")
    metric_label = metric or "metric"

    return [
        {
            "claim_id": "C1",
            "claim": f"{target} xuất hiện trong {fact_table}",
            "claim_type": "data_fact",
            "required_evidence": ["sql_profile", "enum_drift_check"],
            "check": {"field": "enum_drift.new_values", "op": "contains", "value": target},
            "status": "pending",
        },
        {
            "claim_id": "C2",
            "claim": f"{repo} chưa handle {target}",
            "claim_type": "code_fact",
            "required_evidence": ["code_search"],
            "check": {"field": "code.missing_values", "op": "contains", "value": target},
            "status": "pending",
        },
        {
            "claim_id": "C3",
            "claim": f"Việc này làm {metric_label} overstated (affected_amount > 0)",
            "claim_type": "quantitative",
            "required_evidence": ["sql_profile", "reconciliation_check"],
            "check": {"field": "affected_amount", "op": ">", "value": 0},
            "status": "pending",
        },
        {
            "claim_id": "C4",
            "claim": f"{target} nên được tính vào {deduction_col}",
            "claim_type": "business_decision",
            "required_evidence": ["finance_decision", "human_approval"],
            "check": {"op": "always_requires_approval"},
            "status": "pending",
        },
    ]
