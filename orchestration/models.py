"""Shared models for planner-driven execution and evidence verification."""

from __future__ import annotations

from typing import Any, Literal, TypedDict


ToolSource = Literal["local", "mcp"]
# collected = tool chạy xong, dữ liệu đã thu (CHƯA phải verify nghiệp vụ — verify thật ở claim/trust layer)
# skipped   = bỏ qua vì một dependency không thành công
EvidenceStatus = Literal[
    "unverified", "collected", "verified", "unsupported", "blocked", "skipped", "error"
]


class PlanStep(TypedDict, total=False):
    """A planner-selected tool call.

    `depends_on` names prior step ids whose evidence should exist before this
    step runs. The initial implementation executes sequentially, but keeping the
    dependency field makes the plan ready for DAG execution later.
    """

    id: str
    tool: str
    capability: str
    reason: str
    inputs: dict[str, Any]
    depends_on: list[str]
    expected_evidence: str


class EvidenceItem(TypedDict, total=False):
    """Normalized evidence emitted by any local or MCP tool."""

    id: str
    step_id: str
    source_tool: str
    source: ToolSource
    evidence_type: str
    status: EvidenceStatus
    data: Any
    summary: str
    citations: list[dict[str, Any]]
    error: str
