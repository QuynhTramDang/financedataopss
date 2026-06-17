"""log_search — đọc mock log của một job (Airflow/dbt giả lập).

MVP đọc file local trong data/mock_logs/. Production sẽ thay bằng Airflow/Datadog API (cùng interface).
"""

from __future__ import annotations

from pathlib import Path

_LOG_DIR = Path(__file__).resolve().parents[1] / "data" / "mock_logs"


def log_search(job: str) -> dict:
    """Trả {job, found, log}. log = nội dung file <job>.log."""
    path = _LOG_DIR / f"{job}.log"
    if not path.exists():
        return {"job": job, "found": False, "log": ""}
    return {"job": job, "found": True, "log": path.read_text(encoding="utf-8")}


def available_jobs() -> list[str]:
    return sorted(p.stem for p in _LOG_DIR.glob("*.log"))
