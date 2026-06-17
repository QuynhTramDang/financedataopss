-- staging.stg_payment — làm sạch payment_txn (tầng 1/3: stg → ods → dtm).
-- Ép kiểu, chuẩn hoá refund_status (UPPER/TRIM), loại bản ghi rác (thiếu khoá/partition).
-- KHÔNG đụng business logic ở tầng staging — chỉ làm sạch.

SELECT
    txn_id,
    txn_date,
    order_id,
    CAST(amount AS INTEGER)            AS amount,
    UPPER(TRIM(refund_status))         AS refund_status,
    CAST(refunded_amount AS INTEGER)   AS refunded_amount
FROM payment_txn
WHERE txn_id IS NOT NULL
  AND txn_date IS NOT NULL
  AND TRIM(refund_status) <> '';
