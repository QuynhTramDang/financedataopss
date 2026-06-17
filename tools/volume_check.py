"""volume_check — so row count partition hiện tại với baseline tính TỪ LỊCH SỬ (§11.2).

Không hardcode ngày tham chiếu: baseline = trung bình row count của N partition gần nhất trước đó.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Optional

from database.connection import run_query
from domain.contracts import partition_key_of, safe_ident

DROP_RATIO = 0.5      # < 50% baseline → coi là volume drop
RECENT_N = 14         # số partition lịch sử dùng làm baseline


def volume_check(txn_date: str, table: str, recent_n: int = RECENT_N,
                 conn: Optional[sqlite3.Connection] = None) -> dict[str, Any]:
    pkey = partition_key_of(table)
    tbl = safe_ident(table)

    cur = run_query(f"select count(*) as c from {tbl} where {pkey} = :d",
                    {"d": txn_date}, conn=conn)[0]["c"]
    rows = run_query(
        f"select avg(c) as b from (select {pkey} as p, count(*) as c from {tbl} "
        f"where {pkey} < :d group by {pkey} order by p desc limit :n)",
        {"d": txn_date, "n": recent_n}, conn=conn)
    baseline = rows[0]["b"] or 0
    drop = baseline > 0 and cur < DROP_RATIO * baseline
    return {"row_count": cur, "baseline": round(baseline, 1), "drop": bool(drop)}
