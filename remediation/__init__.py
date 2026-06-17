"""Fix-strategy registry: anomaly_type → chiến lược khắc phục (code_patch | operational)."""

from .strategies import build_remediation, get_strategy

__all__ = ["build_remediation", "get_strategy"]
