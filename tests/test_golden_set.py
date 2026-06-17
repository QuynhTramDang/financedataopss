"""Step 13 — Golden set eval (4 case gồm negative) + negative-case behavior."""

import pytest

from evals._harness import actual_final_status, ensure_seeded, load_golden, run_case


@pytest.fixture(scope="module", autouse=True)
def _seed():
    ensure_seeded()


@pytest.mark.parametrize("case", load_golden(), ids=lambda c: c["case_id"])
def test_golden_case(case):
    final = run_case(case)
    assert final.get("anomaly_type") == case["expected_anomaly"]
    assert final.get("confidence_route") == case["expected_route"]
    assert actual_final_status(final) == case["expected_final_status"]
    assert set(case["expected_tools"]) <= set(final.get("tool_plan", []))

    expected_patch = case.get("expected_patch_contains")
    patch = final.get("patch")
    if expected_patch:
        assert patch and expected_patch in patch["new_code"]
    else:
        assert patch is None


def test_negative_case_does_not_fabricate_root_cause():
    from graph.state import new_state
    from graph.workflow import build_workflow

    final = build_workflow().invoke(new_state("Revenue report 2026-06-10 nghi lệch nhưng chưa rõ"))
    assert final["anomaly_type"] is None
    assert final["confidence_route"] == "escalate"
    assert final["root_cause"] is None        # KHÔNG bịa root cause khi thiếu evidence
    assert final.get("patch") is None
    assert final["rca_report"]                 # vẫn có evidence pack để escalate


def test_all_evaluators_pass():
    from evals.evaluate_grounding import evaluate as ev_ground
    from evals.evaluate_patch import evaluate as ev_patch
    from evals.evaluate_root_cause import evaluate as ev_rc
    from evals.evaluate_tool_selection import evaluate as ev_tool

    assert ev_rc()
    assert ev_tool()
    assert ev_ground()
    assert ev_patch()


def test_eval_accuracy_measured():
    """B2: đo accuracy BẰNG SỐ trên golden set mở rộng (7 case, gồm duplicate/distribution/volume)."""
    from evals.evaluate_all import evaluate_all

    m = evaluate_all()
    assert m["cases"] == 7
    assert m["detection_accuracy"] == 1.0          # nhận đúng anomaly_type cả 7 ca
    assert m["routing_accuracy"] == 1.0
    assert m["tool_selection_accuracy"] == 1.0
    assert m["final_status_accuracy"] == 1.0
    assert m["grounding_accuracy"] == 1.0           # không bịa claim/patch
