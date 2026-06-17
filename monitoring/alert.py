"""alert — dựng alert từ anomaly đã phát hiện (kèm evidence + recommended action theo tier).

enum_drift (sửa được bằng code) → mở investigation + propose patch (L2, cần approval).
data quality (null/missing/volume) → notify owner / re-run an toàn (L3 reversible).
"""

from __future__ import annotations

from typing import Any

_SEVERITY = {"enum_drift": "high", "missing_partition": "high",
             "null_spike": "medium", "volume_drop": "medium"}

# anomaly → (recommended_action, tier)
_ACTION = {
    "enum_drift": ("open_investigation_and_propose_patch", "L2_assisted"),
    "missing_partition": ("notify_owner_and_trigger_rerun", "L3_safe_autonomous"),
    "null_spike": ("notify_owner", "L3_safe_autonomous"),
    "volume_drop": ("notify_owner", "L3_safe_autonomous"),
}


def build_alert(date: str, summary: dict, cls: dict) -> dict[str, Any]:
    anomaly = cls["anomaly_type"]
    action, tier = _ACTION.get(anomaly, ("escalate", "L1_read_only"))
    return {
        "date": date,
        "anomaly_type": anomaly,
        "severity": _SEVERITY.get(anomaly, "low"),
        "evidence": cls.get("evidence", []),
        "affected_amount": summary.get("affected_amount", 0),
        "recommended_action": action,
        "tier": tier,
        "detected_before_finance": True,
    }


def format_alert(alert: dict) -> str:
    """Format kiểu Slack message (cho demo)."""
    return (
        f"[DQ Alert] {alert['date']} — {alert['anomaly_type']} (severity={alert['severity']})\n"
        f"Evidence: {'; '.join(alert['evidence']) or 'n/a'}\n"
        f"Affected amount: {alert['affected_amount']:,}\n"
        f"Suggested action: {alert['recommended_action']} (tier {alert['tier']})"
    )
