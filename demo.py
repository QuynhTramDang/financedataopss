"""Demo end-to-end Impact-Aware Finance DataOps Twin (CLI).

Chạy: python demo.py
Đi qua 5 phần: Investigation (Slice 1) · Proactive Monitoring · Incident Agent ·
Lineage/Impact Q&A · Golden Set evaluation.
"""

from __future__ import annotations

import sys

# in tiếng Việt sạch trên Windows console
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

from agents.incident_agent import handle_incident
from agents.lineage_qa import answer
from data.seed_data.seed import main as seed_main
from graph.state import new_state
from graph.workflow import build_workflow
from monitoring import format_alert, run_sweep_once
from observability import get_trace, totals
from tools.memory_writeback import write_incident


def h(title: str) -> None:
    print("\n" + "=" * 72)
    print(f"  {title}")
    print("=" * 72)


def main() -> None:
    print("Seeding demo data (SQLite)...")
    seed_main()

    # ── 1. INVESTIGATION (case enum drift PARTIAL_REFUND) ──
    h("1) INVESTIGATION — Revenue 2026-06-07 lệch 2.1%")
    app = build_workflow()
    final = app.invoke(new_state(
        "Revenue report ngày 2026-06-07 đang lệch 2.1% so với payment dashboard."))

    print("\n-- Timeline --")
    for i, e in enumerate(final["timeline"], 1):
        lat = f" {e['latency_ms']}ms" if e.get("latency_ms") is not None else ""
        print(f"  {i:2d}. {e['node']}{lat} — {e['note']}")

    print(f"\nIntent={final['intent']} | metric={final['metric']} | risk={final['risk_level']} "
          f"| anomaly={final['anomaly_type']} | route={final['confidence_route']}")
    print(f"Root cause: {final['root_cause']}")

    print("\n-- Claims --")
    for c in final["claims"]:
        print(f"  [{c['status']:>16}] {c['claim']}")

    imp = final["impact_analysis"]
    print(f"\nImpact: before={imp['before_fix_diff']*100:.2f}% -> after={imp['after_fix_diff']*100:.2f}% "
          f"| affected={imp['affected_amount']:,} VND")

    val = final["validation_result"]
    print(f"Validation: {val['validation_status']} ({val['passed']}/{val['total']})")

    print("\n-- Patch --")
    print(f"  {final['patch']['old_code']}")
    print(f"  -> {final['patch']['new_code']}")

    print("\n-- Trust Matrix --")
    for k, v in final["trust_matrix"].items():
        print(f"  {k}: {v}")

    dbt = final["dbt_test"]["verification"]
    print(f"\ndbt test catches_bug={dbt['catches_bug']} "
          f"({dbt['before_fix_status']} -> {dbt['after_fix_status']})")

    tot = totals(get_trace())
    print(f"\nObservability: input_tokens={tot['input_tokens']} (0 = chạy offline/fallback) | "
          f"0 raw rows -> LLM")

    print(f"\nApproval status (mặc định): {final['approval_status']} -> "
          f"memory_writeback={final['memory_writeback_status']} (CHƯA approve => không ghi)")
    wb = write_incident(final, "approved")   # mô phỏng human approve
    print(f"Sau khi Approve: {wb['status']} -> incident {wb.get('incident', {}).get('incident_id')}")

    # ── 2. PROACTIVE MONITORING ──
    h("2) PROACTIVE MONITORING — DQ sweep (bắt lỗi TRƯỚC khi Finance báo)")
    for a in run_sweep_once():
        print("\n" + format_alert(a))
    print("\n(2026-06-10 sạch -> không alert)")

    # ── 3. INCIDENT AGENT ──
    h("3) INCIDENT AGENT — job-fail triage")
    for job in ("load_stripe_payments", "daily_orders_pipeline", "revenue_daily",
                "export_finance_report"):
        res = handle_incident(job)
        auto = res["auto_action_taken"]
        print(f"\n[{job}] {res['failure_type']} -> action={res['action']} (tier {res['tier']}) "
              f"auto={auto or '— cần approval/escalate'}")

    # ── 4. LINEAGE / IMPACT Q&A ──
    h("4) LINEAGE + IMPACT Q&A (L1 read-only)")
    for q in ("net_revenue tính từ đâu?", "Nếu sửa stg_payment thì ảnh hưởng gì?"):
        print(f"\nQ: {q}\nA: {answer(q)['answer']}")

    # ── 5. GOLDEN SET ──
    h("5) GOLDEN SET EVALUATION")
    from evals.evaluate_root_cause import evaluate
    evaluate()

    print("\n" + "=" * 72)
    print("  DEMO DONE.")
    print("=" * 72)


if __name__ == "__main__":
    main()
