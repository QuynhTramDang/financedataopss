# Previous Incidents

## INC-2026-0520 — refund_status mapping
- Metric: net_revenue
- Triệu chứng: net_revenue overstated.
- Root cause: xuất hiện refund_status value mới chưa được `revenue_daily` xử lý.
- Fix: cập nhật refund mapping logic.
- Approved by: Data Owner.
- Bài học: profile enum của refund_status mỗi khi revenue lệch.
