"""guards — đảm bảo KHÔNG có raw transaction row lọt vào state/LLM (§13, §26 Security).

Quét tool_results_summary tìm dấu hiệu raw row (vd dict có 'txn_id', hoặc key tên 'raw'/'rows').
"""

from __future__ import annotations

from typing import Any

_RAW_KEY_HINTS = ("raw", "rows")
_ROW_FINGERPRINT = "txn_id"


def _scan(obj: Any, violations: list[str], path: str = "") -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() in _RAW_KEY_HINTS and isinstance(v, list) and v:
                violations.append(f"{path}.{k} chứa list (nghi raw rows)")
            if _ROW_FINGERPRINT in obj:
                violations.append(f"{path} chứa '{_ROW_FINGERPRINT}' (raw transaction)")
            _scan(v, violations, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _scan(item, violations, f"{path}[{i}]")


def assert_no_raw_rows(state: dict) -> list[str]:
    """Trả danh sách vi phạm (rỗng = ok). Dùng cho test/CI."""
    violations: list[str] = []
    _scan(state.get("tool_results_summary", {}) or {}, violations, "tool_results_summary")
    return violations
