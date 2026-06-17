"""Planner-driven diagnostics (orchestrator-workers, bounded).

LLM tự chọn tool chẩn đoán (qua orchestration.planner). Mỗi step được:
  - lọc về tập tool gathering hợp lệ + enrich input từ scope,
  - dedupe (không chạy lại tool+input trùng),
  - chạy qua executor (governance gác, evidence chuẩn hoá).
enum_drift_check là phép DẪN XUẤT từ evidence (deterministic) nên được tự thêm, không để LLM tự bịa input.
Có fallback offline (không model/LLM lỗi → fixed plan) để CI/test vẫn chạy. Verdict vẫn ở root_cause_reasoner.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

from orchestration.executor import execute_plan
from orchestration.models import EvidenceItem, PlanStep
from orchestration.planner import build_plan
from orchestration.registry import get_registry
from domain.contracts import resolve_scope

_MEMORY_DIR = Path(__file__).resolve().parents[1] / "memory"
_PIPELINE_MEMORY = _MEMORY_DIR / "pipeline_memory.json"


def _lineage_files(pipeline: str) -> list[str]:
    """Đi ngược lineage từ `pipeline` (BFS upstream) → list repo_path các tầng code có file.

    Bảng nguồn (payment_txn/order_fact) không có repo_path nên bị bỏ qua.
    Vd dtm_revenue_daily → [dtm.sql, ods.sql, stg_payment.sql, stg_order.sql].
    """
    try:
        pipelines = json.loads(_PIPELINE_MEMORY.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    by_name = {p["pipeline"]: p for p in pipelines}
    files: list[str] = []
    seen: set[str] = set()
    queue = [pipeline]
    while queue:
        name = queue.pop(0)
        if name in seen:
            continue
        seen.add(name)
        rec = by_name.get(name)
        if not rec:
            continue  # node là bảng nguồn (không phải pipeline) → không có code file
        if rec.get("repo_path"):
            files.append(rec["repo_path"])
        queue.extend(rec.get("upstream", []))
    return files

# Tool LLM được phép tự chọn (input suy được từ scope). enum_drift_check KHÔNG ở đây — nó dẫn xuất.
GATHERING = {
    "metadata_scan", "sql_profile", "freshness_check", "volume_check",
    "null_check", "duplicate_check", "distribution_drift_check", "code_search", "lineage_lookup",
}
_FALLBACK_ORDER = [
    "metadata_scan", "sql_profile", "freshness_check", "volume_check",
    "null_check", "duplicate_check", "distribution_drift_check", "code_search", "lineage_lookup",
]
MAX_FOLLOWUP_ROUNDS = 2


def _infer_scope(state: dict) -> dict[str, Any]:
    """Suy scope từ metric contract — fail-loud nếu thiếu metric/date (xem domain.contracts)."""
    return resolve_scope(state)


def _enrich(tool: str, inputs: dict[str, Any], scope: dict[str, Any]) -> dict[str, Any]:
    """Điền input mặc định từ scope cho tool gathering (LLM có thể bỏ sót)."""
    d = dict(inputs or {})
    if tool == "metadata_scan":
        d.setdefault("table", scope["table"])
    elif tool == "sql_profile":
        contract = scope.get("contract", {})
        d.setdefault("txn_date", scope["txn_date"])
        d.setdefault("table", scope["table"])
        d.setdefault("group_col", scope["enum_field"])
        d.setdefault("measure_column", contract.get("measure_column"))
        d.setdefault("deduction_column", contract.get("deduction_column"))
    elif tool in {"freshness_check", "volume_check"}:
        d.setdefault("txn_date", scope["txn_date"])
        d.setdefault("table", scope["table"])
    elif tool == "null_check":
        d.setdefault("txn_date", scope["txn_date"])
        d.setdefault("table", scope["table"])
        d.setdefault("column", scope["null_column"])
    elif tool == "duplicate_check":
        contract = scope.get("contract", {})
        d.setdefault("txn_date", scope["txn_date"])
        d.setdefault("table", scope["table"])
        d.setdefault("key_col", contract.get("business_key") or scope["enum_field"])
    elif tool == "distribution_drift_check":
        contract = scope.get("contract", {})
        d.setdefault("txn_date", scope["txn_date"])
        d.setdefault("table", scope["table"])
        d.setdefault("measure_col", contract.get("measure_column") or scope["null_column"])
    elif tool == "code_search":
        d.setdefault("pattern", scope["enum_field"])
        d.setdefault("repo_paths", _lineage_files(scope["pipeline"]))
    elif tool == "lineage_lookup":
        d.setdefault("asset", scope["pipeline"])
    return d


def _step(step_id: str, tool: str, reason: str, inputs: dict[str, Any],
          depends_on: Optional[list[str]] = None) -> PlanStep:
    record = get_registry().get(tool)
    return {
        "id": step_id,
        "tool": tool,
        "capability": record.capability,
        "reason": reason,
        "inputs": inputs,
        "depends_on": depends_on or [],
        "expected_evidence": record.evidence_type,
    }


def _key(tool: str, inputs: dict[str, Any]) -> str:
    safe = {k: v for k, v in inputs.items() if k != "conn"}
    return f"{tool}:{json.dumps(safe, sort_keys=True, default=str)}"


def _normalize(raw_steps: list[dict[str, Any]], scope: dict[str, Any],
               executed: set[str], counter: list[int]) -> list[PlanStep]:
    """Lọc về GATHERING + enrich + validate required + dedupe → PlanStep."""
    registry = get_registry()
    out: list[PlanStep] = []
    for rs in raw_steps or []:
        tool = rs.get("tool")
        if tool not in GATHERING:
            continue
        inputs = _enrich(tool, rs.get("inputs") or {}, scope)
        required = set(registry.get(tool).input_schema.get("required", []))
        if not required <= set(inputs):
            continue  # thiếu input bắt buộc → bỏ (không đoán bừa)
        k = _key(tool, inputs)
        if k in executed:
            continue
        executed.add(k)
        counter[0] += 1
        out.append(_step(f"{tool}-{counter[0]}", tool, rs.get("reason", "") or "planner", inputs))
    return out


def _fallback_plan(scope: dict[str, Any], executed: set[str], counter: list[int]) -> list[PlanStep]:
    raw = [{"tool": t, "inputs": {}, "reason": "fallback fixed plan"} for t in _FALLBACK_ORDER]
    return _normalize(raw, scope, executed, counter)


def _data(evidence: list[EvidenceItem], tool: str) -> dict[str, Any]:
    for item in evidence:
        if item.get("source_tool") == tool and item.get("status") == "collected":
            data = item.get("data")
            return data if isinstance(data, dict) else {}
    return {}


def _derived_plan(scope: dict[str, Any], evidence: list[EvidenceItem],
                  executed: set[str], counter: list[int]) -> list[PlanStep]:
    """enum_drift_check: dẫn xuất từ metadata + profile (deterministic, không để LLM bịa input)."""
    meta = _data(evidence, "metadata_scan")
    prof = _data(evidence, "sql_profile")
    if not (meta.get("found") and prof.get("profile")):
        return []
    known = meta.get("known_values", {}).get(scope["enum_field"], [])
    inputs = {"actual_values": list(prof["profile"].keys()), "known_values": known}
    k = _key("enum_drift_check", inputs)
    if k in executed:
        return []
    executed.add(k)
    counter[0] += 1
    return [_step(f"enum_drift_check-{counter[0]}", "enum_drift_check",
                  "derive enum drift from profile vs baseline", inputs)]


def _task(state: dict, scope: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_request": state.get("user_request"),
        "intent": state.get("intent"),
        "metric": state.get("metric"),
        **scope,
    }


def _legacy_summary(scope: dict[str, Any], evidence: list[EvidenceItem]) -> dict[str, Any]:
    meta = _data(evidence, "metadata_scan")
    prof = _data(evidence, "sql_profile")
    drift = _data(evidence, "enum_drift_check")
    code = _data(evidence, "code_search")
    lineage = _data(evidence, "lineage_lookup")
    freshness = _data(evidence, "freshness_check")
    volume = _data(evidence, "volume_check")
    null_amount = _data(evidence, "null_check")
    duplicate = _data(evidence, "duplicate_check")
    distribution = _data(evidence, "distribution_drift_check")

    profile = prof.get("profile", {})
    affected_amount = sum(
        profile.get(v, {}).get("deduction", 0) for v in drift.get("new_values", [])
    )
    handled_values = code.get("handled_values", [])
    missing_in_code = [v for v in drift.get("new_values", []) if v not in handled_values]

    # match có literal = dòng mapping thật (vd CASE WHEN ... 'REFUNDED') → trỏ đúng file/tầng chứa bug
    matches = code.get("matches", [])
    mapping = next((m for m in matches if "'" in (m.get("text") or "")), None)
    mapping = mapping or (matches[0] if matches else {})
    bug_file = mapping.get("file") or lineage.get("repo_path")

    tools_used = [item["source_tool"] for item in evidence if item.get("status") == "collected"]
    plan_steps = [
        {
            "step_id": item.get("step_id"),
            "tool": item.get("source_tool"),
            "evidence_type": item.get("evidence_type"),
            "status": item.get("status"),
            "summary": item.get("summary"),
        }
        for item in evidence
    ]

    return {
        "tools_used": tools_used,
        "plan_steps": plan_steps,
        "evidence": evidence,
        "scope": scope,
        "metadata": {
            "partition_key": meta.get("partition_key"),
            "known_values": meta.get("known_values", {}).get(scope["enum_field"], []),
            "last_profiled_at": meta.get("last_profiled_at"),
        },
        "sql_governance": prof.get("governance", {}).get("decision"),
        "group_profile": profile,
        "enum_drift": drift,
        "affected_amount": affected_amount,
        "code": {
            "repo_path": bug_file,
            "handled_values": handled_values,
            "missing_values": missing_in_code,
            "snippet": mapping.get("text"),
            "files_searched": code.get("files_searched", []),
        },
        "lineage": {
            "upstream": lineage.get("upstream"),
            "downstream": lineage.get("downstream"),
        },
        "quality_checks": {
            "freshness": freshness,
            "volume": volume,
            "null_amount": null_amount,
            "duplicate": duplicate,
            "distribution": distribution,
        },
    }


def run(state: dict, conn: Optional[sqlite3.Connection] = None) -> dict[str, Any]:
    """Plan (LLM hoặc fallback) → execute → derive → follow-up bounded → legacy summary."""
    registry = get_registry()
    scope = _infer_scope(state)
    task = _task(state, scope)
    executed: set[str] = set()
    counter = [0]
    evidence: list[EvidenceItem] = []

    # ── round 0: ưu tiên RUNBOOK đã học (memory) → LLM chọn tool → fallback fixed plan ──
    pack = state.get("context_pack") or {}
    known = [t for t in (pack.get("known_runbook_tools") or []) if t in GATHERING]
    if known:
        # incident tương tự đã có runbook → áp đúng bộ tool đó (learning → đổi hành vi thật)
        plan = _normalize([{"tool": t, "inputs": {}, "reason": "known runbook"} for t in known],
                          scope, executed, counter)
    else:
        raw = build_plan(task, registry, GATHERING)
        plan = _normalize(raw, scope, executed, counter) if raw is not None else []
    if not plan:
        plan = _fallback_plan(scope, executed, counter)
    evidence += execute_plan(plan, conn=conn, registry=registry)
    evidence += execute_plan(_derived_plan(scope, evidence, executed, counter),
                             conn=conn, registry=registry)

    # ── follow-up bounded: LLM xem evidence rồi xin thêm tool (tối đa N vòng) ──
    for _ in range(MAX_FOLLOWUP_ROUNDS):
        ev_summary = [{"tool": e["source_tool"], "summary": e.get("summary")}
                      for e in evidence if e.get("status") == "collected"]
        raw_more = build_plan(task, registry, GATHERING, evidence=ev_summary)
        if not raw_more:
            break
        extra = _normalize(raw_more, scope, executed, counter)
        if not extra:
            break
        evidence += execute_plan(extra, conn=conn, registry=registry)
        evidence += execute_plan(_derived_plan(scope, evidence, executed, counter),
                                 conn=conn, registry=registry)

    return _legacy_summary(scope, evidence)
