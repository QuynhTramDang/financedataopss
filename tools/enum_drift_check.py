"""enum_drift_check — phát hiện value enum mới so với baseline known_values (§11.2)."""

from __future__ import annotations

from typing import Any


def enum_drift_check(actual_values: list[str], known_values: list[str]) -> dict[str, Any]:
    """Trả {known_values, actual_values, new_values, has_drift}."""
    known = set(known_values or [])
    actual = set(actual_values or [])
    new_values = sorted(actual - known)
    return {
        "known_values": sorted(known),
        "actual_values": sorted(actual),
        "new_values": new_values,
        "has_drift": bool(new_values),
    }
