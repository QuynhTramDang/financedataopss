"""A2 — planner-driven tool selection (orchestrator-workers, bounded) + executor gates."""

import pytest

from agents.diagnostic_planner import _infer_scope, _normalize
from data.seed_data.seed import AFFECTED_AMOUNT, PRIMARY_TXN_DATE, seed_database
from database.connection import get_connection
from model_router.providers import ProviderUnavailable
from orchestration.executor import execute_plan
from orchestration.planner import build_plan
from orchestration.registry import ToolRecord, ToolRegistry, get_registry

GATHERING = {
    "metadata_scan", "sql_profile", "freshness_check", "volume_check",
    "null_check", "code_search", "lineage_lookup",
}


@pytest.fixture()
def conn():
    c = get_connection(":memory:")
    seed_database(c)
    yield c
    c.close()


def _mkstep(sid, tool, inputs=None, depends_on=None):
    return {"id": sid, "tool": tool, "capability": "x", "reason": "t",
            "inputs": inputs or {}, "depends_on": depends_on or [], "expected_evidence": "x"}


# ── executor: governance + dependency gate (nit #2) + status collected (nit #3) ──
def test_executor_blocks_and_skips_dependent():
    reg = ToolRegistry(records={
        "deploy": ToolRecord(name="deploy", capability="x", description="",
                             input_schema={"type": "object"}, output_schema={},
                             evidence_type="x", fn=None),
        "metadata_scan": get_registry().get("metadata_scan"),
    })
    plan = [_mkstep("s1", "deploy"),
            _mkstep("s2", "metadata_scan", {"table": "payment_txn"}, ["s1"])]
    ev = {e["step_id"]: e for e in execute_plan(plan, registry=reg)}
    assert ev["s1"]["status"] == "blocked"      # governance chặn deploy
    assert ev["s2"]["status"] == "skipped"      # dependency fail → skip


def test_executor_collected_and_unregistered():
    ev = execute_plan([_mkstep("s1", "metadata_scan", {"table": "payment_txn"})])
    assert ev[0]["status"] == "collected"
    ev2 = execute_plan([_mkstep("s1", "does_not_exist")])
    assert ev2[0]["status"] == "error"


# ── planner: LLM đề xuất, fallback khi không model ──
class _FakeRouter:
    def __init__(self, steps):
        self._steps = steps

    def call_structured(self, route, prompt, schema, system=None):
        return {"steps": self._steps}


class _DeadRouter:
    def call_structured(self, *a, **k):
        raise ProviderUnavailable("no model")


def test_build_plan_returns_raw_steps():
    raw = build_plan({"metric": "net_revenue"}, get_registry(), GATHERING,
                     router=_FakeRouter([{"tool": "sql_profile", "inputs": {}}]))
    assert raw == [{"tool": "sql_profile", "inputs": {}}]


def test_build_plan_none_when_no_model():
    assert build_plan({"metric": "x"}, get_registry(), GATHERING, router=_DeadRouter()) is None


def test_normalize_drops_unknown_and_enriches():
    scope = _infer_scope({"date": PRIMARY_TXN_DATE, "metric": "net_revenue"})
    raw = [{"tool": "sql_profile", "inputs": {}},
           {"tool": "enum_drift_check", "inputs": {}},  # derived, không phải gathering → bỏ
           {"tool": "bogus"}]                            # không có thật → bỏ
    steps = _normalize(raw, scope, set(), [0])
    assert [s["tool"] for s in steps] == ["sql_profile"]
    sp = steps[0]["inputs"]
    assert sp == {"txn_date": PRIMARY_TXN_DATE, "table": "payment_txn", "group_col": "refund_status",
                  "measure_column": "amount", "deduction_column": "refunded_amount"}


# ── tích hợp: planner-driven path (LLM chọn tool) ──
def test_diagnostic_planner_uses_llm_plan(monkeypatch, conn):
    import agents.diagnostic_planner as dp

    def fake_build(task, registry, allowed, evidence=None):
        if evidence is not None:
            return []  # không follow-up
        return [{"tool": t, "inputs": {}, "reason": "llm"}
                for t in ["metadata_scan", "sql_profile", "code_search"]]

    monkeypatch.setattr(dp, "build_plan", fake_build)
    summary = dp.run({"date": PRIMARY_TXN_DATE, "metric": "net_revenue"}, conn=conn)

    # enum_drift là phép dẫn xuất → vẫn chạy dù LLM không chọn
    assert summary["enum_drift"]["new_values"] == ["PARTIAL_REFUND"]
    assert summary["affected_amount"] == AFFECTED_AMOUNT
    assert "enum_drift_check" in summary["tools_used"]
    # LLM KHÔNG chọn volume/null → không chạy (bằng chứng plan động, không vẹt)
    assert "volume_check" not in summary["tools_used"]
    assert "null_check" not in summary["tools_used"]


# ── A3: scope suy từ metric_memory + metadata (bỏ hardcode) ──
def test_scope_derived_from_metric_memory():
    scope = _infer_scope({"date": PRIMARY_TXN_DATE, "metric": "net_revenue"})
    assert scope["table"] == "payment_txn"          # metric_memory.source_tables[0]
    assert scope["pipeline"] == "dtm_revenue_daily"  # metric_memory.pipeline
    assert scope["enum_field"] == "refund_status"    # metadata known_values key
    assert scope["null_column"] == "amount"          # metadata measure_columns[0]


def test_scope_generalizes_to_other_metric():
    # metric khác (order_volume trên order_fact) → scope suy hoàn toàn từ contract, không cứng revenue
    scope = _infer_scope({"date": PRIMARY_TXN_DATE, "metric": "order_volume"})
    assert scope["table"] == "order_fact"
    assert scope["enum_field"] == "region"
    assert scope["null_column"] == "order_amount"
    assert scope["pipeline"] == "ods_payment_enriched"


def test_scope_fails_loud_without_metric():
    from domain.contracts import ContractError
    with pytest.raises(ContractError):
        _infer_scope({"date": PRIMARY_TXN_DATE})   # thiếu metric → fail-loud, KHÔNG đoán revenue


# ── code_search đa-file theo lineage: chỉ đúng tầng chứa bug ──
def test_code_search_across_lineage_points_to_ods():
    from tools.code_search import code_search
    res = code_search("refund_status", repo_paths=[
        "pipelines/models/finance/dtm_revenue_daily.sql",   # không có refund_status literal
        "pipelines/models/ods/ods_payment_enriched.sql",    # CASE bug ở đây
        "pipelines/models/staging/stg_payment.sql",
    ])
    assert "REFUNDED" in res["handled_values"]
    assert "PARTIAL_REFUND" not in res["handled_values"]
    files_hit = {m["file"] for m in res["matches"]}
    assert "pipelines/models/ods/ods_payment_enriched.sql" in files_hit


def test_lineage_files_walk_upstream():
    from agents.diagnostic_planner import _lineage_files
    files = _lineage_files("dtm_revenue_daily")
    assert "pipelines/models/ods/ods_payment_enriched.sql" in files
    assert "pipelines/models/finance/dtm_revenue_daily.sql" in files


def test_diagnostic_summary_points_to_bug_file(conn):
    import agents.diagnostic_planner as dp
    # metric net_revenue → pipeline dtm → code_search quét lineage → trỏ đúng ods (tầng chứa CASE bug)
    summary = dp.run({"date": PRIMARY_TXN_DATE, "metric": "net_revenue"}, conn=conn)
    assert summary["code"]["missing_values"] == ["PARTIAL_REFUND"]
    assert "ods_payment_enriched.sql" in (summary["code"]["repo_path"] or "")
    assert "'REFUNDED'" in (summary["code"]["snippet"] or "")
