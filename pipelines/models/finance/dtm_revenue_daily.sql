-- finance.dtm_revenue_daily — tầng 3/3 (data mart): metric ngày cho Finance.
-- net_revenue dùng refunded_effective (mang theo BUG từ ODS nếu chưa patch).
-- Có window function (7-day moving average) để phục vụ distribution/volume drift check.

WITH daily AS (
    SELECT
        txn_date,
        SUM(amount)                            AS gross_revenue,
        SUM(amount) - SUM(refunded_effective)  AS net_revenue,
        SUM(refunded_effective)                AS total_refunded,
        COUNT(*)                               AS txn_count,
        COUNT(DISTINCT order_id)               AS order_count
    FROM ods_payment_enriched
    GROUP BY txn_date
)
SELECT
    txn_date,
    gross_revenue,
    net_revenue,
    total_refunded,
    txn_count,
    order_count,
    CASE WHEN gross_revenue > 0
         THEN ROUND(1.0 * total_refunded / gross_revenue, 4)
         ELSE 0 END                            AS refund_rate,
    ROUND(AVG(net_revenue) OVER (
        ORDER BY txn_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    )) AS net_revenue_7d_avg
FROM daily
ORDER BY txn_date;
