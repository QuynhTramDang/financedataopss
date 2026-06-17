-- staging.stg_order — làm sạch order_fact (tầng 1/3).
-- Chuẩn hoá region/category, ép kiểu order_amount.

SELECT
    order_id,
    txn_date,
    customer_id,
    UPPER(TRIM(region))        AS region,
    UPPER(TRIM(category))      AS category,
    CAST(order_amount AS INTEGER) AS order_amount,
    UPPER(TRIM(order_status))  AS order_status
FROM order_fact
WHERE order_id IS NOT NULL;
