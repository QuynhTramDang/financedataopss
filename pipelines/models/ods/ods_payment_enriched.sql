-- ods.ods_payment_enriched — tầng 2/3: enrich payment bằng dimension order + map refund.
--
-- 1) Khử trùng giao dịch theo txn_id (window ROW_NUMBER) — guard chống double-insert ở nguồn.
-- 2) JOIN dimension order (region/category) — LEFT JOIN để giữ payment kể cả khi order mất
--    (FK break sẽ lộ ra: region/category = NULL dù order_id khác NULL).
-- 3) ⚠️ BUG CỐ Ý (refund mapping): refunded_effective chỉ tính cho refund_status = 'REFUNDED',
--    BỎ SÓT 'PARTIAL_REFUND'. Đây là nơi root cause của case revenue mismatch nằm.
--    Patch sẽ đổi điều kiện thành: refund_status IN ('REFUNDED', 'PARTIAL_REFUND').

WITH dedup AS (
    SELECT
        p.*,
        ROW_NUMBER() OVER (PARTITION BY p.txn_id ORDER BY p.txn_id) AS _rn
    FROM stg_payment p
)
SELECT
    d.txn_id,
    d.txn_date,
    d.order_id,
    d.amount,
    d.refund_status,
    d.refunded_amount,
    o.customer_id,
    o.region,
    o.category,
    CASE
        WHEN d.refund_status = 'REFUNDED' THEN d.refunded_amount
        ELSE 0
    END AS refunded_effective
FROM dedup d
LEFT JOIN stg_order o ON o.order_id = d.order_id
WHERE d._rn = 1;
