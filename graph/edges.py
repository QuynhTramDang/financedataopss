"""Wiring các cạnh của workflow (tách khỏi workflow.py cho dễ đọc).

Thứ tự theo §5.1 LangGraph Workflow:
  intent → memory/RAG → known/unknown router → tool governance → diagnostics →
  root cause → [confidence?] → claim verify → safe patch → patch review → validation →
  trust scorer → RCA → human approval → [approved?] → memory write-back
Nhánh escalate (low-confidence): bỏ qua patch, đi thẳng RCA (evidence pack) rồi kết thúc.
"""

from __future__ import annotations

from langgraph.graph import END, START

from . import conditions, nodes


def build_edges(graph) -> None:
    graph.add_edge(START, "intent_risk_classifier")
    graph.add_edge("intent_risk_classifier", "memory_rag_retrieval")
    graph.add_edge("memory_rag_retrieval", "known_unknown_router")

    # known và unknown đều tới tool_governance (khác nhau ở runbook — xử lý ở step sau)
    graph.add_conditional_edges(
        "known_unknown_router", conditions.route_known_unknown,
        {"known": "tool_governance", "unknown": "tool_governance"},
    )

    graph.add_edge("tool_governance", "diagnostic_tools")
    graph.add_edge("diagnostic_tools", "root_cause_reasoner")

    # confidence gate
    graph.add_conditional_edges(
        "root_cause_reasoner", conditions.route_confidence,
        {"confident": "claim_verifier", "escalate": "escalate"},
    )

    graph.add_edge("claim_verifier", "safe_patch_generator")
    graph.add_edge("safe_patch_generator", "patch_reviewer")
    graph.add_edge("patch_reviewer", "validation_engine")

    # reflection gate: PASS → trust_scorer; FAIL & còn lượt → refine_patch (rồi re-validate);
    # hết lượt → escalate. KHÔNG đi thẳng RCA với số sai.
    graph.add_conditional_edges(
        "validation_engine", conditions.route_validation,
        {"ok": "trust_scorer", "retry": "refine_patch", "giveup": "escalate"},
    )
    graph.add_edge("refine_patch", "validation_engine")   # loop: thử lại validation sau khi sửa

    graph.add_edge("trust_scorer", "rca_report_generator")
    graph.add_edge("rca_report_generator", "test_docs_generator")  # Step 11A
    graph.add_edge("test_docs_generator", "human_approval")

    # approval gate — approved → thực thi remediation qua MCP (apply_remediation) rồi ghi memory.
    # còn lại halt (không auto-deploy). Write action CHỈ chạy ở nhánh approved này.
    graph.add_conditional_edges(
        "human_approval", conditions.route_approval,
        {"approved": "apply_remediation", "halt": END},
    )
    graph.add_edge("apply_remediation", "memory_writeback")
    graph.add_edge("memory_writeback", END)

    # nhánh escalate: tạo evidence pack (RCA), rồi vẫn tới human_approval — để nếu người
    # cung cấp correction (chỉ ra root cause agent miss) thì ghi vào memory (learning loop).
    graph.add_edge("escalate", "human_approval")
