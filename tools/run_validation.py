"""run_validation — Validation Engine DETERMINISTIC (§17). LLM KHÔNG quyết pass/fail (§14.5).

Bảng/cột/accepted_values/key_columns lấy từ metric contract (không hardcode payment_txn/refund_status).
Chạy: schema_contract, null, duplicate, accepted_values, revenue_reconciliation (before/after từ SQL).
"""

from __future__ import annotations

import sqlite3
from typing import Any, Optional

from database.connection import run_query
from domain.contracts import partition_key_of, safe_ident
from tools.impact_simulation import simulate_impact

RECON_TOLERANCE = 0.001  # 0.1%


def _schema_check(table: str, key_cols: list[str], conn) -> dict:
    cols = {r["name"] for r in run_query(f"PRAGMA table_info({safe_ident(table)})", conn=conn)}
    required = set(key_cols)
    ok = required <= cols
    return {"name": "schema_contract_check", "status": "PASS" if ok else "FAIL",
            "missing": sorted(required - cols)}


def _null_check(table, pkey, measure, deduction, txn_date, conn) -> dict:
    cols = [measure] + ([deduction] if deduction else [])
    cond = " or ".join(f"{safe_ident(c)} is null" for c in cols)
    n = run_query(
        f"select count(*) as c from {safe_ident(table)} where {pkey} = :d and ({cond})",
        {"d": txn_date}, conn=conn)[0]["c"]
    return {"name": "null_check", "status": "PASS" if n == 0 else "FAIL", "null_rows": n}


def _duplicate_check(table, pkey, id_col, txn_date, conn) -> dict:
    n = run_query(
        f"select count(*) as c from (select {safe_ident(id_col)} from {safe_ident(table)} "
        f"where {pkey} = :d group by {safe_ident(id_col)} having count(*) > 1)",
        {"d": txn_date}, conn=conn)[0]["c"]
    return {"name": "duplicate_transaction_check", "status": "PASS" if n == 0 else "FAIL",
            "duplicates": n}


def _accepted_values_check(table, pkey, status_col, accepted, txn_date, conn) -> dict:
    vals = {r[status_col] for r in run_query(
        f"select distinct {safe_ident(status_col)} as {status_col} from {safe_ident(table)} "
        f"where {pkey} = :d", {"d": txn_date}, conn=conn)}
    unexpected = sorted(vals - set(accepted))
    return {"name": "accepted_values_check", "status": "PASS" if not unexpected else "FAIL",
            "unexpected": unexpected}


def run_validation(txn_date: str, new_values: list[str], contract: dict[str, Any],
                   conn: Optional[sqlite3.Connection] = None) -> dict[str, Any]:
    """Chạy toàn bộ test + reconciliation before/after fix theo contract."""
    table = contract["fact_table"]
    pkey = partition_key_of(table)
    status_col = contract["status_column"]
    measure = contract["measure_column"]
    deduction = contract.get("deduction_column")
    key_cols = contract.get("key_columns", [])
    id_col = key_cols[0] if key_cols else pkey
    accepted = contract.get("accepted_values", {}).get(status_col, [])

    tests = [
        _schema_check(table, key_cols, conn),
        _null_check(table, pkey, measure, deduction, txn_date, conn),
        _duplicate_check(table, pkey, id_col, txn_date, conn),
        _accepted_values_check(table, pkey, status_col, accepted, txn_date, conn),
    ]

    impact = simulate_impact(txn_date, new_values, contract, conn=conn)
    recon_pass = abs(impact["after_fix_diff"]) < RECON_TOLERANCE
    tests.append({
        "name": "revenue_reconciliation_check",
        "status": "PASS" if recon_pass else "FAIL",
        "before_fix_diff": impact["before_fix_diff"],
        "after_fix_diff": impact["after_fix_diff"],
    })

    status = "PASS" if all(t["status"] == "PASS" for t in tests) else "FAIL"
    passed = sum(1 for t in tests if t["status"] == "PASS")
    return {
        "validation_status": status,
        "tests": tests,
        "passed": passed,
        "total": len(tests),
        "reconciliation": {
            "before_fix_diff": impact["before_fix_diff"],
            "after_fix_diff": impact["after_fix_diff"],
        },
    }
