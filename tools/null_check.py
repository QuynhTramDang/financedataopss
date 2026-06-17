"""null_check — null rate của một cột quan trọng trong partition (§11.2).

Bảng/cột do caller truyền (suy từ contract.measure_column); partition column từ metadata.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Optional

from database.connection import run_query
from domain.contracts import partition_key_of, safe_ident

SPIKE_THRESHOLD = 0.05   # > 5% null → spike


def null_check(txn_date: str, table: str, column: str,
               conn: Optional[sqlite3.Connection] = None) -> dict[str, Any]:
    pkey = partition_key_of(table)
    col = safe_ident(column)
    row = run_query(
        f"select count(*) as total, sum(case when {col} is null then 1 else 0 end) as nulls "
        f"from {safe_ident(table)} where {pkey} = :d",
        {"d": txn_date}, conn=conn)[0]
    total = row["total"] or 0
    nulls = row["nulls"] or 0
    rate = (nulls / total) if total else 0.0
    return {"column": column, "total": total, "null_count": nulls,
            "null_rate": round(rate, 4), "spike": rate > SPIKE_THRESHOLD}
