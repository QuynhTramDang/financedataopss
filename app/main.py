"""Streamlit UI — Impact-Aware Finance DataOps Twin.

Step 11: full Slice 1 view — chạy investigation, hiển thị timeline / context / diagnostics /
patch / validation / trust matrix / RCA, và approval flow (approve → memory write-back).
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st  # noqa: E402

from app.components.patch_viewer import render_patch, render_validation  # noqa: E402
from app.components.rca_viewer import render_rca  # noqa: E402
from app.components.timeline import render_timeline  # noqa: E402
from app.components.trust_matrix import render_claims, render_trust  # noqa: E402
from graph.state import new_state  # noqa: E402
from graph.workflow import build_workflow  # noqa: E402
from observability import assert_no_raw_rows, get_trace, totals, within_budget  # noqa: E402
from tools.memory_writeback import write_incident  # noqa: E402

st.set_page_config(page_title="Finance DataOps Twin", layout="wide")
st.title("Impact-Aware Finance DataOps Twin")
st.caption("LangGraph Control Plane — State → Model → Tools → Routing → "
           "Verification → Validation → Human Approval")

with st.sidebar:
    st.header("Model Router")
    try:
        from model_router import get_router

        routes = get_router()._routes  # noqa: SLF001
        st.success(f"{len(routes)} route từ models.yaml")
        for name, cfg in routes.items():
            icon = "🟢" if cfg.get("phase1") == "real" else "⚪"
            st.write(f"{icon} **{name}** ({cfg.get('phase1')})")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Router: {exc}")

    if st.session_state.get("final"):
        st.divider()
        st.header("Observability")
        tr = get_trace()
        tot = totals(tr)
        st.metric("Input tokens", tot["input_tokens"])
        st.caption(f"output={tot['output_tokens']} · llm_nodes={tot['llm_nodes']} · "
                   f"budget={'OK' if within_budget(tr) else 'OVER'}")
        raw = assert_no_raw_rows(st.session_state["final"])
        st.caption(f"raw rows → LLM: {'0 ✅' if not raw else raw}")

request = st.text_area(
    "Investigation request",
    value="Revenue report ngày 2026-06-07 đang lệch 2.1% so với payment dashboard. "
          "Kiểm tra nguyên nhân và đề xuất fix.",
    height=90,
)

if st.button("Run investigation", type="primary"):
    st.session_state["final"] = build_workflow().invoke(new_state(request))
    st.session_state["writeback"] = None

final = st.session_state.get("final")
if final:
    left, right = st.columns([3, 2])
    with left:
        render_timeline(final.get("timeline", []))
        st.subheader("Root cause")
        st.write(final.get("root_cause") or "Chưa kết luận (escalate)")
        render_patch(final.get("patch"), final.get("patch_review"))
        render_validation(final.get("validation_result"))
    with right:
        st.subheader("State")
        st.json({k: final.get(k) for k in
                 ("investigation_id", "intent", "metric", "date", "risk_level",
                  "issue_mode", "confidence_route", "approval_status")})
        render_trust(final.get("trust_matrix"))

    render_claims(final.get("claims"))

    dbt = final.get("dbt_test")
    if dbt:
        v = dbt["verification"]
        st.subheader("Generated dbt test (chặn tái diễn)")
        st.caption(f"catches_bug={v['catches_bug']} · "
                   f"trước fix: {v['before_fix_status']} → sau fix: {v['after_fix_status']}")
        st.code(dbt["yaml"], language="yaml")
    if final.get("docs_update"):
        with st.expander("Đề xuất cập nhật docs"):
            st.markdown(final["docs_update"]["markdown"])

    render_rca(final.get("rca_report"))

    # ── Approval flow ──
    st.divider()
    st.subheader("Human Approval")
    c1, c2, c3 = st.columns(3)
    if c1.button("✅ Approve"):
        res = write_incident(final, "approved")
        st.session_state["writeback"] = res
    if c2.button("❌ Reject"):
        st.session_state["writeback"] = {"status": "rejected"}
    if c3.button("✏️ Request revision"):
        st.session_state["writeback"] = {"status": "needs_revision"}

    wb = st.session_state.get("writeback")
    if wb:
        if wb["status"] == "written":
            st.success(f"Approved → incident ghi vào memory: {wb['incident']['incident_id']}")
        else:
            st.warning(f"Trạng thái: {wb['status']} — không ghi memory (không apply patch).")

# ── Proactive Monitoring (scheduler sweep) ───────────────────
st.divider()
st.subheader("Proactive Monitoring — DQ sweep (bắt lỗi trước khi Finance báo)")
if st.button("Run sweep"):
    from monitoring import format_alert, run_sweep_once
    alerts = run_sweep_once()
    if not alerts:
        st.success("Sweep sạch — không phát hiện anomaly.")
    for a in alerts:
        icon = "🔴" if a["severity"] == "high" else "🟡"
        st.markdown(f"{icon} **{a['date']}** — `{a['anomaly_type']}` · {a['recommended_action']} "
                    f"(tier {a['tier']})")
        st.caption(format_alert(a))

# ── Incident Agent (pipeline-fail triage) ───────────────────
st.divider()
st.subheader("Incident Agent — job-fail triage")
from tools.log_search import available_jobs  # noqa: E402

job = st.selectbox("Chọn job fail (mock log)", available_jobs())
if st.button("Triage incident"):
    from agents.incident_agent import handle_incident
    res = handle_incident(job)
    auto = res.get("auto_action_taken")
    st.markdown(f"**{res['failure_type']}** · action=`{res['action']}` · tier={res['tier']} · "
                f"auto={'✅ ' + auto if auto else '— (cần approval/escalate)'}")
    st.code(res["summary"])
    st.caption("Audit: " + " | ".join(res.get("audit", [])))

# ── Ask: lineage / impact Q&A (L1 read-only) ─────────────────
st.divider()
st.subheader("Hỏi nhanh: lineage / impact (L1 read-only)")
q = st.text_input("Ví dụ: 'net_revenue tính từ đâu?' hoặc 'sửa stg_payment ảnh hưởng gì?'")
if st.button("Ask"):
    from agents.lineage_qa import answer
    res = answer(q)
    st.caption(f"mode={res['mode']} · asset={res.get('asset')} · tier={res['tier']}")
    st.info(res["answer"])
    if res.get("blast_radius"):
        st.json(res["blast_radius"])
