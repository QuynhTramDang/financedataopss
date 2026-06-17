"""run_classifier — phân loại failure type từ log (deterministic keyword rules).

Loại: transient | permission | code_bug | schema_drift | data_quality | unknown.
Thứ tự ưu tiên tránh nhầm (transient/permission/code_bug trước schema/quality).
"""

from __future__ import annotations

from typing import Any

# (type, keywords) — xét theo thứ tự
_RULES = [
    ("transient", ["429", "rate limit", "timeout", "connection reset",
                   "temporarily unavailable", "503", "too many requests"]),
    ("permission", ["permission denied", "403", "access denied", "unauthorized"]),
    ("code_bug", ["traceback", "keyerror", "nameerror", "syntaxerror",
                  "typeerror", "attributeerror"]),
    ("schema_drift", ["schema mismatch", "added by upstream", "type changed",
                      "unexpected column", "schema drift", "required column"]),
    ("data_quality", ["accepted_values", "not_null", "null check", "duplicate",
                      "dbt test", "freshness"]),
]


def classify_failure(log_text: str) -> dict[str, Any]:
    low = (log_text or "").lower()
    for ftype, keywords in _RULES:
        hits = [k for k in keywords if k in low]
        if hits:
            return {"failure_type": ftype, "matched": hits,
                    "confidence": min(0.6 + 0.1 * len(hits), 0.95)}
    return {"failure_type": "unknown", "matched": [], "confidence": 0.2}
