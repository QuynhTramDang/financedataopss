"""Đánh giá root cause + routing + final status trên golden set.

Chạy: python -m evals.evaluate_root_cause
"""

from __future__ import annotations

import sys

from evals._harness import actual_final_status, ensure_seeded, load_golden, print_report, run_case


def evaluate() -> bool:
    ensure_seeded()
    rows = []
    for case in load_golden():
        final = run_case(case)
        anom = final.get("anomaly_type")
        route = final.get("confidence_route")
        status = actual_final_status(final)
        ok = (anom == case["expected_anomaly"]
              and route == case["expected_route"]
              and status == case["expected_final_status"])
        rows.append({"case_id": case["case_id"], "pass": ok,
                     "detail": f"anomaly={anom} route={route} status={status}"})
    return print_report("Root cause / routing / final status", rows)


if __name__ == "__main__":
    sys.exit(0 if evaluate() else 1)
