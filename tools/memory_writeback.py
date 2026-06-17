"""memory_writeback — ghi incident mới vào long-term memory CHỈ SAU human approval (§8.3).

Upsert theo incident_id (idempotent). incident_id/metric/pipeline suy từ metric contract
(không hardcode 'revenue_daily'/'net_revenue'). Đường dẫn override bằng env DATAOPS_INCIDENT_MEMORY.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from domain.contracts import ContractError, get_contract

_DEFAULT = Path(__file__).resolve().parents[1] / "memory" / "incident_memory.json"


def _incident_path() -> Path:
    return Path(os.getenv("DATAOPS_INCIDENT_MEMORY", str(_DEFAULT)))


def build_incident(state: dict) -> dict[str, Any]:
    summary = state.get("tool_results_summary", {}) or {}
    date = state.get("date", "unknown")
    new_values = summary.get("enum_drift", {}).get("new_values", [])
    metric = state.get("metric") or "metric"
    try:
        contract = get_contract(state.get("metric")) if state.get("metric") else {}
    except ContractError:
        contract = {}
    status_col = contract.get("status_column", "status")
    pipeline = contract.get("pipeline") or summary.get("code", {}).get("repo_path", "pipeline")

    # correction do người cung cấp được ưu tiên (học từ chỉ dẫn, kể cả khi agent miss)
    correction = state.get("human_correction") or {}
    root_cause = correction.get("root_cause") or state.get("root_cause")
    fix = correction.get("fix") or (state.get("patch") or {}).get("new_code")
    anomaly = correction.get("anomaly_type") or state.get("anomaly_type")
    # runbook_tools: tool nên chạy cho ca này lần sau (người gợi ý, hoặc tool agent đã chạy)
    runbook_tools = correction.get("suggested_tools") or state.get("tool_plan", [])
    created_from = "human_correction" if correction else "human_approved_rca"

    return {
        "incident_id": f"INC-{date}-{metric}",
        "metric": metric,
        "anomaly_type": anomaly,
        "issue": f"{metric} mismatch caused by new {status_col} {new_values}",
        "symptom": f"{metric} overstated",
        "root_cause": root_cause,
        "fix": fix,
        "related_pipeline": pipeline,
        "diagnostic_steps": state.get("tool_plan", []),
        "runbook_tools": runbook_tools,
        "approval_required": ["Finance Owner", "Data Owner"],
        "created_from": created_from,
    }


def write_incident(state: dict, approval_status: str) -> dict[str, Any]:
    """Ghi khi approved HOẶC khi có human_correction (learning loop). Trả {status, incident?}."""
    correction = state.get("human_correction")
    if approval_status != "approved" and not correction:
        return {"status": "skipped", "reason": "chưa approve và không có correction"}

    incident = build_incident(state)
    path = _incident_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    if not isinstance(existing, list):
        existing = []

    existing = [r for r in existing if r.get("incident_id") != incident["incident_id"]]
    existing.append(incident)
    path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    status = "learned" if correction else "written"
    return {"status": status, "incident": incident}
