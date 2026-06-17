"""freshness_check — partition của ngày có data chưa (§11.2). row_count=0 → missing partition.

Bảng do caller truyền; partition column suy từ metadata (không hardcode 'txn_date').
"""

from __future__ import annotations

import sqlite3
from typing import Any, Optional

from database.connection import run_query
from domain.contracts import partition_key_of, safe_ident


def freshness_check(txn_date: str, table: str,
                    conn: Optional[sqlite3.Connection] = None) -> dict[str, Any]:
    pkey = partition_key_of(table)
    n = run_query(f"select count(*) as c from {safe_ident(table)} where {pkey} = :d",
                  {"d": txn_date}, conn=conn)[0]["c"]
    return {"row_count": n, "loaded": n > 0}
