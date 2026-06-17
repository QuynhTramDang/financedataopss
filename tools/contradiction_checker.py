"""contradiction_checker — phát hiện mâu thuẫn giữa giá trị report và tool result (§14.6).

Cùng cơ chế so khớp với claim_policy. Nếu report nói khác tool (ngoài tolerance) → block final RCA.
"""

from __future__ import annotations

from typing import Any


def check_contradictions(reported: dict[str, float], tool_values: dict[str, float],
                         tolerance: float = 1e-6) -> dict[str, Any]:
    """So từng field trong `reported` với `tool_values`. Trả {contradiction_found, details}."""
    details = []
    for field, rep in reported.items():
        tool_val = tool_values.get(field)
        if tool_val is None:
            continue
        if abs(rep - tool_val) > tolerance:
            details.append({
                "field": field,
                "report_value": rep,
                "tool_value": tool_val,
                "action": "block_final_report_and_request_review",
            })
    return {"contradiction_found": bool(details), "details": details}
