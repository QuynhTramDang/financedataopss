"""generate_docs — sinh đề xuất cập nhật docs/metric dictionary từ fix đã verify.

Guardrail: trả nội dung markdown + path đề xuất (proposed/), không tự ghi đè docs thật.
"""

from __future__ import annotations

from typing import Any


def generate_docs(state: dict) -> dict[str, Any]:
    from domain.contracts import ContractError, get_contract

    summary = state.get("tool_results_summary", {}) or {}
    new_values = summary.get("enum_drift", {}).get("new_values", [])
    patch = state.get("patch", {}) or {}
    metric = state.get("metric") or "metric"
    try:
        contract = get_contract(state.get("metric")) if state.get("metric") else {}
    except ContractError:
        contract = {}
    status_col = contract.get("status_column", "status")
    deduction_col = contract.get("deduction_column", "deduction")
    base = contract.get("base_handled_statuses", [])

    md = f"""# Đề xuất cập nhật Metric Dictionary — {metric}

## Thay đổi
Bổ sung xử lý {status_col} mới: {new_values}.

## Định nghĩa cập nhật
{metric}: {deduction_col} tính cho các giá trị {status_col}:
{', '.join([*base, *new_values])}.

## Nguồn
- Phát hiện qua investigation {state.get('investigation_id', '?')} ngày {state.get('date', '?')}.
- Fix: `{patch.get('new_code')}`
- Cần Finance Owner approval trước khi cập nhật chính thức.
"""
    return {"suggested_path": "proposed/finance_metric_dictionary_update.md", "markdown": md}
