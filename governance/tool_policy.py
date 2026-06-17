"""tool_policy — tool nào được phép gọi, thuộc tier quyền nào (§12.2).

Agent không được tự do gọi tool. Tool ngoài allow-list → block. Tool ghi/đổi → cần approval (L2).
Deploy production → block trong MVP.
"""

from __future__ import annotations

from .approval_policy import PermissionTier, tier_of_action

# tool → action (để suy ra tier)
_TOOL_ACTION = {
    # L1 read-only diagnostics/retrieval
    "memory_search": "diagnostic",
    "rag_retrieve": "diagnostic",
    "metadata_scan": "diagnostic",
    "schema_diff": "diagnostic",
    "sql_profile": "read_only_sql",
    "freshness_check": "diagnostic",
    "volume_check": "diagnostic",
    "null_check": "diagnostic",
    "duplicate_check": "diagnostic",
    "distribution_drift_check": "diagnostic",
    "enum_drift_check": "diagnostic",
    "distribution_drift_check": "diagnostic",
    "lineage_lookup": "diagnostic",
    "code_search": "diagnostic",
    "deployment_log_search": "diagnostic",
    "impact_simulation": "diagnostic",
    "claim_verifier": "diagnostic",
    "evidence_mapper": "diagnostic",
    "contradiction_checker": "diagnostic",
    "trust_scorer": "diagnostic",
    "run_validation": "diagnostic",
    "generate_rca_report": "diagnostic",
    # MCP read-only (L1) — chỉ đọc trạng thái ngoài, không write
    "airflow_dag_status": "diagnostic",
    "gitlab_pipeline_status": "diagnostic",
    # MCP write (M2) — chỉ chạy sau HITL approval (apply_remediation gác ở graph)
    "airflow_trigger_dag": "rerun_partition",   # L3 reversible (backfill idempotent)
    "gitlab_create_mr": "create_mr",            # L2 — tạo proposal, cần approval
    # L2 assisted (cần approval)
    "generate_patch": "generate_patch",
    "review_patch": "generate_patch",
    "generate_dbt_test": "generate_test",
    "memory_writeback": "memory_writeback",
    # L3 safe-autonomous
    "retry_job": "retry_transient",
    "rerun_partition": "rerun_partition",
    "refresh_metadata": "refresh_metadata",
}

# tuyệt đối cấm trong MVP
_BLOCKED_TOOLS = {"deploy", "deploy_pipeline", "drop_table", "alter_table", "merge_pr"}


def check_tool(tool_name: str) -> dict:
    """Trả {tool, decision: allowed|blocked, tier, requires_approval, reason}."""
    if tool_name in _BLOCKED_TOOLS:
        return {"tool": tool_name, "decision": "blocked",
                "tier": None, "requires_approval": True,
                "reason": "Hành động deploy/DDL bị chặn trong MVP."}

    action = _TOOL_ACTION.get(tool_name)
    if action is None:
        return {"tool": tool_name, "decision": "blocked",
                "tier": None, "requires_approval": True,
                "reason": f"Tool '{tool_name}' không nằm trong allow-list."}

    tier = tier_of_action(action)
    requires_approval = tier == PermissionTier.L2_ASSISTED
    return {"tool": tool_name, "decision": "allowed",
            "tier": tier.value, "requires_approval": requires_approval,
            "reason": "ok"}
