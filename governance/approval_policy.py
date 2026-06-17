"""approval_policy — risk level → hành động cho phép + tier quyền L1/L2/L3 (§12.5).

Tier quyền (guardrail Senior DE Assistant):
  L1 read-only       : đọc/điều tra/trả lời — không ghi gì.
  L2 assisted        : tạo proposal (patch/PR/test) → CẦN human approval.
  L3 safe-autonomous : chỉ action reversible (retry transient, refresh metadata) — có rollback.
Mọi hành động ghi/đổi vẫn cần approval; chỉ ghi memory sau approve.
"""

from __future__ import annotations

from enum import Enum


class PermissionTier(str, Enum):
    L1_READ_ONLY = "L1_read_only"
    L2_ASSISTED = "L2_assisted"
    L3_SAFE_AUTONOMOUS = "L3_safe_autonomous"


# risk_level → quyết định (theo bảng §12.5)
_RISK_ACTIONS = {
    "low": {"allowed_action": "answer_directly", "requires_approval": False, "can_deploy": False},
    "medium": {"allowed_action": "read_only_sql", "requires_approval": False, "can_deploy": False},
    "high": {"allowed_action": "patch_with_validation_and_approval",
             "requires_approval": True, "can_deploy": False},
    "critical": {"allowed_action": "blocked_in_mvp", "requires_approval": True, "can_deploy": False},
}

# action → tier
_ACTION_TIER = {
    # L1 read-only
    "answer_directly": PermissionTier.L1_READ_ONLY,
    "read_only_sql": PermissionTier.L1_READ_ONLY,
    "lineage_question": PermissionTier.L1_READ_ONLY,
    "diagnostic": PermissionTier.L1_READ_ONLY,
    # L2 assisted (cần approval)
    "patch_with_validation_and_approval": PermissionTier.L2_ASSISTED,
    "generate_patch": PermissionTier.L2_ASSISTED,
    "generate_test": PermissionTier.L2_ASSISTED,
    "memory_writeback": PermissionTier.L2_ASSISTED,
    "create_mr": PermissionTier.L2_ASSISTED,
    # L3 safe-autonomous (reversible)
    "retry_transient": PermissionTier.L3_SAFE_AUTONOMOUS,
    "rerun_partition": PermissionTier.L3_SAFE_AUTONOMOUS,
    "refresh_metadata": PermissionTier.L3_SAFE_AUTONOMOUS,
    "notify_owner": PermissionTier.L3_SAFE_AUTONOMOUS,
}


def decide_risk_action(risk_level: str) -> dict:
    """Trả {risk_level, allowed_action, requires_approval, can_deploy, tier}."""
    info = dict(_RISK_ACTIONS.get(risk_level, _RISK_ACTIONS["medium"]))
    info["risk_level"] = risk_level
    info["tier"] = tier_of_action(info["allowed_action"]).value
    return info


def tier_of_action(action: str) -> PermissionTier:
    """Tier quyền của một action (mặc định L2 nếu không rõ → an toàn, cần approval)."""
    return _ACTION_TIER.get(action, PermissionTier.L2_ASSISTED)
