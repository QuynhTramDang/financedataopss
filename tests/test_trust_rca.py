"""Step 11 — Trust Scorer + RCA Report (+ Slice 1 end-to-end)."""

from data.seed_data.seed import AFFECTED_AMOUNT
from tools.generate_rca_report import generate_rca_report
from tools.trust_scorer import score


def _good_state():
    return {
        "investigation_id": "INV-1",
        "date": "2026-06-07",
        "metric": "net_revenue",
        "root_cause": "PARTIAL_REFUND chưa map trong revenue_daily",
        "context_pack": {"metric_definition": "net_revenue = paid_amount - refunded_amount"},
        "claims": [
            {"claim_id": "C1", "claim": "a", "claim_type": "data_fact",
             "required_evidence": ["sql_profile"], "status": "verified"},
            {"claim_id": "C2", "claim": "b", "claim_type": "code_fact",
             "required_evidence": ["code_search"], "status": "verified"},
            {"claim_id": "C4", "claim": "c", "claim_type": "business_decision",
             "required_evidence": ["human_approval"], "status": "requires_approval"},
        ],
        "claim_verification_result": {"has_critical_unsupported": False},
        "validation_result": {"validation_status": "PASS", "passed": 5, "total": 5,
                              "reconciliation": {"before_fix_diff": 0.021, "after_fix_diff": 0.0}},
        "impact_analysis": {"before_fix_diff": 0.021, "after_fix_diff": 0.0,
                            "affected_amount": AFFECTED_AMOUNT,
                            "affected_report": "finance_revenue_report"},
        "patch": {"target_file": "revenue_daily.sql",
                  "old_code": "= 'REFUNDED'", "new_code": "in ('REFUNDED','PARTIAL_REFUND')",
                  "reason": "include PARTIAL_REFUND", "rollback_plan": "revert"},
        "tool_results_summary": {"enum_drift": {"new_values": ["PARTIAL_REFUND"]},
                                 "code": {"missing_values": ["PARTIAL_REFUND"]}},
    }


def test_trust_matrix_ready_on_good_case():
    res = score(_good_state())
    tm = res["trust_matrix"]
    assert res["ready_for_report"] is True
    assert res["blockers"] == []
    assert tm["data_anomaly"] == "High"
    assert tm["code_root_cause"] == "High"
    assert tm["patch_correctness"] == "High"
    assert tm["business_interpretation"] == "Medium"


def test_trust_blocks_on_contradiction():
    st = _good_state()
    st["impact_analysis"]["after_fix_diff"] = 0.008    # khác validation (0.0) → contradiction
    res = score(st)
    assert res["ready_for_report"] is False
    assert any("contradiction" in b for b in res["blockers"])


def test_trust_blocks_on_failed_validation():
    st = _good_state()
    st["validation_result"]["validation_status"] = "FAIL"
    res = score(st)
    assert res["ready_for_report"] is False


def test_rca_report_contains_sections_and_numbers():
    st = _good_state()
    st["trust_matrix"] = score(st)["trust_matrix"]
    rca = generate_rca_report(st)
    assert "# Root Cause Analysis Report" in rca
    assert "Claim Verification" in rca
    assert "Trust Matrix" in rca
    assert "2.10%" in rca                  # before fix mismatch tính từ số thật
    assert "210,000,000" in rca            # affected amount


def test_slice1_end_to_end():
    """Slice 1 happy path: chạy đủ engine thật + approve → writeback."""
    from data.seed_data.seed import main as seed_main
    from graph.state import new_state
    from graph.workflow import build_workflow

    seed_main()
    state = new_state("Revenue report 2026-06-07 lệch 2.1% so với payment dashboard")
    state["approval_status"] = "approved"
    final = build_workflow().invoke(state)

    assert final["risk_level"] == "high"
    assert "PARTIAL_REFUND" in final["tool_results_summary"]["enum_drift"]["new_values"]
    assert final["root_cause"]
    assert final["validation_result"]["validation_status"] == "PASS"
    assert "PARTIAL_REFUND" in final["patch"]["new_code"]
    assert final["trust_matrix"]["patch_correctness"] == "High"
    assert final["rca_report"] and "Root Cause Analysis" in final["rca_report"]
    assert final["memory_writeback_status"] == "written"
