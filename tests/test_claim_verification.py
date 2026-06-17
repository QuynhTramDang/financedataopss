"""Step 8 — Claim Verifier + rule engine + contradiction checker."""

from governance.claim_policy import verify_claims
from tools.claim_verifier import build_claims
from tools.contradiction_checker import check_contradictions
from tools.evidence_mapper import map_evidence


def _summary():
    return {
        "enum_drift": {"new_values": ["PARTIAL_REFUND"]},
        "code": {"missing_values": ["PARTIAL_REFUND"],
                 "repo_path": "pipelines/models/finance/revenue_daily.sql"},
        "affected_amount": 210_000_000,
    }


def test_claims_verified_and_business_requires_approval():
    claims = build_claims({"tool_results_summary": _summary()})
    res = verify_claims(claims, _summary())
    by_id = {c["claim_id"]: c for c in res["claims"]}

    assert by_id["C1"]["status"] == "verified"          # data_fact
    assert by_id["C2"]["status"] == "verified"          # code_fact
    assert by_id["C3"]["status"] == "verified"          # quantitative
    assert by_id["C4"]["status"] == "requires_approval"  # business_decision luôn cần approval
    assert res["has_critical_unsupported"] is False


def test_missing_evidence_makes_claim_unsupported():
    # tool_results thiếu enum_drift/code → claim data/code thành unsupported
    claims = build_claims({"tool_results_summary": _summary()})
    res = verify_claims(claims, {"affected_amount": 0})
    by_id = {c["claim_id"]: c for c in res["claims"]}
    assert by_id["C1"]["status"] == "unsupported"
    assert by_id["C3"]["status"] == "unsupported"       # affected_amount = 0 → không > 0
    assert res["has_critical_unsupported"] is True


def test_llm_cannot_force_verified_only_ruleengine_decides():
    # claim do "LLM" tạo nhưng evidence không có → rule engine vẫn đánh unsupported
    fake_claim = [{
        "claim_id": "X", "claim": "bịa", "claim_type": "data_fact",
        "required_evidence": ["sql_profile"],
        "check": {"field": "enum_drift.new_values", "op": "contains", "value": "FAKE"},
        "status": "verified",  # LLM tự gán — phải bị ghi đè
    }]
    res = verify_claims(fake_claim, _summary())
    assert res["claims"][0]["status"] == "unsupported"


def test_evidence_mapper_table():
    claims = build_claims({"tool_results_summary": _summary()})
    verify_claims(claims, _summary())
    table = map_evidence(claims)
    assert len(table) == 4
    assert all("status" in row and "source" in row for row in table)


def test_contradiction_checker_blocks_on_mismatch():
    # §14.6: report nói 0.03% nhưng tool nói 0.8%
    res = check_contradictions({"after_fix_diff": 0.0003}, {"after_fix_diff": 0.008})
    assert res["contradiction_found"] is True
    assert res["details"][0]["field"] == "after_fix_diff"


def test_contradiction_checker_passes_when_consistent():
    res = check_contradictions({"after_fix_diff": 0.0003}, {"after_fix_diff": 0.0003})
    assert res["contradiction_found"] is False


def test_node_sets_claims_in_graph():
    from data.seed_data.seed import main as seed_main
    from graph.state import new_state
    from graph.workflow import build_workflow

    seed_main()
    final = build_workflow().invoke(new_state("Revenue 2026-06-07 lệch 2.1%"))
    cvr = final.get("claim_verification_result", {})
    assert cvr.get("verified", 0) >= 3
    assert cvr.get("requires_approval", 0) >= 1
    assert cvr.get("has_critical_unsupported") is False
