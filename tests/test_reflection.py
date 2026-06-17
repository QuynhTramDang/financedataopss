"""#1 Reflection loop — validation FAIL → critique + refine + re-validate (bounded), không đi thẳng RCA."""

import pytest

from graph.conditions import MAX_VALIDATION_ATTEMPTS, route_validation


def _seed_and_app():
    from data.seed_data.seed import main as seed_main
    from graph.workflow import build_workflow
    seed_main()
    return build_workflow()


def _fake_validation(statuses):
    """Trả callable run_validation giả: lần lượt theo `statuses` (PASS/FAIL)."""
    calls = {"n": 0}

    def fake(txn_date, new_values, contract, conn=None):
        i = calls["n"]
        calls["n"] += 1
        status = statuses[i] if i < len(statuses) else statuses[-1]
        diff = 0.0 if status == "PASS" else 0.02
        return {"validation_status": status, "tests": [], "passed": 1 if status == "PASS" else 0,
                "total": 1, "reconciliation": {"before_fix_diff": 0.02, "after_fix_diff": diff}}

    fake.calls = calls
    return fake


# ── unit: routing ────────────────────────────────────────────
def test_route_validation():
    assert route_validation({"validation_result": {"validation_status": "PASS"}}) == "ok"
    assert route_validation({"validation_result": {"validation_status": "FAIL"},
                             "validation_attempts": 0}) == "retry"
    assert route_validation({"validation_result": {"validation_status": "FAIL"},
                             "validation_attempts": MAX_VALIDATION_ATTEMPTS}) == "giveup"


# ── pass first try → KHÔNG loop (real data) ──────────────────
def test_validation_passes_first_try_no_reflection():
    from graph.state import new_state
    final = _seed_and_app().invoke(new_state("Revenue 2026-06-07 lệch 2.1%"))
    nodes = [e["node"] for e in final["timeline"]]
    assert "refine_patch" not in nodes              # data thật pass ngay → không cần reflection
    assert "trust_scorer" in nodes


# ── FAIL rồi PASS → reflection sửa rồi đi tiếp ───────────────
def test_reflection_retries_then_proceeds(monkeypatch):
    import tools.run_validation as rv
    from graph.state import new_state
    fake = _fake_validation(["FAIL", "PASS"])
    monkeypatch.setattr(rv, "run_validation", fake)

    final = _seed_and_app().invoke(new_state("Revenue 2026-06-07 lệch 2.1%"))
    nodes = [e["node"] for e in final["timeline"]]
    assert "refine_patch" in nodes                  # đã critique + sửa
    assert nodes.count("validation_engine") == 2    # re-validate sau refine
    assert "trust_scorer" in nodes                  # PASS lần 2 → đi tiếp RCA
    assert "escalate" not in nodes
    assert fake.calls["n"] == 2


# ── luôn FAIL → bounded, hết lượt thì escalate (không loop vô hạn) ──
def test_reflection_bounded_then_escalates(monkeypatch):
    import tools.run_validation as rv
    from graph.state import new_state
    fake = _fake_validation(["FAIL"])   # luôn FAIL
    monkeypatch.setattr(rv, "run_validation", fake)

    final = _seed_and_app().invoke(new_state("Revenue 2026-06-07 lệch 2.1%"))
    nodes = [e["node"] for e in final["timeline"]]
    assert nodes.count("refine_patch") == MAX_VALIDATION_ATTEMPTS   # đúng số lượt tối đa
    assert nodes.count("validation_engine") == MAX_VALIDATION_ATTEMPTS + 1
    assert "escalate" in nodes                      # hết lượt → escalate, KHÔNG ra RCA với số sai
