"""Propose new issue definitions for unknown investigations.

This module does not promote a new detector by itself. It only creates a
candidate taxonomy entry from the user request and already-collected evidence so
the escalation packet can be reviewed, approved, and later converted into a
real detector/runbook.
"""

from __future__ import annotations

from typing import Any, Optional


def _has_signal(summary: dict[str, Any]) -> bool:
    if summary.get("evidence"):
        return True
    checks = summary.get("quality_checks", {}) or {}
    if any(v for v in checks.values() if v):
        return True
    return bool(summary.get("group_profile") or summary.get("lineage") or summary.get("code"))


def _issue_type(text: str, summary: dict[str, Any]) -> tuple[str, str, list[str], list[str]]:
    low = text.lower()
    if any(k in low for k in ("region", "province", "country", "segment", "dimension", "phan bo", "phân bổ")):
        return (
            "dimension_allocation_drift",
            "Metric total may reconcile, but allocation by a reporting dimension appears inconsistent.",
            [
                "overall metric reconciliation is not enough to explain the user-reported issue",
                "dimension-level split should be compared against source or prior baseline",
                "lineage/code should be inspected for changed join keys or mapping rules",
            ],
            ["dimension_reconciliation", "lineage_lookup", "code_search", "distribution_drift_check"],
        )
    if any(k in low for k in ("fx", "exchange", "currency", "ty gia", "tỷ giá", "ngoai te", "ngoại tệ")):
        return (
            "fx_rate_application_drift",
            "Amounts may be correct in source currency but wrong after exchange-rate application.",
            [
                "compare source amount, currency, rate date, and converted amount",
                "check whether rate date changed from transaction date to settlement/reporting date",
                "inspect transformation code that applies FX rates",
            ],
            ["sql_profile", "lineage_lookup", "code_search", "distribution_drift_check"],
        )
    if any(k in low for k in ("late", "delay", "tre", "trễ", "cham", "chậm")):
        return (
            "late_arriving_dimension_or_fact",
            "Facts or dimensions may arrive after the reporting cut-off and create temporary mismatch.",
            [
                "freshness/volume checks do not fully explain the reported mismatch",
                "compare event time, load time, and reporting cut-off",
                "inspect upstream schedule and late-arriving data policy",
            ],
            ["freshness_check", "volume_check", "lineage_lookup", "log_search"],
        )
    if summary.get("code", {}).get("files_searched"):
        return (
            "unclassified_transformation_logic_drift",
            "Evidence points to a transformation or metric-definition issue that is not covered by current detectors.",
            [
                "standard detectors did not match",
                "code/lineage evidence exists and should be reviewed for a new detector pattern",
            ],
            ["code_search", "lineage_lookup", "sql_profile"],
        )
    return (
        "unclassified_data_quality_issue",
        "The investigation has evidence, but no current detector can classify the failure pattern.",
        [
            "standard detectors did not match",
            "collected evidence should be reviewed to define a reusable issue pattern",
        ],
        ["sql_profile", "freshness_check", "volume_check", "null_check", "lineage_lookup"],
    )


def _has_candidate_cue(text: str, summary: dict[str, Any]) -> bool:
    low = text.lower()
    cue_terms = (
        "region", "province", "country", "segment", "dimension", "phan bo", "phân bổ",
        "fx", "exchange", "currency", "ty gia", "tỷ giá", "ngoai te", "ngoại tệ",
        "late", "delay", "tre", "trễ", "cham", "chậm",
    )
    return any(k in low for k in cue_terms) or bool(summary.get("candidate_issue_hint"))


def propose_issue_definition(state: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Return a candidate issue definition, or None when there is no usable signal."""
    summary = state.get("tool_results_summary", {}) or {}
    request = state.get("user_request") or ""
    if not _has_signal(summary) and not request.strip():
        return None
    if not _has_candidate_cue(request, summary):
        return None

    issue_type, description, evidence_pattern, suggested_tools = _issue_type(request, summary)
    return {
        "candidate_issue_type": issue_type,
        "description": description,
        "evidence_pattern": evidence_pattern,
        "suggested_tools": suggested_tools,
        "confidence": 0.35 if issue_type.startswith("unclassified") else 0.45,
        "status": "proposed",
        "requires_human_review": True,
        "promotion_path": [
            "review evidence packet",
            "approve or edit candidate issue definition",
            "add detector and remediation strategy",
            "write approved runbook/memory entry",
        ],
    }
