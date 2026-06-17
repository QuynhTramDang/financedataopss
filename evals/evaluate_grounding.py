"""Đánh giá grounding: confident → claim verified, không critical unsupported;
escalate → KHÔNG bịa code patch. Chạy: python -m evals.evaluate_grounding"""

from __future__ import annotations

import sys

from evals._harness import ensure_seeded, load_golden, print_report, run_case


def evaluate() -> bool:
    ensure_seeded()
    rows = []
    for case in load_golden():
        final = run_case(case)
        if case["expected_route"] == "confident":
            cvr = final.get("claim_verification_result", {}) or {}
            ok = (not cvr.get("has_critical_unsupported", True)) and cvr.get("verified", 0) >= 3
            detail = f"verified={cvr.get('verified')} critical_unsupported={cvr.get('has_critical_unsupported')}"
        else:
            ok = final.get("patch") is None      # escalate: không sinh code fix
            detail = f"patch={'None' if final.get('patch') is None else 'present'}"
        rows.append({"case_id": case["case_id"], "pass": ok, "detail": detail})
    return print_report("Grounding (no fabricated claim/patch)", rows)


if __name__ == "__main__":
    sys.exit(0 if evaluate() else 1)
