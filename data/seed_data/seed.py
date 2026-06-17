"""Seed dữ liệu demo (deterministic) — nhiều ngày + nhiều scenario (B1).

Nguyên tắc:
  - Mọi con số reconciliation tính TỪ SQL (không hardcode). revenue_baseline = net_revenue ĐÚNG,
    tính dedup theo order_id + trừ refund cho MỌI loại (REFUNDED, PARTIAL_REFUND).
  - 4 ngày lõi GIỮ NGUYÊN số để không phá test cũ:
      2026-06-07 enum drift PARTIAL_REFUND  → mismatch 2.1% (case 1)
      2026-06-08 null spike (amount NULL 40%)
      2026-06-09 missing partition (0 row)
      2026-06-10 clean (negative case)
  - Bổ sung scenario mới (xem scenarios.py): 06-11 duplicate, 06-12 fk_break,
    06-13 distribution_drift, 06-14 volume_drop; + ~30 ngày lịch sử bình thường 16/05–06/06.

  Case 1 (giữ nguyên):
    refund_status   | rows | amount/row | refunded/row | Σ amount        | Σ refunded
    NONE            |  951 | 10,000,000 |            0 |  9,510,000,000  |           0
    REFUNDED        |  250 | 10,000,000 |   10,000,000 |  2,500,000,000  | 2,500,000,000
    PARTIAL_REFUND  |   70 | 10,000,000 |    3,000,000 |    700,000,000  |   210,000,000
    net_revenue ĐÚNG = 10,000,000,000 ; BUG (chỉ REFUNDED) = 10,210,000,000 ; mismatch = 2.1%
"""

from __future__ import annotations

import random
import sqlite3
from datetime import date, timedelta
from typing import Optional

from database.connection import get_connection, init_schema

# ── ngày các case ──────────────────────────────────────────────
PRIMARY_TXN_DATE = "2026-06-07"      # enum drift PARTIAL_REFUND
SECOND_TXN_DATE = "2026-06-08"       # null spike
MISSING_TXN_DATE = "2026-06-09"      # missing partition
CLEAN_TXN_DATE = "2026-06-10"        # clean / negative
DUP_TXN_DATE = "2026-06-11"          # duplicate (double count theo order_id)
FK_BREAK_TXN_DATE = "2026-06-12"     # FK break (order_id mồ côi)
DRIFT_TXN_DATE = "2026-06-13"        # distribution drift (amount ≈5x)
LOWVOL_TXN_DATE = "2026-06-14"       # volume drop / late-arriving
HISTORY_START = "2026-02-15"         # lịch sử bình thường ~120 ngày (đến 06-06)
HISTORY_END = "2026-06-06"

# ── case 1 (giữ nguyên) ────────────────────────────────────────
# (refund_status, rows, amount_per_row, refunded_per_row)
_GROUPS = [
    ("NONE", 951, 10_000_000, 0),
    ("REFUNDED", 250, 10_000_000, 10_000_000),
    ("PARTIAL_REFUND", 70, 10_000_000, 3_000_000),
]

# case 2 (null spike): 120 ok + 80 amount=NULL → null_rate 40%
SECOND_OK_ROWS = 120
SECOND_NULL_ROWS = 80
SECOND_NULL_RATE = SECOND_NULL_ROWS / (SECOND_NULL_ROWS + SECOND_OK_ROWS)

# Hằng số kỳ vọng (cho test/eval — vẫn được kiểm chứng lại bằng SQL).
AFFECTED_AMOUNT = 210_000_000
NET_REVENUE_CORRECT = 10_000_000_000
EXPECTED_MISMATCH = 0.021

# ── tham số sinh data bình thường ──────────────────────────────
REGIONS = ["NORTH", "SOUTH", "CENTRAL"]
CATEGORIES = ["GAME", "ADS", "PAYMENT"]
_AMOUNTS = [5_000_000, 8_000_000, 10_000_000, 12_000_000, 15_000_000]
_REFUND_PROB = 0.18
_RNG_SEED = 20260607


def _daterange(start: str, end: str):
    d0 = date.fromisoformat(start)
    d1 = date.fromisoformat(end)
    cur = d0
    while cur <= d1:
        yield cur.isoformat()
        cur += timedelta(days=1)


class _Builder:
    """Sinh rows payment_txn + order_fact (deterministic). order_id mồ côi → fk break."""

    def __init__(self, rng: random.Random):
        self.rng = rng
        self.payments: list[tuple] = []   # (txn_id, date, amount, status, refunded, order_id)
        self.orders: dict[int, tuple] = {}  # order_id → (date, customer, region, category, amount, status)
        self._txn = 1
        self._ord = 1

    def _new_order(self, txn_date: str, amount: Optional[int]) -> int:
        oid = self._ord
        self._ord += 1
        self.orders[oid] = (
            txn_date, 1000 + (oid % 500),
            REGIONS[oid % len(REGIONS)], CATEGORIES[oid % len(CATEGORIES)],
            amount or 0, "PAID",
        )
        return oid

    def _orphan_order(self) -> int:
        """order_id được payment tham chiếu nhưng KHÔNG tạo trong order_fact (FK break)."""
        oid = self._ord
        self._ord += 1
        return oid

    def _add(self, txn_date: str, amount, status: str, refunded: int, order_id: int) -> None:
        self.payments.append((self._txn, txn_date, amount, status, refunded, order_id))
        self._txn += 1

    def _normal_row(self, txn_date: str, *, order_id: Optional[int] = None,
                    amount: Optional[int] = None) -> None:
        amt = amount if amount is not None else self.rng.choice(_AMOUNTS)
        status = "REFUNDED" if self.rng.random() < _REFUND_PROB else "NONE"
        refunded = amt if status == "REFUNDED" else 0
        oid = order_id if order_id is not None else self._new_order(txn_date, amt)
        self._add(txn_date, amt, status, refunded, oid)

    def build(self) -> None:
        # ── lịch sử bình thường 16/05–06/06 ──
        for d in _daterange(HISTORY_START, HISTORY_END):
            for _ in range(self.rng.randint(1000, 1300)):
                self._normal_row(d)

        # ── 06-07 enum drift PARTIAL_REFUND (giữ nguyên số) ──
        for status, n, amt, refunded in _GROUPS:
            for _ in range(n):
                oid = self._new_order(PRIMARY_TXN_DATE, amt)
                self._add(PRIMARY_TXN_DATE, amt, status, refunded, oid)

        # ── 06-08 null spike ──
        for _ in range(SECOND_OK_ROWS):
            oid = self._new_order(SECOND_TXN_DATE, 10_000_000)
            self._add(SECOND_TXN_DATE, 10_000_000, "NONE", 0, oid)
        for _ in range(SECOND_NULL_ROWS):
            oid = self._new_order(SECOND_TXN_DATE, 10_000_000)
            self._add(SECOND_TXN_DATE, None, "NONE", 0, oid)  # amount NULL

        # ── 06-09 missing partition: không insert ──

        # ── 06-10 clean ──
        for _ in range(1000):
            oid = self._new_order(CLEAN_TXN_DATE, 10_000_000)
            self._add(CLEAN_TXN_DATE, 10_000_000, "NONE", 0, oid)
        for _ in range(200):
            oid = self._new_order(CLEAN_TXN_DATE, 10_000_000)
            self._add(CLEAN_TXN_DATE, 10_000_000, "REFUNDED", 10_000_000, oid)

        # ── 06-11 duplicate: 1000 đơn, 50 đơn bị tính 2 lần (cùng order_id) ──
        dup_seed: list[tuple] = []
        for _ in range(1000):
            amt = self.rng.choice(_AMOUNTS)
            status = "REFUNDED" if self.rng.random() < _REFUND_PROB else "NONE"
            refunded = amt if status == "REFUNDED" else 0
            oid = self._new_order(DUP_TXN_DATE, amt)
            self._add(DUP_TXN_DATE, amt, status, refunded, oid)
            dup_seed.append((amt, status, refunded, oid))
        for amt, status, refunded, oid in dup_seed[:50]:
            self._add(DUP_TXN_DATE, amt, status, refunded, oid)  # double count

        # ── 06-12 fk_break: 40/1000 payment trỏ order_id mồ côi ──
        for i in range(1000):
            if i < 40:
                amt = self.rng.choice(_AMOUNTS)
                status = "NONE"
                self._add(FK_BREAK_TXN_DATE, amt, status, 0, self._orphan_order())
            else:
                self._normal_row(FK_BREAK_TXN_DATE)

        # ── 06-13 distribution drift: amount ≈5x ──
        for _ in range(1000):
            self._normal_row(DRIFT_TXN_DATE, amount=50_000_000)

        # ── 06-14 volume drop ──
        for _ in range(60):
            self._normal_row(LOWVOL_TXN_DATE)

    def baselines(self) -> dict[str, int]:
        """net_revenue ĐÚNG mỗi ngày: dedup theo order_id, trừ refund cho mọi loại refund."""
        seen: set[int] = set()
        out: dict[str, int] = {}
        for _txn, txn_date, amount, status, refunded, order_id in self.payments:
            if order_id in seen:
                continue  # bản ghi trùng (double count ở nguồn) → loại khỏi số ĐÚNG
            seen.add(order_id)
            net = (amount or 0) - (refunded if status in ("REFUNDED", "PARTIAL_REFUND") else 0)
            out[txn_date] = out.get(txn_date, 0) + net
        return out


def seed_database(conn: sqlite3.Connection, txn_date: str = PRIMARY_TXN_DATE) -> None:
    """Tạo schema + nạp payment_txn, order_fact, revenue_baseline (raw layer)."""
    init_schema(conn)
    builder = _Builder(random.Random(_RNG_SEED))
    builder.build()

    conn.executemany(
        "INSERT INTO payment_txn (txn_id, txn_date, amount, refund_status, refunded_amount, order_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        builder.payments,
    )
    conn.executemany(
        "INSERT INTO order_fact (order_id, txn_date, customer_id, region, category, "
        "order_amount, order_status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(oid, *vals) for oid, vals in builder.orders.items()],
    )
    conn.executemany(
        "INSERT OR REPLACE INTO revenue_baseline (txn_date, net_revenue_correct) VALUES (?, ?)",
        list(builder.baselines().items()),
    )
    conn.commit()


def main(db_path: Optional[str] = None) -> None:
    """Seed raw + materialize layer stg/ods/dtm + in tóm tắt."""
    from pipelines.run_pipeline import build_layers

    from data.seed_data.domains import seed_domains

    conn = get_connection(db_path)
    try:
        seed_database(conn)
        build_layers(conn)
        dom = seed_domains(conn)          # cash flow + spend + AR (multi-domain warehouse)
        n = conn.execute("SELECT COUNT(*) FROM payment_txn").fetchone()[0]
        days = conn.execute("SELECT COUNT(DISTINCT txn_date) FROM payment_txn").fetchone()[0]
        base07 = conn.execute(
            "SELECT net_revenue_correct FROM revenue_baseline WHERE txn_date = ?",
            (PRIMARY_TXN_DATE,)).fetchone()[0]
        print(f"Seeded {n} payment rows across {days} days (revenue).")
        print(f"revenue_baseline[{PRIMARY_TXN_DATE}] = {base07:,} (expected {NET_REVENUE_CORRECT:,})")
        for k, v in dom.items():
            print(f"  domain {k}: {v['rows']} rows across {v['days']} days")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
