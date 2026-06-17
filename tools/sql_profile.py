"""sql_profile — chạy SQL aggregate (QUA governance) để profile anomaly/enum/null (§13).

Bảng/cột/partition lấy từ caller (suy từ metric contract + metadata), KHÔNG hardcode.
Chỉ trả aggregate (count/measure/deduction), KHÔNG raw rows. SQL phải pass sql_policy trước khi chạy.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Optional

from database.connection import run_query
from domain.contracts import partition_key_of, safe_ident
from governance import check_sql


def sql_profile(txn_date: str, table: str, group_col: str, measure_column: str,
                deduction_column: Optional[str] = None,
                conn: Optional[sqlite3.Connection] = None) -> dict[str, Any]:
    """Profile theo `group_col` cho 1 partition. Trả {governance, profile, sql}.

    profile: { value: {count, measure, deduction} } — chỉ số tổng hợp, 0 raw row.
    measure = sum(measure_column); deduction = sum(deduction_column) (0 nếu không có).
    """
    pkey = partition_key_of(table)
    table = safe_ident(table)
    group_col = safe_ident(group_col)
    measure_column = safe_ident(measure_column)
    ded_expr = f"sum({safe_ident(deduction_column)})" if deduction_column else "0"

    sql = (
        f"select {group_col} as value, count(*) as cnt, "
        f"sum({measure_column}) as measure, {ded_expr} as deduction "
        f"from {table} where {pkey} = :d group by {group_col}"
    )

    gov = check_sql(sql)
    if gov["decision"] != "allowed":
        return {"governance": gov, "profile": {}, "sql": sql}

    rows = run_query(sql, {"d": txn_date}, conn=conn)
    profile = {
        r["value"]: {
            "count": r["cnt"],
            "measure": r["measure"] or 0,
            "deduction": r["deduction"] or 0,
        }
        for r in rows
    }
    return {"governance": gov, "profile": profile, "sql": sql}
