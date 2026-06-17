"""Kết nối SQLite + helper query.

Nguyên tắc (§13): tool/database đọc data, LLM chỉ nhận summary. Module này là lớp truy cập DB
dùng chung cho diagnostic tools, validation engine và seed script.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Optional

import yaml

_ROOT = Path(__file__).resolve().parents[1]
_CONFIG_PATH = Path(__file__).with_name("db_config.yaml")
_PIPELINE_SQL = _ROOT / "pipelines" / "models" / "finance" / "revenue_daily.sql"
_FALLBACK_DB_PATH: Optional[str] = None


def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def get_db_path() -> str:
    """Đường dẫn DB: env DATABASE_PATH > db_config.yaml. Trả absolute path."""
    env = os.getenv("DATABASE_PATH")
    rel = env or _load_config()["database"]["path"]
    p = Path(rel)
    return str(p if p.is_absolute() else _ROOT / p)


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Mở connection. Row factory = sqlite3.Row để truy cập theo tên cột."""
    global _FALLBACK_DB_PATH
    path = db_path or get_db_path()
    if db_path is None and _FALLBACK_DB_PATH:
        path = _FALLBACK_DB_PATH
    elif db_path is None and not os.getenv("DATABASE_PATH") and path != ":memory:":
        db_file = Path(path)
        if not db_file.exists() or Path(f"{path}-journal").exists():
            _FALLBACK_DB_PATH = str(Path(tempfile.gettempdir()) / "finance_dataops_demo.db")
            path = _FALLBACK_DB_PATH
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    def _open(p: str) -> sqlite3.Connection:
        c = sqlite3.connect(p)
        c.row_factory = sqlite3.Row
        return c

    conn = _open(path)
    if path != ":memory:" and db_path is None and not os.getenv("DATABASE_PATH"):
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS __connection_probe (ok INTEGER)")
            conn.execute("DROP TABLE IF EXISTS __connection_probe")
            conn.commit()
        except sqlite3.OperationalError:
            conn.close()
            try:
                Path(path).unlink(missing_ok=True)
                Path(f"{path}-journal").unlink(missing_ok=True)
            except OSError:
                pass
            _FALLBACK_DB_PATH = str(Path(tempfile.gettempdir()) / "finance_dataops_demo.db")
            conn = _open(_FALLBACK_DB_PATH)
    return conn


def run_query(sql: str, params: Optional[dict] = None,
              conn: Optional[sqlite3.Connection] = None,
              db_path: Optional[str] = None) -> list[dict[str, Any]]:
    """Chạy SELECT, trả về list[dict]. Nếu không truyền conn thì tự mở/đóng."""
    own = conn is None
    conn = conn or get_connection(db_path)
    try:
        cur = conn.execute(sql, params or {})
        return [dict(row) for row in cur.fetchall()]
    finally:
        if own:
            conn.close()


def read_pipeline_sql() -> str:
    """Đọc nội dung revenue_daily.sql (legacy default — back-compat cho code_search/validation)."""
    return _PIPELINE_SQL.read_text(encoding="utf-8")


def read_sql_file(repo_path: str) -> str:
    """Đọc một file SQL theo repo-relative path (vd 'pipelines/models/ods/ods_payment_enriched.sql').

    Dùng cho code_search đa-file theo lineage (metric → dtm → ods → stg).
    """
    p = Path(repo_path)
    full = p if p.is_absolute() else _ROOT / p
    return full.read_text(encoding="utf-8")


def init_schema(conn: sqlite3.Connection) -> None:
    """Tạo bảng từ schema.sql."""
    schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    conn.executescript(schema)
    conn.commit()
