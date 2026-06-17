"""Step 14 — Observability: trace per-node, token totals, 0 raw rows guard."""

from observability import assert_no_raw_rows, get_trace, totals, within_budget
from observability.token_tracker import per_node


def _run():
    from data.seed_data.seed import main as seed_main
    from graph.state import new_state
    from graph.workflow import build_workflow
    seed_main()
    return build_workflow().invoke(new_state("Revenue 2026-06-07 lệch 2.1%"))


def test_trace_has_event_per_executed_node():
    final = _run()
    trace = get_trace()
    trace_nodes = {e["node"] for e in trace}
    timeline_nodes = {e["node"] for e in final["timeline"] if e["node"] != "state_init"}
    # mỗi node chạy (trừ state_init nằm trong new_state) đều có event observability
    assert timeline_nodes <= trace_nodes
    assert all("latency_ms" in e for e in trace)


def test_no_raw_rows_to_llm():
    final = _run()
    assert assert_no_raw_rows(final) == []     # §13: 0 raw row vào LLM


def test_token_totals_and_budget():
    _run()
    trace = get_trace()
    tot = totals(trace)
    assert "input_tokens" in tot and "output_tokens" in tot
    # offline (fallback, không LLM) → 0 token, đương nhiên trong budget
    assert within_budget(trace) is True


def test_per_node_breakdown_shape():
    _run()
    rows = per_node(get_trace())
    assert rows and all({"node", "model", "input_tokens", "latency_ms"} <= set(r) for r in rows)


def test_guard_detects_injected_raw_rows():
    bad_state = {"tool_results_summary": {"sample": [{"txn_id": 1, "amount": 100}]}}
    assert assert_no_raw_rows(bad_state) != []   # phát hiện raw row có txn_id
