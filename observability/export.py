"""export — xuất trace ra ngoài. Mặc định JSONL local; seam cắm Langfuse/LangSmith khi có env+SDK.

Offline/CI: JSONL (không phụ thuộc mạng). Production: set LANGFUSE_* / LANGSMITH_* → đẩy lên dashboard.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from .token_tracker import totals
from .trace_logger import current_trace_id, get_trace

_ROOT = Path(__file__).resolve().parents[1]


def export_jsonl(trace: Optional[list[dict]] = None, path: str = "reports/traces.jsonl") -> str:
    """Ghi trace (1 dòng/event) ra file JSONL. Trả đường dẫn file."""
    trace = trace if trace is not None else get_trace()
    full = Path(path) if Path(path).is_absolute() else _ROOT / path
    full.parent.mkdir(parents=True, exist_ok=True)
    with full.open("a", encoding="utf-8") as fh:
        for ev in trace:
            fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
    return str(full)


def _langfuse_export(trace: list[dict]) -> dict[str, Any]:
    """Seam: chỉ kích hoạt khi có SDK + env. Lỗi/không có → fallback (không làm vỡ)."""
    try:
        from langfuse import Langfuse  # type: ignore  # noqa: F401
    except Exception:  # noqa: BLE001
        return {"status": "skipped", "reason": "langfuse SDK chưa cài"}
    # (Triển khai thật: tạo trace/span theo trace_id; để seam ở đây cho gọn.)
    return {"status": "not_implemented", "reason": "wire Langfuse SDK ở production"}


def export_trace(trace: Optional[list[dict]] = None) -> dict[str, Any]:
    """Xuất trace: Langfuse/LangSmith nếu cấu hình, ngược lại JSONL local. Trả summary."""
    trace = trace if trace is not None else get_trace()
    summary = {"trace_id": current_trace_id(), "events": len(trace), **totals(trace)}

    if os.getenv("LANGFUSE_PUBLIC_KEY") or os.getenv("LANGFUSE_SECRET_KEY"):
        summary["export"] = _langfuse_export(trace)
    else:
        summary["export"] = {"status": "jsonl", "path": export_jsonl(trace)}
    return summary
