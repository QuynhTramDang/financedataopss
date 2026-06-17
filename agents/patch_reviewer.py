"""patch_reviewer — review patch về business risk + approval requirement + test cần chạy (§16, FR-011).

Quyết định approval/risk là DETERMINISTIC (thay đổi logic Finance metric → high + cần approval).
LLM (Claude) chỉ bổ sung nhận xét; có fallback khi không có model.
"""

from __future__ import annotations

from typing import Any

from model_router import ProviderError, get_router


def review_patch(patch: dict, contract: dict | None = None, router=None) -> dict[str, Any]:
    """Trả {business_risk, requires_approval, suggested_tests, comment}."""
    # rule: patch chạm logic Finance metric → high risk + approval
    status_col = (contract or {}).get("status_column", "status")
    metric_label = (contract or {}).get("metric", "Finance metric")
    business_risk = "high"
    requires_approval = True
    suggested_tests = [
        f"accepted_values_check({status_col})",
        "revenue_reconciliation_check",
        "null_check",
    ]

    comment = (f"Patch thay đổi mapping `{status_col}` trong {patch.get('target_file')} — "
               f"ảnh hưởng {metric_label}, cần Finance Owner approval.")
    try:
        router = router or get_router()
        out = router.call_structured(
            route="patch_reviewer",
            prompt=f"Nhận xét rủi ro business của patch sau (1-2 câu): {patch}",
            schema={"type": "object", "properties": {"comment": {"type": "string"}},
                    "required": ["comment"], "additionalProperties": False},
            system="Bạn là DE senior review patch logic Finance.",
        )
        comment = out["comment"]
    except (ProviderError, Exception):  # noqa: BLE001 — không model → giữ comment template
        pass

    return {
        "business_risk": business_risk,
        "requires_approval": requires_approval,
        "suggested_tests": suggested_tests,
        "comment": comment,
    }
