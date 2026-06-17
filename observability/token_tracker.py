"""token_tracker — tổng hợp token từ trace + kiểm tra budget (§27)."""

from __future__ import annotations

from typing import Any

MAX_INPUT_TOKENS = 10_000   # target §27: 5k–10k input tokens / investigation


def totals(trace: list[dict]) -> dict[str, Any]:
    return {
        "input_tokens": sum(e.get("input_tokens", 0) for e in trace),
        "output_tokens": sum(e.get("output_tokens", 0) for e in trace),
        "llm_nodes": sum(1 for e in trace if e.get("model")),
        "cost_usd": round(sum(e.get("cost_usd", 0.0) for e in trace), 6),
    }


def within_budget(trace: list[dict], max_input: int = MAX_INPUT_TOKENS) -> bool:
    return totals(trace)["input_tokens"] <= max_input


def per_node(trace: list[dict]) -> list[dict[str, Any]]:
    return [{"node": e["node"], "model": e.get("model"),
             "input_tokens": e.get("input_tokens", 0),
             "output_tokens": e.get("output_tokens", 0),
             "latency_ms": e.get("latency_ms")} for e in trace]
