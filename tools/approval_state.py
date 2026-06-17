"""approval_state — quản lý trạng thái approve/reject/request_revision (FR-015)."""

from __future__ import annotations

VALID_DECISIONS = {"approve": "approved", "reject": "rejected", "request_revision": "needs_revision"}


def apply_decision(decision: str) -> str:
    """Map hành động người dùng → approval_status. Patch không apply nếu chưa 'approved'."""
    if decision not in VALID_DECISIONS:
        raise ValueError(f"Decision không hợp lệ: {decision}")
    return VALID_DECISIONS[decision]


def can_apply(approval_status: str) -> bool:
    return approval_status == "approved"
