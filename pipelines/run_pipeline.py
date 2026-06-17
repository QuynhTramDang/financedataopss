"""run_pipeline — materialize các tầng stg → ods → dtm từ bảng nguồn (CREATE TABLE AS).

Mô phỏng một dbt run nhỏ: mỗi "model" là một file SELECT; runner DROP + CREATE TABLE AS theo
đúng thứ tự phụ thuộc. Tool diagnostic/validation có thể query các bảng tầng này như data thật.

    from pipelines.run_pipeline import build_layers
    build_layers(conn)        # sau khi seed bảng nguồn
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

_MODELS = Path(__file__).resolve().parent / "models"

# (tên bảng materialize, đường dẫn file SQL) — theo thứ tự phụ thuộc stg → ods → dtm.
LAYERS: list[tuple[str, Path]] = [
    ("stg_payment", _MODELS / "staging" / "stg_payment.sql"),
    ("stg_order", _MODELS / "staging" / "stg_order.sql"),
    ("ods_payment_enriched", _MODELS / "ods" / "ods_payment_enriched.sql"),
    ("dtm_revenue_daily", _MODELS / "finance" / "dtm_revenue_daily.sql"),
]


def _select_body(path: Path) -> str:
    """Đọc file SQL, bỏ dấu ';' cuối để nhúng vào CREATE TABLE AS (một statement)."""
    return path.read_text(encoding="utf-8").strip().rstrip(";")


def build_layers(conn: sqlite3.Connection) -> list[str]:
    """Materialize tuần tự các tầng. Trả danh sách bảng đã tạo."""
    built: list[str] = []
    for name, path in LAYERS:
        body = _select_body(path)
        conn.execute(f"DROP TABLE IF EXISTS {name}")
        conn.execute(f"CREATE TABLE {name} AS\n{body}")
        built.append(name)
    conn.commit()
    return built


def main(db_path: str | None = None) -> None:
    from database.connection import get_connection

    conn = get_connection(db_path)
    try:
        built = build_layers(conn)
        for name in built:
            n = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            print(f"  materialized {name}: {n} rows")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
