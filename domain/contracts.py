"""Metric contracts — domain knowledge tách khỏi code (enterprise pattern).

Code = thuật toán (metric *kind*); config = instance (bảng/cột/giá trị cụ thể của từng metric).
Tool đọc contract thay vì nhúng 'refund_status'/'payment_txn'. Thiếu contract/field/scope bắt buộc
→ raise (FAIL-LOUD), KHÔNG đoán mặc định revenue.

Nguồn: memory/metric_memory.json (contract) + database/cached_profile.json (metadata bảng).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_METRIC_MEMORY = _ROOT / "memory" / "metric_memory.json"
_CACHED_PROFILE = _ROOT / "database" / "cached_profile.json"

# field bắt buộc của một metric contract
_REQUIRED = ("partition_key", "fact_table", "measure_column", "status_column", "pipeline")
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ContractError(ValueError):
    """Thiếu/sai metric contract — fail-loud, không fallback."""


class ScopeError(ValueError):
    """Thiếu thông tin scope (metric/date) để điều tra — fail-loud."""


def safe_ident(name: str) -> str:
    """Chỉ cho phép identifier hợp lệ trước khi nội suy vào SQL (chống injection từ config)."""
    if not name or not _IDENT.match(name):
        raise ContractError(f"Identifier không hợp lệ để dùng trong SQL: {name!r}")
    return name


def _load_contracts() -> list[dict[str, Any]]:
    try:
        return json.loads(_METRIC_MEMORY.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ContractError(f"Không đọc được metric_memory.json: {exc}") from exc


def list_metrics() -> list[str]:
    return [c["metric"] for c in _load_contracts() if c.get("metric")]


def metric_terms() -> dict[str, list[str]]:
    """{metric: [tên + biến thể + aliases]} — cho intent classifier nhận diện metric/finance."""
    out: dict[str, list[str]] = {}
    for c in _load_contracts():
        m = c.get("metric")
        if not m:
            continue
        out[m] = [m, m.replace("_", " "), *c.get("aliases", [])]
    return out


def get_contract(metric: str | None) -> dict[str, Any]:
    """Trả contract của metric. Raise ContractError nếu thiếu metric/contract/field bắt buộc."""
    if not metric:
        raise ContractError("Thiếu 'metric' — không thể suy scope/contract (fail-loud).")
    for rec in _load_contracts():
        if rec.get("metric") == metric:
            missing = [f for f in _REQUIRED if not rec.get(f)]
            if missing:
                raise ContractError(
                    f"Metric contract '{metric}' thiếu field bắt buộc: {missing}")
            return rec
    raise ContractError(
        f"Không có metric contract cho '{metric}' trong metric_memory.json (fail-loud).")


def table_metadata(table: str) -> dict[str, Any]:
    try:
        profiles = json.loads(_CACHED_PROFILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ContractError(f"Không đọc được cached_profile.json: {exc}") from exc
    meta = profiles.get(table)
    if not meta:
        raise ContractError(f"Không có metadata cho bảng '{table}' (fail-loud).")
    return meta


def partition_key_of(table: str) -> str:
    pk = table_metadata(table).get("partition_key")
    if not pk:
        raise ContractError(f"Bảng '{table}' không khai partition_key trong metadata.")
    return safe_ident(pk)


def partitioned_tables() -> dict[str, str]:
    """{table: partition_key} cho mọi bảng có khai partition (cho sql_policy)."""
    try:
        profiles = json.loads(_CACHED_PROFILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {t: m["partition_key"] for t, m in profiles.items() if m.get("partition_key")}


def resolve_scope(state: dict) -> dict[str, Any]:
    """Suy scope điều tra TỪ contract + state. Fail-loud nếu thiếu metric/date.

    Thứ tự ưu tiên cho từng field: state override → contract.
    """
    contract = get_contract(state.get("metric"))
    date = state.get("date")
    if not date:
        raise ScopeError("Thiếu 'date'/partition_value trong state — không thể điều tra (fail-loud).")
    table = state.get("table") or contract["fact_table"]
    return {
        "metric": state.get("metric"),
        "contract": contract,
        "txn_date": date,
        "partition_key": partition_key_of(table),
        "table": table,
        "enum_field": state.get("enum_field") or contract["status_column"],
        "null_column": state.get("null_column") or contract["measure_column"],
        "pipeline": state.get("pipeline") or contract["pipeline"],
    }
