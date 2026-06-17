# Data Contracts

## payment_txn
- partition_key: `txn_date`
- columns: txn_id, txn_date, amount, refund_status, refunded_amount
- refund_status accepted_values: `NONE`, `REFUNDED`, `PARTIAL_REFUND`
- amount, refunded_amount: not null, >= 0
- Mọi query phải filter theo `txn_date` (cấm full scan).

## order_fact
- partition_key: `order_date`
- dùng cho join doanh thu theo order.
