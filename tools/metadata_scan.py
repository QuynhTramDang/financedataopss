"""metadata_scan — đọc schema/partition/known_values (cached profile, §13 metadata-first).

known_values là ảnh chụp trước đó (last_profiled_at) — dùng làm baseline cho enum_drift_check.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_CACHE = Path(__file__).resolve().parents[1] / "database" / "cached_profile.json"


def _load() -> dict[str, Any]:
    return json.loads(_CACHE.read_text(encoding="utf-8"))


def metadata_scan(table: str) -> dict[str, Any]:
    """Trả metadata của bảng: partition_key, columns, known_values, last_profiled_at."""
    profiles = _load()
    meta = profiles.get(table)
    if not meta:
        return {"table": table, "found": False}
    return {"table": table, "found": True, **meta}
