"""duplicate_check — phát hiện bản ghi trùng theo business key trong 1 partition (§11.2).

Đếm số business key xuất hiện >1 lần (vd 1 đơn bị tính 2 lần) → double count. Bảng/cột do caller
truyền (key_col = contract.business_key); partition column suy từ metadata.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Optional

from database.connection import run_query
from domain.contracts import partition_key_of, safe_ident


def duplicate_check(txn_date: str, table: str, key_col: str,
                    conn: Optional[sqlite3.Connection] = None) -> dict[str, Any]:
    pkey = partition_key_of(table)
    rows = run_query(
        f"select {safe_ident(key_col)} as k, count(*) as c from {safe_ident(table)} "
        f"where {pkey} = :d group by {safe_ident(key_col)} having count(*) > 1",
        {"d": txn_date}, conn=conn)
    dup_groups = len(rows)
    dup_rows = sum(r["c"] - 1 for r in rows)
    return {"key_col": key_col, "dup_groups": dup_groups, "dup_rows": dup_rows,
            "has_duplicate": dup_groups > 0}
