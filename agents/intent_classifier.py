"""intent_classifier — phân loại intent/metric/date/risk (Step 4).

Thiết kế (FR-002 + triết lý §14.2.2):
  - LLM (route 'classifier', model nhỏ) đề xuất intent/metric/date/risk.
  - Nếu không có model (thiếu key) hoặc LLM trả sai schema → fallback **heuristic deterministic**,
    để graph vẫn chạy offline.
  - **Rule override (deterministic, không tin mỗi LLM):** mọi vấn đề liên quan Finance metric →
    risk_level = 'high'. Date/metric được trích lại bằng regex/keyword nếu LLM bỏ sót.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from domain.contracts import list_metrics, metric_terms
from model_router import LLMSchemaError, ProviderError, get_router

INTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string"},
        "metric": {"type": ["string", "null"]},
        "date": {"type": ["string", "null"]},
        "risk_level": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
    },
    "required": ["intent", "risk_level"],
    "additionalProperties": False,
}

_SYSTEM = (
    "Bạn là bộ phân loại yêu cầu điều tra dữ liệu Finance. "
    "Phân loại intent, trích metric (vd net_revenue), date (YYYY-MM-DD nếu có), và risk_level."
)


def _extract_date(text: str) -> Optional[str]:
    m = re.search(r"\d{4}-\d{2}-\d{2}", text)
    return m.group(0) if m else None


def _detect_metric(text: str) -> Optional[str]:
    """Nhận diện metric từ contract (tên + aliases) — không hardcode 'net_revenue'."""
    low = text.lower()
    for metric, terms in metric_terms().items():
        if any(t and t.lower() in low for t in terms):
            return metric
    return None


def _is_finance(metric: Optional[str], text: str) -> bool:
    if metric and metric in set(list_metrics()):
        return True
    low = text.lower()
    return any(t and t.lower() in low for terms in metric_terms().values() for t in terms)


def _heuristic(user_request: str) -> dict[str, Any]:
    low = user_request.lower()
    if any(k in low for k in ("mismatch", "lệch", "lech", "sai", "chênh")):
        intent = "investigate_revenue_mismatch" if "revenue" in low or "doanh thu" in low \
            else "investigate_data_mismatch"
    else:
        intent = "general_investigation"
    return {"intent": intent, "metric": None, "date": None, "risk_level": "medium"}


def classify(user_request: str, router=None) -> dict[str, Any]:
    """Trả {intent, metric, date, risk_level}. Luôn áp rule override risk cho Finance metric."""
    router = router or get_router()
    try:
        data = router.call_structured(
            route="classifier",
            prompt=f"Yêu cầu của người dùng:\n{user_request}",
            schema=INTENT_SCHEMA,
            system=_SYSTEM,
        )
    except (LLMSchemaError, ProviderError) as exc:  # gồm ProviderUnavailable
        # không có model / sai schema → fallback deterministic (graph vẫn chạy offline)
        data = _heuristic(user_request)
        data["_fallback"] = f"heuristic ({type(exc).__name__})"

    # ── deterministic enrichment ──
    if not data.get("metric"):
        data["metric"] = _detect_metric(user_request)
    if not data.get("date"):
        data["date"] = _extract_date(user_request)

    # ── rule override: Finance metric → risk cao (không tin mỗi LLM) ──
    if _is_finance(data.get("metric"), user_request):
        data["risk_level"] = "high"
    data.setdefault("risk_level", "medium")

    return data
