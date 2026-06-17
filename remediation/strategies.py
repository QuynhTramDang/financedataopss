"""Fix-strategy registry — mỗi anomaly_type → một chiến lược khắc phục (pluggable).

Trước đây chỉ enum_drift có fix (mở rộng mapping); mọi thứ khác escalate trắng. Registry này cho:
  - kind="code_patch"  : sinh patch code (enum_drift, duplicate...).
  - kind="operational" : đề xuất HÀNH ĐỘNG vận hành (backfill, reingest...) — không sửa code,
                         vẫn cần human approval (đúng bản chất data-quality).
Thêm anomaly mới = thêm 1 strategy ở đây, KHÔNG sửa node/graph.
"""

from __future__ import annotations

from typing import Any, Callable, Optional


def _remediation(strategy: str, anomaly_type: str, kind: str, summary: str,
                 details: dict[str, Any]) -> dict[str, Any]:
    return {"strategy": strategy, "anomaly_type": anomaly_type, "kind": kind,
            "summary": summary, "details": details, "requires_approval": True}


def _enum_drift(state: dict) -> dict[str, Any]:
    from tools.generate_patch import generate_patch
    s = state.get("tool_results_summary", {}) or {}
    new_values = s.get("enum_drift", {}).get("new_values", [])
    return _remediation("expand_mapping", "enum_drift", "code_patch",
                        f"Mở rộng mapping để gồm giá trị mới {new_values}",
                        {"patch": generate_patch(s)})


def _duplicate(state: dict) -> dict[str, Any]:
    s = state.get("tool_results_summary", {}) or {}
    pipeline = (s.get("scope", {}) or {}).get("pipeline")
    return _remediation("dedup_by_business_key", "duplicate", "code_patch",
                        "Khử trùng theo business key (ROW_NUMBER/DISTINCT) ở tầng ods để tránh double count",
                        {"patch": {"change_type": "add_dedup", "target_file": pipeline,
                                   "requires_approval": True,
                                   "reason": "Loại bản ghi trùng (cùng khóa) gây double count"}})


def _missing_partition(state: dict) -> dict[str, Any]:
    s = state.get("tool_results_summary", {}) or {}
    pipeline = (s.get("scope", {}) or {}).get("pipeline")
    date = state.get("date")
    return _remediation("backfill_partition", "missing_partition", "operational",
                        f"Backfill partition {date} cho {pipeline} (re-run ingestion/upstream)",
                        {"action": "backfill", "partition": date, "pipeline": pipeline})


def _null_spike(state: dict) -> dict[str, Any]:
    s = state.get("tool_results_summary", {}) or {}
    col = (s.get("scope", {}) or {}).get("null_column")
    return _remediation("reingest_source", "null_spike", "operational",
                        f"Kiểm tra & re-ingest từ upstream (null bất thường ở cột {col})",
                        {"action": "reingest", "check": "upstream source", "column": col})


def _volume_drop(state: dict) -> dict[str, Any]:
    date = state.get("date")
    return _remediation("await_or_backfill", "volume_drop", "operational",
                        f"Chờ late-arriving data cho {date}, hoặc backfill nếu xác nhận thiếu",
                        {"action": "await_or_backfill", "partition": date})


def _distribution_drift(state: dict) -> dict[str, Any]:
    return _remediation("recompute_or_investigate_source", "distribution_drift", "operational",
                        "Phân phối measure lệch mạnh — kiểm tra nguồn/định nghĩa metric, recompute nếu sai",
                        {"action": "investigate_source"})


def _unknown_issue(state: dict) -> dict[str, Any]:
    candidate = state.get("candidate_issue") or {}
    issue_type = candidate.get("candidate_issue_type", "unclassified_data_quality_issue")
    return _remediation("review_candidate_issue_definition", "unknown_issue", "analysis",
                        f"Review candidate issue definition `{issue_type}` before promoting it to detector/runbook",
                        {"action": "human_review_candidate_issue", "candidate_issue": candidate})


_STRATEGIES: dict[str, Callable[[dict], dict[str, Any]]] = {
    "enum_drift": _enum_drift,
    "duplicate": _duplicate,
    "missing_partition": _missing_partition,
    "null_spike": _null_spike,
    "volume_drop": _volume_drop,
    "distribution_drift": _distribution_drift,
    "unknown_issue": _unknown_issue,
}


def get_strategy(anomaly_type: Optional[str]) -> Optional[Callable[[dict], dict[str, Any]]]:
    return _STRATEGIES.get(anomaly_type or "")


def build_remediation(state: dict) -> Optional[dict[str, Any]]:
    """Trả remediation theo anomaly_type của state; None nếu chưa có strategy (→ escalate trắng)."""
    fn = _STRATEGIES.get(state.get("anomaly_type") or "")
    return fn(state) if fn else None
