"""scheduler — trigger sweep định kỳ (MVP: run-once; production: cron/Airflow).

auto_open_investigation: khi sweep thấy anomaly, tự mở investigation đầy đủ (cùng engine) để dựng
evidence pack — entry-point = scheduler thay vì user.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Optional

from .sweep import sweep


def run_sweep_once(metric: str, dates: Optional[list[str]] = None,
                   conn: Optional[sqlite3.Connection] = None,
                   suppress: Optional[list[str]] = None) -> list[dict[str, Any]]:
    """Chạy 1 lượt sweep cho metric/asset cấu hình, trả alerts."""
    return sweep(metric, dates=dates, conn=conn, suppress=suppress)


def auto_open_investigation(date: str) -> dict[str, Any]:
    """Tự mở investigation cho partition có anomaly (dùng DB mặc định)."""
    from graph.state import new_state
    from graph.workflow import build_workflow

    request = f"[MONITORING] Revenue report {date} phát hiện anomaly, điều tra tự động."
    return build_workflow().invoke(new_state(request))
