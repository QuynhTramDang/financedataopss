"""Đánh giá patch: chứa value kỳ vọng khi cần fix; KHÔNG có patch khi escalate.
Chạy: python -m evals.evaluate_patch"""

from __future__ import annotations

import sys

from evals._harness import ensure_seeded, load_golden, print_report, run_case


def evaluate() -> bool:
    ensure_seeded()
    rows = []
    for case in load_golden():
        final = run_case(case)
        expected = case.get("expected_patch_contains")
        patch = final.get("patch")
        if expected:
            ok = bool(patch) and expected in patch.get("new_code", "")
            detail = f"patch chứa '{expected}'={ok}"
        else:
            ok = patch is None
            detail = f"no patch={ok}"
        rows.append({"case_id": case["case_id"], "pass": ok, "detail": detail})
    return print_report("Patch correctness", rows)


if __name__ == "__main__":
    sys.exit(0 if evaluate() else 1)
