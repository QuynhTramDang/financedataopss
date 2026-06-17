"""LangGraph state cho một investigation (theo §5.2 của PROJECT_DOC).

`timeline` dùng reducer `add` để các node *append* bước đã chạy (thay vì ghi đè), phục vụ
hiển thị tiến trình trên UI và assert thứ tự node trong test.
"""

from __future__ import annotations

import uuid
from operator import add
from typing import Annotated, Any, Optional, TypedDict


class TimelineEntry(TypedDict, total=False):
    node: str
    status: str          # ok | skipped | escalated | blocked
    note: str
    model: Optional[str]  # model dùng ở node (gắn ở Step 14)


class InvestigationState(TypedDict, total=False):
    # ── input / phân loại ──
    investigation_id: str
    user_request: str
    metric: Optional[str]
    date: Optional[str]
    intent: Optional[str]
    risk_level: Optional[str]

    # ── retrieval / tool ──
    retrieved_context: list[Any]
    context_pack: dict[str, Any]
    tool_plan: list[Any]
    plan_steps: list[Any]
    evidence: list[Any]
    tool_results_summary: dict[str, Any]
    governance: dict[str, Any]

    # ── reasoning / verification ──
    root_cause: Optional[Any]
    anomaly_type: Optional[str]
    candidate_issue: dict[str, Any]
    hypotheses: list[Any]
    claims: list[Any]
    claim_verification_result: dict[str, Any]
    impact_analysis: dict[str, Any]

    # ── patch / validation / report ──
    patch: Optional[Any]
    patch_review: dict[str, Any]
    fix_values: list[Any]          # tập giá trị fix sẽ phủ (reflection có thể broaden)
    validation_attempts: int       # số vòng reflection đã chạy (loop guard)
    remediation: dict[str, Any]    # chiến lược khắc phục theo anomaly (code_patch | operational)
    dispatch_result: dict[str, Any]  # kết quả thực thi remediation qua MCP sau approval (M2)
    validation_result: Optional[Any]
    trust_matrix: dict[str, Any]
    rca_report: Optional[Any]
    dbt_test: dict[str, Any]
    docs_update: dict[str, Any]

    # ── approval / memory ──
    approval_status: str           # pending | approved | rejected | needs_revision
    memory_writeback_status: str   # not_started | written | learned | skipped
    # correction do người cung cấp khi agent miss/sai → ăn vào memory (learning loop)
    human_correction: dict[str, Any]   # {root_cause, fix?, anomaly_type?, suggested_tools?}

    # ── routing flags (skeleton) ──
    issue_mode: Optional[str]      # known | unknown
    confidence_route: Optional[str]  # confident | escalate

    # ── progress ──
    timeline: Annotated[list[TimelineEntry], add]


def new_state(user_request: str, investigation_id: Optional[str] = None) -> InvestigationState:
    """Khởi tạo state cho một investigation mới (Step: State Initialization)."""
    inv_id = investigation_id or f"INV-{uuid.uuid4().hex[:8]}"

    # mỗi investigation bắt đầu với trace observability sạch (trace_id = investigation_id)
    try:
        from observability.trace_logger import reset_trace
        reset_trace(inv_id)
    except Exception:  # noqa: BLE001
        pass

    return InvestigationState(
        investigation_id=inv_id,
        user_request=user_request,
        retrieved_context=[],
        tool_plan=[],
        plan_steps=[],
        evidence=[],
        tool_results_summary={},
        hypotheses=[],
        claims=[],
        claim_verification_result={},
        impact_analysis={},
        trust_matrix={},
        approval_status="pending",
        memory_writeback_status="not_started",
        timeline=[{"node": "state_init", "status": "ok", "note": f"init {inv_id}"}],
    )
