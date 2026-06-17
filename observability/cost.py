"""cost — quy đổi token → USD theo bảng giá model (§28). Model không biết giá → 0.0 (không đoán)."""

from __future__ import annotations

# USD / 1M token (input, output) — chỉnh theo bảng giá thật khi cần.
_PRICES: dict[str, tuple[float, float]] = {
    "claude-opus-4-8": (15.0, 75.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
}


def cost_of(model: str | None, input_tokens: int, output_tokens: int) -> float:
    price = _PRICES.get(model or "")
    if not price:
        return 0.0
    return round(input_tokens / 1e6 * price[0] + output_tokens / 1e6 * price[1], 6)
