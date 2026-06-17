"""Conditional edge functions cho LangGraph.

Skeleton: trả nhánh mặc định dựa trên flag trong state (do node set), để có thể test cả happy path
lẫn nhánh escalate mà không cần logic thật. Các step sau sẽ thay bằng quyết định dựa trên evidence.
"""

from __future__ import annotations

from .state import InvestigationState


def route_known_unknown(state: InvestigationState) -> str:
    """known → theo runbook; unknown → Unknown Issue Mode. (Cả hai đều tới tool_governance.)"""
    return "unknown" if state.get("issue_mode") == "unknown" else "known"


def route_confidence(state: InvestigationState) -> str:
    """confident → sinh patch; escalate → bỏ qua patch, đi thẳng RCA/escalate."""
    return "escalate" if state.get("confidence_route") == "escalate" else "confident"


MAX_VALIDATION_ATTEMPTS = 2   # số vòng reflection tối đa (loop guard)


def route_validation(state: InvestigationState) -> str:
    """Reflection gate: PASS → đi tiếp; FAIL & còn lượt → refine rồi re-validate; hết lượt → escalate.

    Đây là vòng observe→think→act→critique: validation thất bại thì critique + sửa lại patch,
    KHÔNG đi thẳng tới RCA với số sai. Bounded bằng validation_attempts (chống loop vô hạn).
    """
    vr = state.get("validation_result") or {}
    if vr.get("validation_status") == "PASS":
        return "ok"
    if state.get("validation_attempts", 0) < MAX_VALIDATION_ATTEMPTS:
        return "retry"
    return "giveup"


def route_approval(state: InvestigationState) -> str:
    """Ghi memory khi 'approved' HOẶC khi người cung cấp correction (learning loop).

    'approved' → học từ kết luận đã duyệt; có human_correction → học từ chỉ dẫn của người
    (kể cả khi agent miss/escalate). Còn lại → halt (không auto-deploy).
    """
    if state.get("approval_status") == "approved" or state.get("human_correction"):
        return "approved"
    return "halt"
