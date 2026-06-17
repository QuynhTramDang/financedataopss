# Agentic Orchestration Architecture

This project is moving from a fixed investigation pipeline toward a
planner-driven agent platform. The current migration keeps governance, local
tools, evals, memory, and validation intact while replacing hard-coded
orchestration in small slices.

## Target Shape

```text
request
  -> intent / risk / scope classification
  -> context + retrieval
  -> planner
  -> tool registry
  -> governed executor
  -> evidence store
  -> verifier / critic
  -> decision router
      -> gather more evidence
      -> report / escalate
      -> propose patch
      -> request human approval
```

The graph should own lifecycle and routing. The planner should own which tools
to call. Governance remains the final authority before any tool execution.

## Current Migration Slice

- `orchestration.models` defines `PlanStep` and `EvidenceItem`.
- `orchestration.registry` is the canonical registry for local tools.
- `orchestration.executor` runs plan steps through registry + governance and
  returns normalized evidence.
- `agents.diagnostic_planner` now builds a plan, executes it, and maps evidence
  back to the legacy `tool_results_summary` contract.
- `graph.state` carries `plan_steps` and `evidence` so future nodes can become
  evidence-first without breaking the existing UI/tests.

This means the graph still looks mostly fixed today, but the diagnostic section
has been converted into a planner/executor/evidence loop internally.

## Tool Registry Rules

Every tool should have one registry record with:

- `name`
- `capability`
- `description`
- `input_schema`
- `output_schema`
- `evidence_type`
- `source`: `local` or `mcp`
- governance decision via `governance.tool_policy.check_tool`

Adding a new diagnostic should usually mean adding a tool record plus a planner
rule, not editing graph edges.

## MCP Integration Direction

MCP should be used as the integration boundary for external systems such as
Airflow, GitLab, Teams, Jira, Datadog, or Confluence. It should not replace
local deterministic domain tools such as SQL profiling, reconciliation,
impact simulation, trust scoring, or claim verification.

Recommended boundary:

```text
planner
  -> internal tool registry
  -> MCP gateway / broker
  -> allow-listed MCP server/tool
  -> external system
```

Do not let the agent call arbitrary MCP servers directly. MCP-backed tools
should be registered like local tools and governed with the same risk tiers,
approval rules, audit logging, timeout, and output normalization.

`orchestration.mcp_gateway` is currently a safety-first stub. The first real
implementation should wrap a vetted MCP client and only expose approved
server/tool pairs.

## Next Refactor Steps

1. Move scope inference out of `diagnostic_planner` into a dedicated scope
   classifier.
2. Replace the fixed diagnostic plan with policy-driven plan generation based
   on intent, metric, pipeline, and missing evidence.
3. Convert `root_cause_reasoner`, `claim_verifier`, and `trust_scorer` to read
   normalized `EvidenceItem` objects instead of legacy summary fields.
4. Add LangGraph checkpoint/store support for durable human-in-the-loop runs.
5. Register read-only MCP tools first, for example Airflow DAG/task inspection
   and GitLab pipeline/MR read operations.
6. Add write/action MCP tools only after approval gates and audit logs are in
   place, for example Airflow retry, GitLab MR creation, and Teams approval
   notifications.
