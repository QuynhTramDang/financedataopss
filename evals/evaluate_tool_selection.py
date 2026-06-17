"""Đánh giá tool selection: expected_tools ⊆ tool_plan. Chạy: python -m evals.evaluate_tool_selection"""

from __future__ import annotations

import sys

from evals._harness import ensure_seeded, load_golden, print_report, run_case


def evaluate() -> bool:
    ensure_seeded()
    rows = []
    for case in load_golden():
        final = run_case(case)
        expected = set(case.get("expected_tools", []))
        actual = set(final.get("tool_plan", []))
        ok = expected <= actual
        rows.append({"case_id": case["case_id"], "pass": ok,
                     "detail": f"missing={sorted(expected - actual) or 'none'}"})
    return print_report("Tool selection", rows)


if __name__ == "__main__":
    sys.exit(0 if evaluate() else 1)
