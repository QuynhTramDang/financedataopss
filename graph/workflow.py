"""Build & compile LangGraph workflow (control plane).

Dùng:
    from graph.workflow import build_workflow
    from graph.state import new_state
    app = build_workflow()
    final = app.invoke(new_state("Revenue 2026-06-07 lệch 2.1% ..."))
    for step in final["timeline"]:
        print(step["node"], step["status"])
"""

from __future__ import annotations

import time

from langgraph.graph import StateGraph

from observability.trace_logger import log_event, pop_node_buffer, start_node_buffer

from . import nodes
from .edges import build_edges
from .state import InvestigationState


def _observe(name, fn):
    """Wrap node: đo latency + gom model/token đã dùng trong node, log_event + gắn vào timeline."""
    def wrapped(state):
        start_node_buffer()
        t0 = time.perf_counter()
        out = fn(state)
        latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        calls = pop_node_buffer()
        model = calls[-1]["model"] if calls else None
        in_tok = sum(c["input_tokens"] for c in calls)
        out_tok = sum(c["output_tokens"] for c in calls)
        log_event({"node": name, "latency_ms": latency_ms, "model": model,
                   "input_tokens": in_tok, "output_tokens": out_tok})
        if isinstance(out, dict) and out.get("timeline"):
            out["timeline"][-1]["latency_ms"] = latency_ms
            if model:
                out["timeline"][-1]["model"] = model
        return out
    return wrapped

_NODES = {
    "intent_risk_classifier": nodes.intent_risk_classifier,
    "memory_rag_retrieval": nodes.memory_rag_retrieval,
    "known_unknown_router": nodes.known_unknown_router,
    "tool_governance": nodes.tool_governance,
    "diagnostic_tools": nodes.diagnostic_tools,
    "root_cause_reasoner": nodes.root_cause_reasoner,
    "claim_verifier": nodes.claim_verifier,
    "safe_patch_generator": nodes.safe_patch_generator,
    "refine_patch": nodes.refine_patch,
    "patch_reviewer": nodes.patch_reviewer,
    "validation_engine": nodes.validation_engine,
    "trust_scorer": nodes.trust_scorer,
    "rca_report_generator": nodes.rca_report_generator,
    "test_docs_generator": nodes.test_docs_generator,
    "human_approval": nodes.human_approval,
    "apply_remediation": nodes.apply_remediation,
    "memory_writeback": nodes.memory_writeback,
    "escalate": nodes.escalate,
}


def build_workflow(checkpointer=None, interrupt_before_approval: bool = False):
    """Tạo và compile graph. Trả về compiled app có .invoke(state).

    - checkpointer: truyền MemorySaver/SqliteSaver để bật persist/resume/time-travel (HITL thật).
      Khi có checkpointer, invoke cần config={"configurable":{"thread_id": ...}}.
    - interrupt_before_approval: PAUSE trước node human_approval để con người xét rồi resume
      (cập nhật approval_status qua update_state + invoke(None, config)). Cần checkpointer.
    Mặc định (None/False) → giữ hành vi cũ (chạy thẳng, không cần thread_id) cho test/CLI.
    """
    graph = StateGraph(InvestigationState)
    for name, fn in _NODES.items():
        graph.add_node(name, _observe(name, fn))
    build_edges(graph)

    compile_kwargs: dict = {}
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer
        if interrupt_before_approval:
            compile_kwargs["interrupt_before"] = ["human_approval"]
    return graph.compile(**compile_kwargs)
