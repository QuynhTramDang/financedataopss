"""impact_simulation — mismatch trước/sau fix + affected_amount TỪ SQL THẬT (§17, §13).

Bảng/cột/baseline/report lấy từ metric contract (không hardcode payment_txn/refund_status).
before = pipeline hiện handle (contract.base_handled_statuses);
after  = base + new_values (giá trị fix bổ sung). Số tính từ query, không hằng số.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Optional

from database.connection import run_query
from domain.contracts import partition_key_of, safe_ident


def simulate_impact(txn_date: str, new_values: list[str], contract: dict[str, Any],
                    conn: Optional[sqlite3.Connection] = None) -> dict[str, Any]:
    """So net_revenue trước fix (base_handled) vs sau fix (base + new_values), so với baseline."""
    table = safe_ident(contract["fact_table"])
    pkey = partition_key_of(contract["fact_table"])
    measure = safe_ident(contract["measure_column"])
    status = safe_ident(contract["status_column"])
    ded = contract.get("deduction_column")
    ded_col = safe_ident(ded) if ded else None
    base = contract.get("base_handled_statuses", [])

    def _net(statuses: list[str]) -> int:
        if ded_col is None:
            ded_expr = "0"
        else:
            placeholders = ", ".join(f"'{s}'" for s in statuses) or "''"
            ded_expr = f"sum(case when {status} in ({placeholders}) then {ded_col} else 0 end)"
        sql = f"select sum({measure}) - {ded_expr} as net from {table} where {pkey} = :d"
        return run_query(sql, {"d": txn_date}, conn=conn)[0]["net"]

    before_net = _net(base)
    after_net = _net([*base, *new_values])

    bcol = safe_ident(contract["baseline_column"])
    btab = safe_ident(contract["baseline_table"])
    baseline = run_query(
        f"select {bcol} as b from {btab} where {pkey} = :d", {"d": txn_date}, conn=conn,
    )[0]["b"]

    return {
        "before_fix_net": before_net,
        "after_fix_net": after_net,
        "baseline": baseline,
        "before_fix_diff": round((before_net - baseline) / baseline, 6),
        "after_fix_diff": round((after_net - baseline) / baseline, 6),
        "affected_amount": before_net - after_net,
        "affected_report": contract.get("downstream_report"),
    }
