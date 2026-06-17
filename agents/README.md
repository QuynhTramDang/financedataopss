# Agents

This directory does not define free-form "persona agents". In this project, an
agent is a governed reasoning component: each component has a narrow role, clear
inputs, structured outputs, and explicit constraints around evidence, policy,
fallbacks, and approval.

## Design Intent

This project uses AI for tasks that benefit from language understanding or soft
reasoning:

- classify the initial intent, metric, date, and risk
- propose a bounded diagnostic plan from the tool catalog
- summarize root cause from collected evidence
- review or comment on the business risk of a patch
- propose a candidate issue definition when a failure pattern is outside the
  current taxonomy

AI does not decide the final outcome by itself. Tool results, validation,
governance policy, claim verification, trust scoring, and human approval remain
the decision authority.

## Ground Rules

- Tool evidence beats LLM narrative.
- LLM output must be structured and schema-validated when routed through the
  model router.
- If the model is unavailable or returns invalid output, the workflow must still
  have deterministic fallback behavior.
- Raw transaction rows must not be passed into the LLM.
- Low-confidence or unknown cases must escalate instead of inventing a root
  cause.
- New issue types may be proposed as candidate definitions, but require human
  review before becoming detectors, runbooks, or memory.
- Finance-impacting changes require approval before remediation is applied.

## Component Roles

- `intent_classifier.py`: classifies a user request into intent, metric, date,
  and risk. Deterministic enrichment and finance risk overrides still apply.
- `context_retriever.py`: builds runtime context from memory and RAG documents.
- `diagnostic_planner.py`: builds a bounded diagnostic tool plan. The LLM may
  suggest tools, but governance and the executor decide what actually runs.
- `root_cause_reasoner.py`: reasons from collected evidence. It may use the LLM
  only to phrase a short narrative for confident cases.
- `issue_definer.py`: proposes candidate issue definitions for clearly signaled
  unknown patterns. It does not promote them into production rules.
- `patch_reviewer.py`: reviews patch risk textually, while approval and risk
  gates remain deterministic.
- `incident_agent.py`: triages job or log failures using controlled mappings
  and evidence.
- `lineage_qa.py`: answers read-only lineage and definition questions from
  known metadata and context.

## What Belongs Here

Put code in `agents/` when it coordinates reasoning around a business or data
ops task and produces a governed decision artifact, such as a plan, hypothesis,
classification, review, or escalation packet.

Put deterministic executable checks in `tools/`, policy decisions in
`governance/`, graph routing in `graph/`, and cross-tool execution concerns in
`orchestration/`.

## Unknown Issue Mode

When existing detectors do not match, the workflow should not force the case
into a known anomaly type. If the user request or evidence clearly suggests a
new pattern, the system may produce a `candidate_issue` with:

- `candidate_issue_type`
- description
- evidence pattern
- suggested tools
- confidence
- promotion path
- `requires_human_review = true`

This is a proposal only. Promotion into a real detector or runbook happens after
human review and approval.
