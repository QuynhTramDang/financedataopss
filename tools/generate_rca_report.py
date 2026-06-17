"""generate_rca_report — sinh RCA markdown (§18.2) từ state.

Template DETERMINISTIC để số liệu chính xác (không hallucinate). LLM có thể tinh chỉnh prose nhưng
KHÔNG được đổi số — ở đây ta dựng trực tiếp từ evidence/validation đã verify.
"""

from __future__ import annotations

from typing import Any


def _pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def generate_rca_report(state: dict) -> str:
    inv = state.get("investigation_id", "INV-?")
    date = state.get("date", "?")
    metric = state.get("metric") or "metric"
    root_cause = state.get("root_cause") or "Chưa kết luận (escalate)"
    summary = state.get("tool_results_summary", {}) or {}
    impact = state.get("impact_analysis", {}) or {}
    validation = state.get("validation_result", {}) or {}
    claims = state.get("claims", []) or []
    trust = state.get("trust_matrix", {}) or {}
    patch = state.get("patch", {}) or {}

    affected = impact.get("affected_amount", 0)
    before = impact.get("before_fix_diff", 0)
    after = impact.get("after_fix_diff", 0)

    claim_rows = "\n".join(
        f"| {c['claim']} | {', '.join(c.get('required_evidence', []))} | {c['status']} |"
        for c in claims
    )
    trust_rows = "\n".join(f"- {k}: {v}" for k, v in trust.items())
    tests_passed = f"{validation.get('passed', 0)}/{validation.get('total', 0)}"

    return f"""# Root Cause Analysis Report — {inv}

## Incident Summary
Báo cáo {metric} cho {date} bị lệch (overstated).

## Root Cause
{root_cause}

## Evidence
- enum_drift: {summary.get('enum_drift', {}).get('new_values')}
- affected_amount: {affected:,} VND
- code missing mapping: {summary.get('code', {}).get('missing_values')}
- reconciliation trước fix: {_pct(before)}; sau fix: {_pct(after)}

## Claim Verification
| Claim | Evidence | Status |
|---|---|---|
{claim_rows}

## Trust Matrix
{trust_rows}

## Business Impact
- {metric} overstated {_pct(before)}.
- Affected amount: {affected:,} VND.
- Affected report: {impact.get('affected_report')}.

## Proposed Fix
- File: {patch.get('target_file')}
- {patch.get('old_code')}  →  {patch.get('new_code')}
- Reason: {patch.get('reason')}

## Validation Result
- Before fix mismatch: {_pct(before)}
- After fix mismatch: {_pct(after)}
- Tests passed: {tests_passed}

## Approval Required
Finance Owner và Data Owner approval trước khi publish lại số.

## Rollback Plan
{patch.get('rollback_plan', 'Revert patch và restore partition trước đó.')}
"""
