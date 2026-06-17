"""Multi-domain seed generator (B-enrich) — cash flow, spend/cost, AR/collections.

Each domain is a *deduction metric*: net = sum(amount) - sum(deduction where status in handled).
That means the existing real engine (tools.run_validation / tools.impact_simulation /
tools.generate_dbt_test) works for every domain WITHOUT new tool code — driven entirely by
the metric contract in memory/metric_memory.json.

The generator embeds realistic anomalies on specific dates so the real detectors, sweep,
validation and reconciliation actually fire:
  enum_drift          -> unmapped new status value -> metric overstated (FIXABLE, real recon)
  null_spike          -> measure NULL on ~40% rows
  missing_partition   -> 0 rows for the date
  duplicate           -> business key counted twice
  distribution_drift  -> amounts ~5x (outlier spike)
  volume_drop         -> row count collapses (late / missing data)

Baselines are the source of truth: dedup by business key, subtract deduction for the
CORRECT set of statuses (base_handled + the drift value), so the buggy pipeline (base only)
overstates exactly on enum-drift dates and reconciliation lands on 0% after the fix.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from database.connection import get_connection, init_schema

HISTORY_START = "2026-02-15"   # ~120 days of history
HISTORY_END = "2026-06-14"
_RNG_SEED = 20260215


@dataclass
class DomainSpec:
    key: str
    label: str
    fact_table: str
    baseline_table: str
    baseline_col: str
    partition_key: str
    measure: str
    status_col: str
    deduction_col: str
    business_key: str
    pk: str
    base_handled: list[str]
    drift_value: str
    normal_statuses: list[str]        # statuses for normal rows (besides base_handled)
    dims: dict[str, list[str]]        # dimension column -> values
    amounts: list[int]
    deduction_ratio: float            # fraction of amount that becomes deduction when applicable
    rows_per_day: tuple[int, int]
    scenarios: dict[str, str]         # date -> anomaly type
    extra_cols: list[str] = field(default_factory=list)


DOMAINS: list[DomainSpec] = [
    DomainSpec(
        key="cash_flow", label="Cash Flow", fact_table="cash_flow_txn",
        baseline_table="cash_flow_baseline", baseline_col="net_cash_correct",
        partition_key="flow_date", measure="amount", status_col="settlement_status",
        deduction_col="held_amount", business_key="settlement_id", pk="cf_id",
        base_handled=["FAILED"], drift_value="CHARGEBACK",
        normal_statuses=["SETTLED", "SETTLED", "SETTLED", "PENDING", "FAILED"],
        dims={"channel": ["BANK", "WALLET", "CARD"], "direction": ["INFLOW", "OUTFLOW"]},
        amounts=[20_000_000, 35_000_000, 50_000_000, 80_000_000, 120_000_000],
        deduction_ratio=1.0, rows_per_day=(280, 360),
        scenarios={"2026-06-05": "enum_drift", "2026-06-12": "enum_drift",  # recurring
                   "2026-05-28": "null_spike", "2026-06-02": "missing_partition",
                   "2026-06-09": "volume_drop", "2026-06-11": "distribution_drift"},
    ),
    DomainSpec(
        key="spend", label="Cost / Spend", fact_table="spend_txn",
        baseline_table="spend_baseline", baseline_col="net_spend_correct",
        partition_key="spend_date", measure="amount", status_col="adjust_status",
        deduction_col="credit_amount", business_key="spend_key", pk="spend_id",
        base_handled=["REBATE"], drift_value="VENDOR_CREDIT",
        normal_statuses=["NONE", "NONE", "NONE", "REBATE"],
        dims={"channel": ["FACEBOOK", "GOOGLE", "TIKTOK", "OPS"], "department": ["MKT", "OPS", "ENG"]},
        amounts=[3_000_000, 6_000_000, 9_000_000, 14_000_000, 22_000_000],
        deduction_ratio=0.4, rows_per_day=(240, 320),
        scenarios={"2026-06-06": "enum_drift", "2026-05-30": "duplicate",
                   "2026-06-03": "distribution_drift", "2026-06-10": "missing_partition",
                   "2026-06-13": "volume_drop"},
    ),
    DomainSpec(
        key="ar", label="AR / Collections", fact_table="invoice_txn",
        baseline_table="ar_baseline", baseline_col="net_receivable_correct",
        partition_key="invoice_date", measure="amount", status_col="ar_status",
        deduction_col="credited_amount", business_key="invoice_key", pk="invoice_id",
        base_handled=["WRITTEN_OFF"], drift_value="DISPUTE_CREDIT",
        normal_statuses=["OPEN", "OPEN", "PAID", "PAID", "WRITTEN_OFF"],
        dims={"segment": ["SME", "ENTERPRISE", "RETAIL"], "region": ["NORTH", "SOUTH", "CENTRAL"]},
        amounts=[15_000_000, 28_000_000, 45_000_000, 70_000_000, 110_000_000],
        deduction_ratio=1.0, rows_per_day=(200, 300),
        scenarios={"2026-06-04": "enum_drift", "2026-06-13": "enum_drift",  # recurring
                   "2026-05-26": "duplicate", "2026-06-01": "null_spike",
                   "2026-06-08": "volume_drop"},
    ),
]


def _daterange(start: str, end: str):
    cur, last = date.fromisoformat(start), date.fromisoformat(end)
    while cur <= last:
        yield cur.isoformat()
        cur += timedelta(days=1)


class _DomainBuilder:
    def __init__(self, spec: DomainSpec, rng: random.Random):
        self.spec = spec
        self.rng = rng
        self.rows: list[tuple] = []
        self._id = 1
        self._bk = 1

    def _row(self, d: str, *, status: str, amount: Optional[int], bk: Optional[int] = None) -> None:
        s = self.spec
        ded = 0
        if status in (*s.base_handled, s.drift_value) and amount:
            ded = int(amount * s.deduction_ratio)
        bkey = bk if bk is not None else self._bk
        if bk is None:
            self._bk += 1
        dim_vals = [self.rng.choice(v) for v in s.dims.values()]
        # column order: pk, partition, measure, status, deduction, business_key, *dims
        self.rows.append((self._id, d, amount, status, ded, bkey, *dim_vals))
        self._id += 1

    def _normal_day(self, d: str, n: int) -> None:
        s = self.spec
        for _ in range(n):
            status = self.rng.choice(s.normal_statuses)
            self._row(d, status=status, amount=self.rng.choice(s.amounts))

    def build(self) -> None:
        s = self.spec
        for d in _daterange(HISTORY_START, HISTORY_END):
            scen = s.scenarios.get(d)
            n = self.rng.randint(*s.rows_per_day)
            if scen == "missing_partition":
                continue                                   # 0 rows
            if scen == "volume_drop":
                self._normal_day(d, max(8, n // 12))
                continue
            if scen == "null_spike":
                ok = int(n * 0.6)
                self._normal_day(d, ok)
                for _ in range(n - ok):
                    self._row(d, status="SETTLED" if s.key == "cash_flow" else s.normal_statuses[0],
                              amount=None)               # measure NULL
                continue
            if scen == "distribution_drift":
                for _ in range(n):
                    self._row(d, status=self.rng.choice(s.normal_statuses),
                              amount=self.rng.choice(s.amounts) * 5)   # outlier spike
                continue
            # normal day first
            self._normal_day(d, n)
            if scen == "enum_drift":
                # unmapped new status value with a real deduction -> metric overstated
                for _ in range(max(12, n // 12)):
                    self._row(d, status=s.drift_value, amount=self.rng.choice(s.amounts))
            elif scen == "duplicate":
                dups = [r for r in self.rows if r[1] == d][: max(10, n // 20)]
                for r in dups:                              # re-insert same business key
                    self._row(d, status=r[3], amount=r[2], bk=r[5])

    def baseline(self) -> dict[str, int]:
        """Correct net per date: dedup by business key, subtract deduction for the CORRECT
        set of statuses (base_handled + drift value)."""
        s = self.spec
        correct_dedups = set(s.base_handled) | {s.drift_value}
        seen: set[int] = set()
        out: dict[str, int] = {}
        for row in self.rows:
            d, amount, status, ded, bkey = row[1], row[2], row[3], row[4], row[5]
            if bkey in seen:
                continue
            seen.add(bkey)
            net = (amount or 0) - (ded if status in correct_dedups else 0)
            out[d] = out.get(d, 0) + net
        return out


def seed_domains(conn) -> dict[str, dict]:
    """Seed all extra domains into an already-init'd schema. Returns per-domain row counts."""
    summary: dict[str, dict] = {}
    rng = random.Random(_RNG_SEED)
    for spec in DOMAINS:
        b = _DomainBuilder(spec, random.Random(rng.randint(1, 10_000_000)))
        b.build()
        cols = [spec.pk, spec.partition_key, spec.measure, spec.status_col,
                spec.deduction_col, spec.business_key, *spec.dims.keys()]
        placeholders = ", ".join("?" for _ in cols)
        conn.executemany(
            f"INSERT INTO {spec.fact_table} ({', '.join(cols)}) VALUES ({placeholders})",
            b.rows,
        )
        conn.executemany(
            f"INSERT OR REPLACE INTO {spec.baseline_table} "
            f"({spec.partition_key}, {spec.baseline_col}) VALUES (?, ?)",
            list(b.baseline().items()),
        )
        summary[spec.key] = {"rows": len(b.rows), "days": len(set(r[1] for r in b.rows))}
    conn.commit()
    return summary


if __name__ == "__main__":
    c = get_connection()
    init_schema(c)
    print(seed_domains(c))
    c.close()
