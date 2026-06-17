"""generate_patch — sinh patch nhỏ (replace_block), KHÔNG rewrite cả file (§16).

old_code lấy từ snippet code_search; cột điều kiện được SUY TỪ chính snippet (không hardcode
'refund_status'). new_code mở rộng `<col> = 'X'` → `<col> in ('X', NEW...)`. Target file lấy từ
evidence code_search (không fallback file revenue_daily).
"""

from __future__ import annotations

import re
from typing import Any, Optional

_COND = re.compile(r"(\w+)\s*=\s*'[^']+'")


def generate_patch(summary: dict, target_file: Optional[str] = None) -> dict[str, Any]:
    code = summary.get("code", {})
    old_code = code.get("snippet")
    handled = code.get("handled_values") or []
    missing = code.get("missing_values") or []
    target_file = target_file or code.get("repo_path")

    if not old_code or not _COND.search(old_code):
        # không có đoạn mapping để vá → trả patch không đổi code, vẫn cần review
        return {
            "patch_id": "PATCH-001", "target_file": target_file,
            "change_type": "none", "risk_level": "high", "requires_approval": True,
            "old_code": old_code, "new_code": old_code,
            "reason": "Không tìm thấy đoạn mapping để vá (cần điều tra thêm).",
            "rollback_plan": f"Không thay đổi {target_file}.",
        }

    col = _COND.search(old_code).group(1)            # suy cột điều kiện từ snippet
    all_values = sorted(set(handled) | set(missing))
    in_list = ", ".join(f"'{v}'" for v in all_values)
    new_code = re.sub(rf"{col}\s*=\s*'[^']+'", f"{col} in ({in_list})", old_code, count=1)

    return {
        "patch_id": "PATCH-001",
        "target_file": target_file,
        "change_type": "replace_block",
        "risk_level": "high",
        "requires_approval": True,
        "old_code": old_code,
        "new_code": new_code,
        "reason": f"{missing} cần được tính vào mapping `{col}` (mapping thiếu giá trị mới).",
        "rollback_plan": f"Revert patch và restore partition của {target_file} trước đó.",
    }
