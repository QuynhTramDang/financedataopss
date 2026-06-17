"""Step 15 — Lineage + Impact Q&A (L1 read-only)."""

from agents.lineage_qa import answer, detect_asset
from tools.impact_analysis import downstream_closure, impact_analysis


def test_impact_of_payment_txn_full_blast_radius():
    res = impact_analysis("payment_txn")
    assert res["found"]
    assert "stg_payment" in res["affected_pipelines"]
    assert "revenue_daily" in res["affected_pipelines"]
    assert "net_revenue" in res["affected_metrics"]
    assert "finance_revenue_report" in res["affected_reports"]


def test_impact_of_stg_payment_downstream():
    # topology 3 tầng: stg_payment → ods_payment_enriched → dtm_revenue_daily → finance_revenue_report
    res = impact_analysis("stg_payment")
    assert "ods_payment_enriched" in res["affected_pipelines"]
    assert "dtm_revenue_daily" in res["affected_pipelines"]
    assert "net_revenue" in res["affected_metrics"]
    assert "finance_revenue_report" in res["affected_reports"]


def test_unknown_asset_not_found():
    res = impact_analysis("khong_ton_tai")
    assert res["found"] is False
    assert res["affected_pipelines"] == []


def test_detect_asset():
    assert detect_asset("sửa stg_payment ảnh hưởng gì") == "stg_payment"
    assert detect_asset("net_revenue tính từ đâu") == "net_revenue"
    assert detect_asset("net revenue là gì") == "net_revenue"   # match cả dạng có space


def test_qa_definition_of_metric():
    out = answer("net_revenue tính từ đâu?")
    assert out["mode"] == "definition"
    assert out["tier"] == "L1_read_only"
    assert "paid_amount - refunded_amount" in out["answer"]


def test_qa_impact_question():
    out = answer("Nếu sửa stg_payment thì ảnh hưởng gì?")
    assert out["mode"] == "impact"
    assert out["blast_radius"]["affected_metrics"] == ["net_revenue"]
    assert "revenue_daily" in out["answer"]


def test_qa_is_read_only_no_patch():
    out = answer("net_revenue là gì")
    # L1: không có patch, không ghi gì
    assert out["tier"] == "L1_read_only"
    assert "patch" not in out
