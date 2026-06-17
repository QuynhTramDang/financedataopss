"""Observability export — trace-id, cost USD, concurrency-safe trace, export JSONL/seam."""

import os

from observability import (
    cost_of,
    current_trace_id,
    export_trace,
    get_trace,
    totals,
)
from observability.export import export_jsonl
from observability.trace_logger import log_event, reset_trace


def test_cost_of_by_model():
    assert cost_of("claude-opus-4-8", 1_000_000, 0) == 15.0
    assert cost_of(None, 1000, 1000) == 0.0          # model lạ → không đoán giá


def test_trace_id_seq_cost_and_isolation():
    tid = reset_trace("trace-x")
    assert tid == "trace-x" and current_trace_id() == "trace-x"
    log_event({"node": "n1", "model": "claude-opus-4-8",
               "input_tokens": 1_000_000, "output_tokens": 0, "latency_ms": 5})
    tr = get_trace()
    assert len(tr) == 1
    assert tr[0]["trace_id"] == "trace-x" and tr[0]["seq"] == 0
    assert tr[0]["cost_usd"] == 15.0
    reset_trace("trace-y")                            # trace mới → list sạch (không đè)
    assert get_trace() == [] and current_trace_id() == "trace-y"


def test_totals_includes_cost():
    reset_trace()
    log_event({"node": "n", "model": "claude-haiku-4-5-20251001",
               "input_tokens": 1_000_000, "output_tokens": 0})
    tot = totals(get_trace())
    assert tot["cost_usd"] == 1.0 and tot["input_tokens"] == 1_000_000


def test_export_jsonl_writes_file(tmp_path):
    reset_trace("trace-file")
    log_event({"node": "n", "latency_ms": 1})
    path = export_jsonl(get_trace(), path=str(tmp_path / "t.jsonl"))
    assert os.path.exists(path)
    assert "trace-file" in (tmp_path / "t.jsonl").read_text(encoding="utf-8")


def test_export_trace_offline_uses_jsonl(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    reset_trace("trace-exp")
    log_event({"node": "n", "latency_ms": 1})
    summary = export_trace()
    assert summary["trace_id"] == "trace-exp" and summary["events"] == 1
    assert summary["export"]["status"] == "jsonl"
    assert "cost_usd" in summary


def test_workflow_trace_tagged_with_investigation_id():
    from data.seed_data.seed import main as seed_main
    from graph.state import new_state
    from graph.workflow import build_workflow

    seed_main()
    build_workflow().invoke(new_state("Revenue 2026-06-07 lệch 2.1%", investigation_id="INV-OBS"))
    tr = get_trace()
    assert tr and all(e.get("trace_id") == "INV-OBS" for e in tr)
