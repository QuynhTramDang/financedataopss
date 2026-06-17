"""Governed executor for plan steps.

Mỗi step đi qua: dependency gate → governance gate → execute → evidence chuẩn hoá.
Policy và normalization tập trung ở đây, không rải rác trong planner.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Optional

from governance.pii_policy import mask_for_llm

from .models import EvidenceItem, PlanStep
from .registry import ToolRegistry, get_registry

# tool cần connection DB inject vào lúc chạy (đọc qua database.connection)
_NEEDS_CONN = {"sql_profile", "freshness_check", "volume_check", "null_check",
               "duplicate_check", "distribution_drift_check"}

# trạng thái coi là "không thành công" → dependent step sẽ bị skip
_FAILED = {"blocked", "skipped", "error"}


def _summary(tool: str, result: Any) -> str:
    if not isinstance(result, dict):
        return "tool executed"
    if tool == "metadata_scan":
        return f"metadata found={result.get('found')}"
    if tool == "sql_profile":
        return f"profile groups={len(result.get('profile', {}))}"
    if tool == "enum_drift_check":
        return f"new_values={result.get('new_values', [])}"
    if tool == "code_search":
        return f"matches={len(result.get('matches', []))}"
    if tool == "lineage_lookup":
        return f"lineage found={result.get('found')}"
    if tool in {"freshness_check", "volume_check", "null_check"}:
        return str(result)
    return "tool executed"


def _evidence(step: PlanStep, record_source: str, evidence_type: str,
              status: str, data: Any, summary: str, **extra: Any) -> EvidenceItem:
    item: EvidenceItem = {
        "id": f"ev-{step['id']}",
        "step_id": step["id"],
        "source_tool": step["tool"],
        "source": record_source,  # type: ignore[typeddict-item]
        "evidence_type": evidence_type,
        "status": status,  # type: ignore[typeddict-item]
        "data": data,
        "summary": summary,
    }
    item.update(extra)  # type: ignore[typeddict-item]
    return item


def execute_plan(
    plan: list[PlanStep],
    *,
    conn: Optional[sqlite3.Connection] = None,
    registry: Optional[ToolRegistry] = None,
    gateway: Any = None,
) -> list[EvidenceItem]:
    """Execute plan steps through registry + governance. Trả evidence chuẩn hoá."""
    registry = registry or get_registry()
    evidence: list[EvidenceItem] = []
    status_by_step: dict[str, str] = {}

    for step in plan:
        sid = step["id"]
        tool_name = step["tool"]

        # ── dependency gate (nit #2): dep nào không thành công → skip step này ──
        failed_dep = next(
            (d for d in step.get("depends_on", []) if status_by_step.get(d) in _FAILED),
            None,
        )
        if failed_dep:
            item = _evidence(step, "local", "", "skipped", {},
                             f"skipped: dependency '{failed_dep}' did not succeed")
            evidence.append(item)
            status_by_step[sid] = "skipped"
            continue

        # ── tool phải có trong registry ──
        try:
            record = registry.get(tool_name)
        except KeyError:
            item = _evidence(step, "local", "", "error", {},
                             f"tool '{tool_name}' is not registered",
                             error="KeyError: unregistered tool")
            evidence.append(item)
            status_by_step[sid] = "error"
            continue

        # ── governance gate ──
        gov = record.governance
        if gov["decision"] != "allowed":
            item = _evidence(step, record.source, record.evidence_type, "blocked",
                             {"governance": gov}, gov["reason"])
            evidence.append(item)
            status_by_step[sid] = "blocked"
            continue

        # ── execute (local callable hoặc MCP tool qua gateway) ──
        try:
            if record.source == "mcp":
                from .mcp_gateway import get_gateway
                gw = gateway or get_gateway()
                result = gw.call(tool_name, dict(step.get("inputs", {})))
            else:
                if record.fn is None:
                    raise RuntimeError(f"Tool '{tool_name}' has no local callable.")
                inputs = dict(step.get("inputs", {}))
                if tool_name in _NEEDS_CONN:
                    inputs["conn"] = conn
                result = record.fn(**inputs)
            # PII gate (§Security): mask trước khi evidence vào state/LLM/RCA — chokepoint duy nhất
            safe = mask_for_llm(result)
            item = _evidence(step, record.source, record.evidence_type, "collected",
                             safe, _summary(tool_name, safe), citations=[])
            evidence.append(item)
            status_by_step[sid] = "collected"
        except Exception as exc:  # noqa: BLE001 — tool fail không được làm vỡ luồng
            item = _evidence(step, record.source, record.evidence_type, "error", {},
                             "tool execution failed", error=f"{type(exc).__name__}: {exc}")
            evidence.append(item)
            status_by_step[sid] = "error"

    return evidence
