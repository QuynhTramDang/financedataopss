"""Canonical tool registry for local and MCP-backed tools.

The registry is the contract between planner, governance, and execution. It
keeps tool metadata in one place so new capabilities can be added without
rewiring the graph.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from governance.tool_policy import check_tool
from tools.code_search import code_search
from tools.distribution_drift_check import distribution_drift_check
from tools.duplicate_check import duplicate_check
from tools.enum_drift_check import enum_drift_check
from tools.freshness_check import freshness_check
from tools.lineage_lookup import lineage_lookup
from tools.metadata_scan import metadata_scan
from tools.null_check import null_check
from tools.sql_profile import sql_profile
from tools.volume_check import volume_check


@dataclass(frozen=True)
class ToolRecord:
    name: str
    capability: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    evidence_type: str
    source: str = "local"
    allowed_intents: tuple[str, ...] = ()
    fn: Optional[Callable[..., Any]] = None
    mcp_server: Optional[str] = None
    mcp_tool: Optional[str] = None
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def governance(self) -> dict[str, Any]:
        return check_tool(self.name)


def _schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _build_records() -> dict[str, ToolRecord]:
    records = [
        ToolRecord(
            name="metadata_scan",
            capability="metadata_baseline",
            description="Read cached schema, partition key, and known enum values for a table.",
            input_schema=_schema({"table": {"type": "string"}}, ["table"]),
            output_schema={"type": "object"},
            evidence_type="metadata_profile",
            fn=metadata_scan,
            tags=("diagnostic", "read_only"),
        ),
        ToolRecord(
            name="sql_profile",
            capability="data_profile",
            description="Run governed aggregate SQL profile for one partition.",
            input_schema=_schema(
                {
                    "txn_date": {"type": "string"},
                    "table": {"type": "string"},
                    "group_col": {"type": "string"},
                    "measure_column": {"type": "string"},
                    "deduction_column": {"type": ["string", "null"]},
                },
                ["txn_date", "table", "group_col", "measure_column"],
            ),
            output_schema={"type": "object"},
            evidence_type="aggregate_profile",
            fn=sql_profile,
            tags=("diagnostic", "sql", "read_only"),
        ),
        ToolRecord(
            name="enum_drift_check",
            capability="enum_drift_detection",
            description="Compare actual enum values against a known baseline.",
            input_schema=_schema(
                {"actual_values": {"type": "array"}, "known_values": {"type": "array"}},
                ["actual_values", "known_values"],
            ),
            output_schema={"type": "object"},
            evidence_type="enum_drift",
            fn=enum_drift_check,
            tags=("diagnostic", "read_only"),
        ),
        ToolRecord(
            name="code_search",
            capability="code_capability_check",
            description="Find related pipeline code and handled enum values across lineage files.",
            input_schema=_schema(
                {"pattern": {"type": "string"}, "repo_paths": {"type": "array"}},
                ["pattern"],
            ),
            output_schema={"type": "object"},
            evidence_type="code_evidence",
            fn=code_search,
            tags=("diagnostic", "read_only"),
        ),
        ToolRecord(
            name="lineage_lookup",
            capability="lineage_lookup",
            description="Look up upstream, downstream, and repository path for an asset.",
            input_schema=_schema({"asset": {"type": "string"}}, ["asset"]),
            output_schema={"type": "object"},
            evidence_type="lineage",
            fn=lineage_lookup,
            tags=("diagnostic", "read_only"),
        ),
        ToolRecord(
            name="freshness_check",
            capability="freshness_check",
            description="Check whether a date partition has loaded rows.",
            input_schema=_schema({"txn_date": {"type": "string"}, "table": {"type": "string"}},
                                 ["txn_date", "table"]),
            output_schema={"type": "object"},
            evidence_type="freshness",
            fn=freshness_check,
            tags=("diagnostic", "read_only"),
        ),
        ToolRecord(
            name="volume_check",
            capability="volume_check",
            description="Compare current partition volume with baseline.",
            input_schema=_schema({"txn_date": {"type": "string"}, "table": {"type": "string"}},
                                 ["txn_date", "table"]),
            output_schema={"type": "object"},
            evidence_type="volume",
            fn=volume_check,
            tags=("diagnostic", "read_only"),
        ),
        ToolRecord(
            name="null_check",
            capability="null_spike_check",
            description="Measure null rate for an important column in one partition.",
            input_schema=_schema(
                {
                    "txn_date": {"type": "string"},
                    "table": {"type": "string"},
                    "column": {"type": "string"},
                },
                ["txn_date", "table", "column"],
            ),
            output_schema={"type": "object"},
            evidence_type="null_profile",
            fn=null_check,
            tags=("diagnostic", "read_only"),
        ),
        ToolRecord(
            name="duplicate_check",
            capability="duplicate_detection",
            description="Count business-key duplicates in a partition (double-count signal).",
            input_schema=_schema({"txn_date": {"type": "string"}, "table": {"type": "string"},
                                  "key_col": {"type": "string"}},
                                 ["txn_date", "table", "key_col"]),
            output_schema={"type": "object"},
            evidence_type="duplicate",
            fn=duplicate_check,
            tags=("diagnostic", "read_only"),
        ),
        ToolRecord(
            name="distribution_drift_check",
            capability="distribution_drift_detection",
            description="Compare today's measure distribution with historical baseline.",
            input_schema=_schema({"txn_date": {"type": "string"}, "table": {"type": "string"},
                                  "measure_col": {"type": "string"}},
                                 ["txn_date", "table", "measure_col"]),
            output_schema={"type": "object"},
            evidence_type="distribution",
            fn=distribution_drift_check,
            tags=("diagnostic", "read_only"),
        ),
        # ── MCP-backed tools (read-only trước; gọi qua mcp_gateway, không có fn local) ──
        ToolRecord(
            name="airflow_dag_status",
            capability="pipeline_run_status",
            description="Read Airflow DAG/task run status for a partition (via MCP).",
            input_schema=_schema({"dag_id": {"type": "string"}, "run_date": {"type": "string"}},
                                 ["dag_id"]),
            output_schema={"type": "object"},
            evidence_type="pipeline_status",
            source="mcp", mcp_server="airflow", mcp_tool="get_dag_run_status",
            tags=("mcp", "read_only"),
        ),
        ToolRecord(
            name="gitlab_pipeline_status",
            capability="ci_status",
            description="Read GitLab pipeline / MR status for a ref (via MCP).",
            input_schema=_schema({"project": {"type": "string"}, "ref": {"type": "string"}}, []),
            output_schema={"type": "object"},
            evidence_type="ci_status",
            source="mcp", mcp_server="gitlab", mcp_tool="get_pipeline_status",
            tags=("mcp", "read_only"),
        ),
        # ── MCP write tools (M2) — chỉ chạy sau HITL approval (node apply_remediation) ──
        ToolRecord(
            name="airflow_trigger_dag",
            capability="pipeline_trigger",
            description="Trigger an Airflow DAG run / backfill for a partition (via MCP, write).",
            input_schema=_schema({"dag_id": {"type": "string"}, "run_date": {"type": "string"}},
                                 ["dag_id"]),
            output_schema={"type": "object"},
            evidence_type="trigger_result",
            source="mcp", mcp_server="airflow", mcp_tool="trigger_dag_run",
            tags=("mcp", "write"),
        ),
        ToolRecord(
            name="gitlab_create_mr",
            capability="create_merge_request",
            description="Create a GitLab merge request with patch + RCA (via MCP, write).",
            input_schema=_schema(
                {"title": {"type": "string"}, "description": {"type": "string"},
                 "source_branch": {"type": "string"}, "target_branch": {"type": "string"}},
                ["title"]),
            output_schema={"type": "object"},
            evidence_type="mr_result",
            source="mcp", mcp_server="gitlab", mcp_tool="create_merge_request",
            tags=("mcp", "write"),
        ),
    ]
    return {r.name: r for r in records}


class ToolRegistry:
    def __init__(self, records: Optional[dict[str, ToolRecord]] = None):
        self._records = records or _build_records()

    def get(self, name: str) -> ToolRecord:
        if name not in self._records:
            raise KeyError(f"Tool '{name}' is not registered.")
        return self._records[name]

    def list(self, *, capability: Optional[str] = None, source: Optional[str] = None) -> list[ToolRecord]:
        records = list(self._records.values())
        if capability:
            records = [r for r in records if r.capability == capability]
        if source:
            records = [r for r in records if r.source == source]
        return records

    def register(self, record: ToolRecord) -> None:
        self._records[record.name] = record


_REGISTRY = ToolRegistry()


def get_registry() -> ToolRegistry:
    return _REGISTRY
