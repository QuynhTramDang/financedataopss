-- models/finance/revenue_daily.sql
--
-- Pipeline tính net_revenue hằng ngày.
-- Định nghĩa Finance: net_revenue = paid_amount - refunded_amount
--                     (refunded_amount tính cho MỌI loại hoàn tiền).
--
-- ⚠️ BUG CỐ Ý: chỉ trừ refund khi refund_status = 'REFUNDED', BỎ SÓT 'PARTIAL_REFUND'.
--    → net_revenue bị overstated khi xuất hiện giao dịch PARTIAL_REFUND.
--    Patch ở Step 9 sẽ đổi điều kiện thành: refund_status in ('REFUNDED', 'PARTIAL_REFUND').
--
-- :txn_date là tham số partition (bắt buộc — governance chặn full scan).

SELECT
    txn_date,
    SUM(amount) - SUM(
        CASE WHEN refund_status = 'REFUNDED' THEN refunded_amount ELSE 0 END
    ) AS net_revenue
FROM payment_txn
WHERE txn_date = :txn_date
GROUP BY txn_date;
