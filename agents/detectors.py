"""Anomaly detector registry — pluggable, ưu tiên theo thứ tự (thêm anomaly = thêm 1 detector).

Mỗi detector(summary, txn_date) → hypothesis dict hoặc None. classify() chạy theo thứ tự, lấy hit
đầu tiên. Ghép với remediation/strategies.py (cùng anomaly_type) → detect + fix end-to-end mà không
sửa graph. Verdict vẫn DETERMINISTIC từ evidence tool (§14.9).
"""

from __future__ import annotations

from typing import Any, Callable, Optional


def _h(anomaly_type: str, fix_type: str, confidence: float, route: str,
       evidence: list[str], root_cause_hint: Optional[str], missing: Optional[list] = None) -> dict:
    return {"anomaly_type": anomaly_type, "fix_type": fix_type, "confidence": confidence,
            "route": route, "evidence": evidence, "root_cause_hint": root_cause_hint,
            "missing": missing or []}


def _enum_drift(summary: dict, txn_date: str) -> Optional[dict]:
    new = summary.get("enum_drift", {}).get("new_values", [])
    missing = summary.get("code", {}).get("missing_values", [])
    if new and missing and set(new) == set(missing):
        return _h("enum_drift", "code_patch", 0.9, "confident",
                  [f"enum_drift: {new}", f"code thiếu mapping: {missing}",
                   f"affected_amount={summary.get('affected_amount', 0):,}"],
                  "code_patch", missing=missing)
    return None


def _missing_partition(summary: dict, txn_date: str) -> Optional[dict]:
    fresh = summary.get("quality_checks", {}).get("freshness", {})
    if fresh and fresh.get("row_count") == 0:
        return _h("missing_partition", "data_quality", 0.85, "escalate",
                  [f"freshness: partition {txn_date} có 0 row"],
                  f"Partition {txn_date} chưa load (0 row) — nghi ingestion/upstream chưa chạy.")
    return None


def _null_spike(summary: dict, txn_date: str) -> Optional[dict]:
    nullc = summary.get("quality_checks", {}).get("null_amount", {})
    if nullc.get("spike"):
        rate = nullc.get("null_rate", 0)
        return _h("null_spike", "data_quality", min(0.6 + rate, 0.9), "escalate",
                  [f"null_check: {nullc.get('column')} null_rate={rate:.0%} ({nullc.get('null_count')} rows)"],
                  f"Null spike ở cột {nullc.get('column')} ({rate:.0%}) ngày {txn_date} — nghi ingestion lỗi.")
    return None


def _duplicate(summary: dict, txn_date: str) -> Optional[dict]:
    d = summary.get("quality_checks", {}).get("duplicate", {})
    if d.get("has_duplicate"):
        return _h("duplicate", "code_patch", 0.8, "escalate",
                  [f"duplicate: {d.get('dup_groups')} key trùng, {d.get('dup_rows')} bản ghi dư"],
                  f"Trùng {d.get('dup_rows')} bản ghi theo {d.get('key_col')} ngày {txn_date} — double count.")
    return None


def _distribution_drift(summary: dict, txn_date: str) -> Optional[dict]:
    dd = summary.get("quality_checks", {}).get("distribution", {})
    if dd.get("drift"):
        return _h("distribution_drift", "data_quality", 0.7, "escalate",
                  [f"distribution: avg={dd.get('avg_today')} vs baseline={dd.get('baseline_avg')} "
                   f"(ratio={dd.get('ratio')})"],
                  f"Phân phối measure lệch mạnh (ratio={dd.get('ratio')}) ngày {txn_date} — nghi nguồn/định nghĩa sai.")
    return None


def _volume_drop(summary: dict, txn_date: str) -> Optional[dict]:
    vol = summary.get("quality_checks", {}).get("volume", {})
    if vol.get("drop"):
        return _h("volume_drop", "data_quality", 0.7, "escalate",
                  [f"volume: {vol.get('row_count')} vs baseline {vol.get('baseline')}"],
                  f"Volume giảm bất thường ngày {txn_date} — nghi data đến trễ/thiếu.")
    return None


# Thứ tự ưu tiên: cụ thể/fixable trước → data-quality. Thêm anomaly mới = thêm hàm vào list.
DETECTORS: list[Callable[[dict, str], Optional[dict]]] = [
    _enum_drift, _missing_partition, _null_spike, _duplicate, _distribution_drift, _volume_drop,
]


def classify(summary: dict, txn_date: str) -> dict[str, Any]:
    """Chạy detector theo thứ tự, lấy hit đầu tiên. Không hit → low-confidence escalate."""
    for detector in DETECTORS:
        hit = detector(summary, txn_date)
        if hit:
            return hit
    return _h(None, "none", 0.2, "escalate", [], None,
              missing=summary.get("code", {}).get("missing_values", []))
