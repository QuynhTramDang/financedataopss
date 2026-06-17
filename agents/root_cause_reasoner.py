"""Root-cause reasoning from verified evidence.

Tool evidence remains the source of truth. The LLM is only used to phrase a
short narrative for confident, evidence-backed cases. When known detectors do
not match, the reasoner may create a candidate issue definition, but it does
not promote that candidate into a production detector.
"""

from __future__ import annotations

from typing import Any

from agents.detectors import classify as _classify
from agents.issue_definer import propose_issue_definition
from model_router import ProviderError, get_router

CONFIDENCE_THRESHOLD = 0.6


def _narrative(missing: list[str], summary: dict, router, metric_label: str = "metric") -> str:
    repo = summary.get("code", {}).get("repo_path", "pipeline")
    template = (
        f"Source has new value(s) {missing}, but {repo} only handles "
        f"{summary.get('code', {}).get('handled_values')}, causing {metric_label} to be overstated."
    )
    try:
        out = router.call_structured(
            route="planner",
            prompt=(
                "Summarize the root cause in 1-2 sentences using only this evidence: "
                f"{summary}"
            ),
            schema={
                "type": "object",
                "properties": {"root_cause": {"type": "string"}},
                "required": ["root_cause"],
                "additionalProperties": False,
            },
            system="You are a senior data engineer. Conclude only from supplied evidence.",
        )
        return out["root_cause"]
    except (ProviderError, Exception):  # noqa: BLE001 - offline/model failure keeps flow deterministic
        return template


def reason(state: dict, router=None) -> dict[str, Any]:
    """Return reasoning result, including a candidate issue for unmatched patterns."""
    summary = state.get("tool_results_summary", {}) or {}
    txn_date = state.get("date")
    cls = _classify(summary, txn_date)
    candidate_issue = None

    route = cls["route"]
    if route == "confident" and cls["confidence"] >= CONFIDENCE_THRESHOLD:
        router = router or get_router()
        root_cause = _narrative(cls["missing"], summary, router, state.get("metric") or "metric")
    elif cls["root_cause_hint"] and cls["root_cause_hint"] != "code_patch":
        root_cause = cls["root_cause_hint"]
    else:
        candidate_issue = propose_issue_definition(state)
        root_cause = None

    anomaly_type = cls["anomaly_type"] or ("unknown_issue" if candidate_issue else None)
    hypothesis_root = root_cause or (
        f"Candidate issue: {candidate_issue['candidate_issue_type']}"
        if candidate_issue else f"Not enough evidence (confidence={cls['confidence']})"
    )
    hypotheses = [{
        "root_cause": hypothesis_root,
        "confidence": cls["confidence"],
        "anomaly_type": anomaly_type,
        "evidence": cls["evidence"],
        "candidate_issue": candidate_issue,
    }]
    return {
        "hypotheses": hypotheses,
        "root_cause": root_cause,
        "confidence": cls["confidence"],
        "confidence_route": route,
        "anomaly_type": anomaly_type,
        "fix_type": cls["fix_type"],
        "candidate_issue": candidate_issue,
    }
