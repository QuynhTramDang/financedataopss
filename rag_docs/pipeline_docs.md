# Pipeline Documentation

## revenue_daily
- File: `pipelines/models/finance/revenue_daily.sql`
- Metric: net_revenue
- Lineage: `payment_txn` → `revenue_daily` → `finance_revenue_report`
- Upstream: payment_txn, order_fact
- Downstream: finance_revenue_report (dashboard Finance)
- Common issues: schema drift, late-arriving payment, refund_status mapping.
- Logic chính: net_revenue = sum(amount) - sum(refunded_amount theo refund_status được map).
