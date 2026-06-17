"""sweep — chạy DQ checklist trên các partition theo dõi, phát hiện anomaly (L1 detect).

Reuse diagnostic_planner + _classify (deterministic). Suppress 'known benign' partition.
Cùng engine với investigation, chỉ khác entry-point = scheduler thay vì user.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Optional

from agents.diagnostic_planner import run as run_diagnostics
from agents.root_cause_reasoner import _classify

from .alert import build_alert

DEFAULT_WATCH = ["2026-06-07", "2026-06-08", "2026-06-09", "2026-06-10"]


def sweep(metric: str, dates: Optional[list[str]] = None,
          conn: Optional[sqlite3.Connection] = None,
          suppress: Optional[list[str]] = None) -> list[dict[str, Any]]:
    """Quét các ngày cho 1 metric/asset đã cấu hình, trả alert cho partition có anomaly.

    `metric` là cấu hình watch (vd 'net_revenue') — scope/contract suy từ đó (không hardcode).
    """
    dates = dates or DEFAULT_WATCH
    suppressed = set(suppress or [])
    alerts = []
    for d in dates:
        if d in suppressed:
            continue
        summary = run_diagnostics({"date": d, "metric": metric}, conn=conn)
        cls = _classify(summary, d)
        if cls["anomaly_type"] is not None:        # chỉ alert khi có anomaly rõ
            alerts.append(build_alert(d, summary, cls))
    return alerts
