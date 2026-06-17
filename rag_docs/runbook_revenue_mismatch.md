# Runbook: Revenue Mismatch

Khi net_revenue lệch so với payment dashboard:

1. **Freshness**: kiểm tra payment_txn đã load đủ partition của ngày chưa.
2. **Enum drift**: profile `refund_status`, tìm value mới chưa được pipeline handle.
3. **Reconciliation**: so net_revenue của pipeline với baseline (dashboard) theo ngày.
4. **Code review**: đọc `revenue_daily.sql`, kiểm tra mapping refund_status.
5. **Recent deploy**: kiểm tra PR/deploy gần đây có đổi logic không.

Lưu ý: thay đổi mapping refund_status là thay đổi logic Finance → cần Finance Owner approval.
