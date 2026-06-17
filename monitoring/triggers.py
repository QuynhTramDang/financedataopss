"""M3 — Inbound trigger: Airflow task fail → TỰ mở investigation (đóng vòng Automation).

Entry-point = sự kiện Airflow (qua on_failure_callback/webhook) thay vì người gõ tay. dag_id → metric
suy từ pipeline_memory (fail-loud nếu không map). Dedup theo (dag_id, run_date) tránh mở trùng nhiều
investigation cho cùng 1 lần fail (loop guard, §31).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

_PIPELINE_MEMORY = Path(__file__).resolve().parents[1] / "memory" / "pipeline_memory.json"
_seen: set[str] = set()


def reset_dedup() -> None:
    _seen.clear()


def _metric_for_dag(dag_id: str) -> str:
    """dag_id (= tên pipeline) → metric từ pipeline_memory. Fail-loud nếu không có mapping."""
    try:
        pipelines = json.loads(_PIPELINE_MEMORY.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Không đọc được pipeline_memory: {exc}") from exc
    for p in pipelines:
        if p.get("pipeline") == dag_id and p.get("metric"):
            return p["metric"]
    raise ValueError(f"DAG '{dag_id}' không map tới metric nào trong pipeline_memory (fail-loud).")


def handle_airflow_failure(dag_id: str, run_date: str, task_id: Optional[str] = None,
                           dedup: bool = True) -> dict[str, Any]:
    """Nhận sự kiện fail → mở investigation đầy đủ (cùng engine). Trả summary (không deploy gì)."""
    key = f"{dag_id}|{run_date}"
    if dedup and key in _seen:
        return {"status": "deduped", "dag_id": dag_id, "run_date": run_date}

    metric = _metric_for_dag(dag_id)   # fail-loud nếu DAG lạ
    _seen.add(key)

    from graph.state import new_state
    from graph.workflow import build_workflow

    task_part = f" task {task_id}" if task_id else ""
    # nhúng metric + date vào request để intent classifier resolve đúng scope
    request = (f"[AIRFLOW] DAG {dag_id} fail ngày {run_date}{task_part} — "
               f"điều tra metric {metric}.")
    inv_id = f"INV-AF-{dag_id}-{run_date}"
    final = build_workflow().invoke(new_state(request, investigation_id=inv_id))

    return {
        "status": "opened",
        "investigation_id": final.get("investigation_id"),
        "dag_id": dag_id,
        "run_date": run_date,
        "metric": metric,
        "anomaly_type": final.get("anomaly_type"),
        "confidence_route": final.get("confidence_route"),
        "remediation": final.get("remediation"),
    }
