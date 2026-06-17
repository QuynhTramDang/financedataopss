"""sql_policy — chặn SQL nguy hiểm trước khi chạy (§12.3, §12.4).

Quy tắc (read-only MVP):
  1. Cấm `select *` (phải chọn cột cụ thể hoặc aggregate).
  2. Bảng có partition BẮT BUỘC filter theo partition key (chống full scan).
  3. Cấm DML/DDL (insert/update/delete/drop/alter/truncate) — MVP chỉ read-only.

Trả về dict: {tool, decision: 'allowed'|'blocked', reason, suggestion}.
"""

from __future__ import annotations

import re

from domain.contracts import partitioned_tables

_WRITE_KEYWORDS = ("insert", "update", "delete", "drop", "alter", "truncate", "create", "merge")

_AGG_SUGGESTION = (
    "Dùng aggregate có filter partition, vd:\n"
    "select <group_col>, count(*) as cnt, sum(<measure>) as total\n"
    "from <table>\nwhere <partition_key> = '<value>'\ngroup by <group_col>;"
)


def _allowed(reason: str = "passes SQL policy") -> dict:
    return {"tool": "run_sql", "decision": "allowed", "reason": reason, "suggestion": None}


def _blocked(reason: str, suggestion: str | None = None) -> dict:
    return {"tool": "run_sql", "decision": "blocked", "reason": reason, "suggestion": suggestion}


def check_sql(sql: str) -> dict:
    low = " ".join(sql.lower().split())  # normalize whitespace

    # 3. read-only
    for kw in _WRITE_KEYWORDS:
        if re.search(rf"\b{kw}\b", low):
            return _blocked(f"DML/DDL '{kw}' không được phép (MVP read-only).")

    # 1. select *
    if re.search(r"select\s+\*", low):
        return _blocked(
            "Cấm `select *` — chọn cột cụ thể hoặc dùng aggregate.",
            suggestion=_AGG_SUGGESTION,
        )

    # 2. partition filter cho bảng có partition (đọc từ metadata, không hardcode)
    for table, pkey in partitioned_tables().items():
        if re.search(rf"\b{table}\b", low) and pkey not in low:
            return _blocked(
                f"Query chạm `{table}` nhưng thiếu filter partition `{pkey}` (nguy cơ full scan).",
                suggestion=f"Thêm điều kiện `where {pkey} = '<YYYY-MM-DD>'` trước khi chạy.",
            )

    return _allowed()
