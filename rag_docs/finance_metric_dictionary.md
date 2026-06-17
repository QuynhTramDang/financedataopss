# Finance Metric Dictionary

## net_revenue
Định nghĩa: `net_revenue = paid_amount - refunded_amount`.
- Owner: Finance
- Source: payment_txn, order_fact
- refunded_amount phải bao gồm mọi loại hoàn tiền: `REFUNDED` và `PARTIAL_REFUND`.
- SLA: daily 09:00.

## gross_revenue
Định nghĩa: `gross_revenue = sum(paid_amount)`, chưa trừ refund.

## refund_status (enum)
Các giá trị hợp lệ: `NONE`, `REFUNDED`, `PARTIAL_REFUND`.
`PARTIAL_REFUND` được Finance quyết định tính vào refunded_amount từ 2026-06-01.
