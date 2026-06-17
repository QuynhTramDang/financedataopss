"""pii_policy — mask trường nhạy cảm trước khi đưa ra ngoài/LLM (§ Security).

MVP: mask theo tên field nhạy cảm (email, phone, card, ssn, cmnd, account...).
Nguyên tắc: không expose PII/raw transaction; chỉ summary/aggregate được đưa vào LLM.
"""

from __future__ import annotations

import re
from typing import Any

_SENSITIVE_KEYS = re.compile(
    r"(email|phone|mobile|card|cvv|ssn|cmnd|cccd|account|passport|address|tax_id)",
    re.IGNORECASE,
)


def _mask_value(value: Any) -> str:
    s = str(value)
    if len(s) <= 4:
        return "***"
    return s[:2] + "*" * (len(s) - 4) + s[-2:]


def mask_record(record: dict[str, Any]) -> dict[str, Any]:
    """Trả bản copy đã mask các field nhạy cảm (theo tên key)."""
    out: dict[str, Any] = {}
    for key, value in record.items():
        if _SENSITIVE_KEYS.search(key):
            out[key] = _mask_value(value)
        else:
            out[key] = value
    return out


def has_pii(record: dict[str, Any]) -> bool:
    return any(_SENSITIVE_KEYS.search(k) for k in record)


def mask_for_llm(obj: Any) -> Any:
    """Mask PII ĐỆ QUY trong dict/list trước khi đưa ra LLM/ngoài (giữ nguyên cấu trúc/số liệu).

    Field có key nhạy cảm + value scalar → mask; còn lại đệ quy xuống dict/list con.
    """
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for key, value in obj.items():
            if _SENSITIVE_KEYS.search(key) and not isinstance(value, (dict, list)):
                out[key] = _mask_value(value)
            else:
                out[key] = mask_for_llm(value)
        return out
    if isinstance(obj, list):
        return [mask_for_llm(x) for x in obj]
    return obj
