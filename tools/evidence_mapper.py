"""evidence_mapper — map mỗi claim với source evidence cụ thể (cho RCA, §14.3)."""

from __future__ import annotations

from typing import Any


def map_evidence(claims: list[dict]) -> list[dict[str, Any]]:
    """Trả bảng claim → evidence: [{claim, source, value, status}]."""
    table = []
    for c in claims:
        table.append({
            "claim": c["claim"],
            "source": ", ".join(c.get("required_evidence", [])),
            "value": c.get("evidence_value"),
            "status": c["status"],
        })
    return table
