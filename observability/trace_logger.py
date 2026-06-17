"""trace_logger — trace per-node (model/token/latency/cost) cho 1 investigation.

Concurrency-safe: events + trace_id giữ trong contextvar (mỗi investigation/thread một trace riêng,
KHÔNG đè nhau như list global cũ). Mỗi event gắn trace_id + seq + cost_usd. Router gọi record_llm()
mỗi LLM call; node decorator (graph.workflow) gom buffer rồi log_event(). new_state() gọi reset_trace().
"""

from __future__ import annotations

import contextvars
import uuid
from typing import Any

from .cost import cost_of

_node_calls: contextvars.ContextVar = contextvars.ContextVar("node_llm_calls", default=None)
_events: contextvars.ContextVar = contextvars.ContextVar("trace_events", default=None)
_trace_id: contextvars.ContextVar = contextvars.ContextVar("trace_id", default=None)


# ── per-node LLM buffer ──────────────────────────────────────
def start_node_buffer() -> None:
    _node_calls.set([])


def record_llm(route: str, provider: str, model: str,
               input_tokens: int, output_tokens: int) -> None:
    buf = _node_calls.get()
    if buf is not None:
        buf.append({"route": route, "provider": provider, "model": model,
                    "input_tokens": input_tokens, "output_tokens": output_tokens})


def pop_node_buffer() -> list[dict]:
    buf = _node_calls.get() or []
    _node_calls.set(None)
    return buf


# ── trace (per-investigation, contextvar) ────────────────────
def reset_trace(trace_id: str | None = None) -> str:
    """Bắt đầu trace mới (mỗi investigation 1 trace sạch). Trả trace_id."""
    tid = trace_id or f"trace-{uuid.uuid4().hex[:8]}"
    _events.set([])
    _trace_id.set(tid)
    return tid


def current_trace_id() -> str | None:
    return _trace_id.get()


def log_event(event: dict) -> None:
    ev: dict[str, Any] = dict(event)
    ev["trace_id"] = _trace_id.get()
    lst = _events.get()
    if lst is None:
        lst = []
        _events.set(lst)
    ev["seq"] = len(lst)
    ev["cost_usd"] = cost_of(ev.get("model"), ev.get("input_tokens", 0), ev.get("output_tokens", 0))
    lst.append(ev)


def get_trace() -> list[dict]:
    return list(_events.get() or [])
