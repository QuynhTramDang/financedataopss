-- Schema cho demo Finance DataOps Twin (SQLite).
-- Đây là các bảng NGUỒN (raw landing). Các tầng stg → ods → dtm KHÔNG nằm ở đây mà được
-- materialize bởi pipelines/run_pipeline.py (CREATE TABLE AS) từ các file SQL trong pipelines/models.
--
-- payment_txn   : giao dịch thanh toán (partition theo txn_date). order_id là FK mềm → order_fact.
-- order_fact    : đơn hàng (dimension: customer/region/category) — để JOIN ở tầng ods + test FK.
-- revenue_baseline: "payment dashboard" — net_revenue ĐÚNG (nguồn sự thật độc lập để reconciliation).

DROP TABLE IF EXISTS payment_txn;
CREATE TABLE payment_txn (
    txn_id          INTEGER PRIMARY KEY,
    txn_date        TEXT    NOT NULL,          -- partition key, 'YYYY-MM-DD'
    amount          INTEGER,                   -- paid_amount (gross); contract = not null,
                                               -- nhưng DB cho phép null để mô phỏng null spike
    refund_status   TEXT    NOT NULL,          -- NONE | REFUNDED | PARTIAL_REFUND
    refunded_amount INTEGER NOT NULL DEFAULT 0,-- số tiền đã hoàn
    order_id        INTEGER                    -- FK mềm → order_fact.order_id (nullable)
);
CREATE INDEX idx_payment_txn_date ON payment_txn (txn_date);
CREATE INDEX idx_payment_txn_order ON payment_txn (order_id);

DROP TABLE IF EXISTS order_fact;
CREATE TABLE order_fact (
    order_id     INTEGER PRIMARY KEY,
    txn_date     TEXT    NOT NULL,
    customer_id  INTEGER,
    region       TEXT,                          -- NORTH | SOUTH | CENTRAL
    category     TEXT,                          -- GAME | ADS | PAYMENT
    order_amount INTEGER,
    order_status TEXT
);
CREATE INDEX idx_order_fact_date ON order_fact (txn_date);

DROP TABLE IF EXISTS revenue_baseline;
CREATE TABLE revenue_baseline (
    txn_date            TEXT PRIMARY KEY,
    net_revenue_correct INTEGER NOT NULL       -- net_revenue đúng theo định nghĩa Finance
);

-- ════════════════════════════════════════════════════════════════════════
-- Multi-domain warehouse (B-enrich): cash flow, spend/cost, AR/collections.
-- Mỗi domain dùng CHUNG engine deduction-metric (measure - deduction cho 1 số
-- status) nên run_validation / simulate_impact / generate_dbt_test chạy thật
-- mà KHÔNG cần tool mới. Mỗi domain có baseline riêng (nguồn sự thật reconcile).
-- ════════════════════════════════════════════════════════════════════════

-- ── Cash Flow (treasury) ──
DROP TABLE IF EXISTS cash_flow_txn;
CREATE TABLE cash_flow_txn (
    cf_id             INTEGER PRIMARY KEY,
    flow_date         TEXT    NOT NULL,         -- partition key
    amount            INTEGER,                  -- gross cash movement
    settlement_status TEXT    NOT NULL,         -- SETTLED | PENDING | FAILED | CHARGEBACK(drift)
    held_amount       INTEGER NOT NULL DEFAULT 0,-- reversed/held cash (deduction)
    settlement_id     INTEGER,                  -- business key (dedup)
    channel           TEXT,                     -- BANK | WALLET | CARD
    direction         TEXT                      -- INFLOW | OUTFLOW
);
CREATE INDEX idx_cf_date ON cash_flow_txn (flow_date);
DROP TABLE IF EXISTS cash_flow_baseline;
CREATE TABLE cash_flow_baseline (
    flow_date       TEXT PRIMARY KEY,
    net_cash_correct INTEGER NOT NULL
);

-- ── Cost / Spend ──
DROP TABLE IF EXISTS spend_txn;
CREATE TABLE spend_txn (
    spend_id      INTEGER PRIMARY KEY,
    spend_date    TEXT    NOT NULL,             -- partition key
    amount        INTEGER,                      -- gross spend
    adjust_status TEXT    NOT NULL,             -- NONE | REBATE | VENDOR_CREDIT(drift)
    credit_amount INTEGER NOT NULL DEFAULT 0,   -- rebate/credit (deduction)
    spend_key     INTEGER,                      -- business key (dedup)
    channel       TEXT,                         -- FACEBOOK | GOOGLE | TIKTOK | OPS
    department    TEXT                          -- MKT | OPS | ENG
);
CREATE INDEX idx_spend_date ON spend_txn (spend_date);
DROP TABLE IF EXISTS spend_baseline;
CREATE TABLE spend_baseline (
    spend_date       TEXT PRIMARY KEY,
    net_spend_correct INTEGER NOT NULL
);

-- ── AR / Collections ──
DROP TABLE IF EXISTS invoice_txn;
CREATE TABLE invoice_txn (
    invoice_id      INTEGER PRIMARY KEY,
    invoice_date    TEXT    NOT NULL,           -- partition key
    amount          INTEGER,                    -- invoiced amount
    ar_status       TEXT    NOT NULL,           -- OPEN | PAID | WRITTEN_OFF | DISPUTE_CREDIT(drift)
    credited_amount INTEGER NOT NULL DEFAULT 0, -- written-off / credited (deduction)
    invoice_key     INTEGER,                    -- business key (dedup)
    segment         TEXT,                       -- SME | ENTERPRISE | RETAIL
    region          TEXT                        -- NORTH | SOUTH | CENTRAL
);
CREATE INDEX idx_invoice_date ON invoice_txn (invoice_date);
DROP TABLE IF EXISTS ar_baseline;
CREATE TABLE ar_baseline (
    invoice_date         TEXT PRIMARY KEY,
    net_receivable_correct INTEGER NOT NULL
);
