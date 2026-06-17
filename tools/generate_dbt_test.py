"""generate_dbt_test — sinh dbt test chặn tái diễn + chứng minh "test đáng lẽ đã bắt được lỗi".

Bảng/cột/accepted_values/model lấy từ metric contract (không hardcode). VERIFY bằng Validation Engine:
test phải FAIL trên logic cũ (chưa map value mới) và PASS sau patch.
Guardrail: chỉ TRẢ nội dung (không tự ghi vào pipeline) — ghi ra proposed/ khi được approve.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Optional

from tools.run_validation import run_validation


def _yaml(contract: dict, accepted: list[str]) -> str:
    values = ", ".join(f"'{v}'" for v in accepted)
    table = contract["fact_table"]
    status = contract["status_column"]
    measure = contract["measure_column"]
    deduction = contract.get("deduction_column")
    pipeline = contract["pipeline"]
    measure_tests = f"          - name: {measure}\n            tests: [not_null]\n"
    if deduction:
        measure_tests += f"          - name: {deduction}\n            tests: [not_null]\n"
    return f"""version: 2

sources:
  - name: finance
    tables:
      - name: {table}
        columns:
          - name: {status}
            tests:
              - accepted_values:
                  values: [{values}]
{measure_tests}
models:
  - name: {pipeline}
    tests:
      - revenue_reconciliation:   # metric phải khớp baseline trong tolerance
          tolerance: 0.001
"""


def generate_dbt_test(summary: dict, contract: dict[str, Any], txn_date: str,
                      conn: Optional[sqlite3.Connection] = None) -> dict[str, Any]:
    new_values = summary.get("enum_drift", {}).get("new_values", [])
    base_accepted = contract.get("accepted_values", {}).get(contract["status_column"], [])
    accepted = sorted(set(base_accepted) | set(new_values))

    # chứng minh test bắt được lỗi: FAIL với logic cũ ([]), PASS sau patch (new_values)
    before = run_validation(txn_date, [], contract, conn=conn)
    after = run_validation(txn_date, new_values, contract, conn=conn)
    verification = {
        "before_fix_status": before["validation_status"],
        "after_fix_status": after["validation_status"],
        "catches_bug": before["validation_status"] == "FAIL"
        and after["validation_status"] == "PASS",
    }

    return {
        "suggested_path": "proposed/schema.yml",
        "accepted_values": accepted,
        "yaml": _yaml(contract, accepted),
        "verification": verification,
    }
