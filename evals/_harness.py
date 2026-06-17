"""Harness dùng chung cho các evaluator: load golden set + chạy 1 case qua graph."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_GOLDEN = Path(__file__).with_name("golden_set.json")


def load_golden() -> list[dict[str, Any]]:
    return json.loads(_GOLDEN.read_text(encoding="utf-8"))


def ensure_seeded() -> None:
    from data.seed_data.seed import main as seed_main
    seed_main()


def run_case(case: dict) -> dict[str, Any]:
    """Chạy 1 golden case qua workflow, trả final state."""
    from graph.state import new_state
    from graph.workflow import build_workflow
    return build_workflow().invoke(new_state(case["input"]))


def actual_final_status(final: dict) -> str:
    """Suy ra final status: 'escalated' nếu route escalate; ngược lại 'ready_for_approval'."""
    if final.get("confidence_route") == "escalate":
        return "escalated"
    validation = final.get("validation_result", {}) or {}
    return "ready_for_approval" if validation.get("validation_status") == "PASS" else "needs_review"


def print_report(title: str, rows: list[dict]) -> bool:
    """In bảng kết quả; trả True nếu tất cả PASS."""
    print(f"\n=== {title} ===")
    all_pass = True
    for r in rows:
        ok = r["pass"]
        all_pass = all_pass and ok
        icon = "PASS" if ok else "FAIL"
        print(f"  [{icon}] {r['case_id']}: {r.get('detail', '')}")
    print(f"  -> {'ALL PASS' if all_pass else 'SOME FAILED'} ({sum(r['pass'] for r in rows)}/{len(rows)})")
    return all_pass
