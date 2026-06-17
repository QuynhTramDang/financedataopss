"""claim_policy — rule engine kiểm chứng claim DETERMINISTIC (§14.2.2, §14.2.3).

LLM tách claim; RULE ENGINE này quyết status:
  - business_decision (op=always_requires_approval) → 'requires_approval' (luôn).
  - các claim khác: resolve evidence_value từ tool_results_summary theo field, áp op:
      contains / > / < / eq / abs_diff_lt → 'verified' nếu khớp, ngược lại 'unsupported'.
  - field không resolve được (thiếu evidence) → 'unsupported'.
"""

from __future__ import annotations

from typing import Any


def _resolve(summary: dict, field: str) -> Any:
    cur: Any = summary
    for part in field.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _apply_op(op: str, evidence: Any, value: Any) -> bool:
    if evidence is None:
        return False
    if op == "contains":
        return value in evidence
    if op == ">":
        return evidence > value
    if op == "<":
        return evidence < value
    if op == "eq":
        return evidence == value
    if op == "abs_diff_lt":
        return abs(evidence - value["target"]) < value["tolerance"]
    return False


def verify_claims(claims: list[dict], tool_results_summary: dict) -> dict[str, Any]:
    """Gán status cho từng claim. Trả {claims, summary counts, has_critical_unsupported}."""
    verified = unsupported = requires_approval = 0
    for c in claims:
        check = c.get("check", {})
        op = check.get("op")
        if op == "always_requires_approval":
            c["status"] = "requires_approval"
            c["evidence_value"] = None
            requires_approval += 1
            continue

        evidence = _resolve(tool_results_summary, check.get("field", ""))
        c["evidence_value"] = evidence
        if _apply_op(op, evidence, check.get("value")):
            c["status"] = "verified"
            verified += 1
        else:
            c["status"] = "unsupported"
            unsupported += 1

    # claim quan trọng (data_fact/code_fact/quantitative) mà unsupported → critical
    has_critical_unsupported = any(
        c["status"] == "unsupported" and c["claim_type"] != "business_decision"
        for c in claims
    )
    return {
        "claims": claims,
        "verified": verified,
        "unsupported": unsupported,
        "requires_approval": requires_approval,
        "has_critical_unsupported": has_critical_unsupported,
    }
