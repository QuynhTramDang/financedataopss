"""scenarios — catalog các tình huống lỗi được nhúng vào data seed.

Mỗi entry mô tả 1 ngày + loại anomaly + kỳ vọng (expected_anomaly/route) để:
  - seed.py biết dựng data gì cho ngày đó,
  - B2 nối vào golden_set.json + evals/evaluate_tool_selection.py (đo planner chọn tool đúng chưa).

`expected_route` = nhánh kỳ vọng của root_cause_reasoner:
  - "confident"  → có thể fix bằng code patch (vd enum drift).
  - "escalate"   → data quality / không đủ evidence → không sinh patch.
"""

from __future__ import annotations

# Tuần demo có lỗi (07–14). Lịch sử "bình thường" 16/05–06/06 do seed.py sinh tự động.
SCENARIOS: list[dict] = [
    {"date": "2026-06-07", "type": "enum_drift", "expected_anomaly": "enum_drift",
     "expected_route": "confident", "fixable": True,
     "note": "refund_status PARTIAL_REFUND mới, ods chưa map → net_revenue overstated 2.1%"},
    {"date": "2026-06-08", "type": "null_spike", "expected_anomaly": "null_spike",
     "expected_route": "escalate", "fixable": False,
     "note": "amount null 40% → nghi ingestion lỗi"},
    {"date": "2026-06-09", "type": "missing_partition", "expected_anomaly": "missing_partition",
     "expected_route": "escalate", "fixable": False,
     "note": "partition 0 row → upstream/ingestion chưa chạy"},
    {"date": "2026-06-10", "type": "clean", "expected_anomaly": None,
     "expected_route": "escalate", "fixable": False,
     "note": "data sạch — negative case, KHÔNG kết luận root cause"},
    {"date": "2026-06-11", "type": "duplicate", "expected_anomaly": "duplicate",
     "expected_route": "escalate", "fixable": False,
     "note": "đơn bị tính 2 lần (cùng order_id) → revenue double count"},
    {"date": "2026-06-12", "type": "fk_break", "expected_anomaly": "fk_break",
     "expected_route": "escalate", "fixable": False,
     "note": "payment trỏ order_id không tồn tại → dimension NULL"},
    {"date": "2026-06-13", "type": "distribution_drift", "expected_anomaly": "distribution_drift",
     "expected_route": "escalate", "fixable": False,
     "note": "amount lệch phân phối mạnh (≈5x) so với baseline"},
    {"date": "2026-06-14", "type": "volume_drop", "expected_anomaly": "volume_drop",
     "expected_route": "escalate", "fixable": False,
     "note": "row count sụt mạnh → nghi late-arriving / thiếu data"},
]

# tra cứu nhanh theo ngày
BY_DATE: dict[str, dict] = {s["date"]: s for s in SCENARIOS}
