"""#1 PII masking (wired thật) + #2 HITL checkpointer/interrupt (LangGraph native)."""

import pytest

from governance.pii_policy import has_pii, mask_for_llm
from orchestration.executor import execute_plan
from orchestration.registry import ToolRecord, ToolRegistry


# ── #1: PII masking ──────────────────────────────────────────
def test_mask_for_llm_recursive_keeps_numbers():
    obj = {
        "email": "alice@example.com",
        "amount": 100,
        "nested": {"phone": "0900123456", "count": 7},
        "rows": [{"card_number": "4111111111111111", "ok": 1}],
    }
    masked = mask_for_llm(obj)
    assert "@" not in masked["email"]
    assert masked["amount"] == 100                       # số liệu giữ nguyên
    assert masked["nested"]["phone"] != "0900123456"
    assert masked["nested"]["count"] == 7
    assert masked["rows"][0]["card_number"] != "4111111111111111"
    assert masked["rows"][0]["ok"] == 1
    assert has_pii({"email": "x"}) and not has_pii({"amount": 1})


def test_executor_masks_pii_before_evidence():
    # tool trả field PII → executor mask trước khi vào state/LLM/RCA (chokepoint)
    reg = ToolRegistry(records={
        "metadata_scan": ToolRecord(
            name="metadata_scan", capability="x", description="",
            input_schema={"type": "object"}, output_schema={}, evidence_type="x",
            fn=lambda **k: {"email": "bob@example.com", "count": 5}),
    })
    plan = [{"id": "s1", "tool": "metadata_scan", "capability": "x", "reason": "t",
             "inputs": {}, "depends_on": [], "expected_evidence": "x"}]
    ev = execute_plan(plan, registry=reg)
    assert ev[0]["status"] == "collected"
    assert "@" not in ev[0]["data"]["email"]             # PII đã mask
    assert ev[0]["data"]["count"] == 5


# ── #2: HITL checkpointer + interrupt → pause/resume ─────────
def test_hitl_interrupt_pause_then_resume():
    from langgraph.checkpoint.memory import MemorySaver

    from data.seed_data.seed import main as seed_main
    from graph.state import new_state
    from graph.workflow import build_workflow

    seed_main()
    app = build_workflow(checkpointer=MemorySaver(), interrupt_before_approval=True)
    cfg = {"configurable": {"thread_id": "hitl-1"}}

    paused = app.invoke(new_state("Revenue 2026-06-07 lệch 2.1%"), cfg)
    nodes = [e["node"] for e in paused["timeline"]]
    assert "rca_report_generator" in nodes               # đã dựng xong RCA để người xét
    assert "human_approval" not in nodes                 # PAUSED trước approval
    assert "memory_writeback" not in nodes

    # con người duyệt → resume từ checkpoint
    app.update_state(cfg, {"approval_status": "approved"})
    final = app.invoke(None, cfg)
    nodes2 = [e["node"] for e in final["timeline"]]
    assert "human_approval" in nodes2
    assert final["memory_writeback_status"] == "written"


def test_default_workflow_no_checkpointer_still_runs():
    # giữ hành vi cũ: không checkpointer → invoke không cần thread_id
    from data.seed_data.seed import main as seed_main
    from graph.state import new_state
    from graph.workflow import build_workflow

    seed_main()
    state = new_state("Revenue 2026-06-07 lệch 2.1%")
    state["approval_status"] = "approved"
    final = build_workflow().invoke(state)
    assert final["memory_writeback_status"] == "written"
