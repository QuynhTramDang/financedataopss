"""action_policy — allow-list hành động tự động (L3) + map failure type → hành động (§3 tiers).

L3 safe-autonomous: chỉ action reversible mới được tự chạy. Còn lại → propose (L2) hoặc escalate.
"""

from __future__ import annotations

from typing import Any

# Chỉ những action này mới được phép chạy tự động (reversible, có thể rollback)
ALLOWED_L3_ACTIONS = {"retry_job", "rerun_partition", "refresh_metadata", "notify_owner"}

# failure_type → (action, tier, requires_approval, autonomous)
_DECISION = {
    "transient":    ("retry_job", "L3_safe_autonomous", False, True),
    "schema_drift": ("propose_patch", "L2_assisted", True, False),
    "code_bug":     ("propose_patch", "L2_assisted", True, False),
    "data_quality": ("notify_owner", "L3_safe_autonomous", False, True),
    "permission":   ("notify_owner_and_escalate", "L1_read_only", False, False),
    "unknown":      ("escalate", "L1_read_only", False, False),
}


def decide_action(failure_type: str) -> dict[str, Any]:
    action, tier, approval, autonomous = _DECISION.get(failure_type, _DECISION["unknown"])
    return {"action": action, "tier": tier, "requires_approval": approval,
            "autonomous": autonomous}


def is_autonomous_allowed(action: str) -> bool:
    """Action có được phép chạy tự động không (nằm trong allow-list L3)."""
    return action in ALLOWED_L3_ACTIONS
