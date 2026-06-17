"""distribution_drift_check — phát hiện phân phối measure lệch mạnh so với lịch sử (§11.2).

So avg(measure) hôm nay vs trung bình N partition trước. ratio ngoài [0.5, 2] → drift.
Không hardcode ngày/cột: measure_col do caller (contract.measure_column), partition từ metadata.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Optional

from database.connection import run_query
from domain.contracts import partition_key_of, safe_ident

LOW, HIGH = 0.5, 2.0
RECENT_N = 14


def distribution_drift_check(txn_date: str, table: str, measure_col: str,
                             recent_n: int = RECENT_N,
                             conn: Optional[sqlite3.Connection] = None) -> dict[str, Any]:
    pkey = partition_key_of(table)
    tbl, col = safe_ident(table), safe_ident(measure_col)
    today = run_query(f"select avg({col}) as a from {tbl} where {pkey} = :d",
                      {"d": txn_date}, conn=conn)[0]["a"]
    base = run_query(
        f"select avg(a) as b from (select {pkey} as p, avg({col}) as a from {tbl} "
        f"where {pkey} < :d group by {pkey} order by p desc limit :n)",
        {"d": txn_date, "n": recent_n}, conn=conn)[0]["b"]
    ratio = (today / base) if (today is not None and base) else None
    drift = ratio is not None and (ratio > HIGH or ratio < LOW)
    return {"avg_today": today, "baseline_avg": round(base, 1) if base else None,
            "ratio": round(ratio, 2) if ratio is not None else None, "drift": bool(drift)}
