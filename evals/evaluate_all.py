"""Aggregate eval — chạy mỗi golden case 1 lần, đo accuracy BẰNG SỐ (%) trên nhiều chiều.

Chạy: python -m evals.evaluate_all
Chiều đo: detection (anomaly) · routing · tool-selection · final-status · grounding (no fabrication).
"""

from __future__ import annotations

import sys
from typing import Any

from evals._harness import actual_final_status, ensure_seeded, load_golden, run_case


def evaluate_all() -> dict[str, Any]:
    ensure_seeded()
    cases = load_golden()
    finals = [(c, run_case(c)) for c in cases]
    n = len(cases)

    def acc(pred) -> float:
        return round(sum(1 for c, f in finals if pred(c, f)) / n, 3) if n else 0.0

    def grounded(c, f) -> bool:
        if c["expected_route"] == "confident":
            cvr = f.get("claim_verification_result", {}) or {}
            return (not cvr.get("has_critical_unsupported", True)) and cvr.get("verified", 0) >= 3
        return f.get("patch") is None  # escalate: không bịa code fix

    metrics = {
        "cases": n,
        "detection_accuracy": acc(lambda c, f: f.get("anomaly_type") == c["expected_anomaly"]),
        "routing_accuracy": acc(lambda c, f: f.get("confidence_route") == c["expected_route"]),
        "tool_selection_accuracy": acc(
            lambda c, f: set(c["expected_tools"]) <= set(f.get("tool_plan", []))),
        "final_status_accuracy": acc(lambda c, f: actual_final_status(f) == c["expected_final_status"]),
        "grounding_accuracy": acc(grounded),
    }
    print(f"\n=== Eval accuracy ({n} cases) ===")
    for k, v in metrics.items():
        if k == "cases":
            continue
        print(f"  {k:24s}: {v * 100:.1f}%")
    return metrics


if __name__ == "__main__":
    m = evaluate_all()
    ok = all(v == 1.0 for k, v in m.items() if k != "cases")
    sys.exit(0 if ok else 1)
