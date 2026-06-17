"""Render timeline của investigation trên Streamlit."""

from __future__ import annotations

import streamlit as st

_ICON = {
    "ok": "🟢",
    "skipped": "⚪",
    "escalated": "🟡",
    "blocked": "🔴",
}


def render_timeline(timeline: list[dict]) -> None:
    """Hiển thị danh sách bước đã chạy (mỗi entry: node/status/note/model)."""
    st.subheader("Workflow timeline")
    if not timeline:
        st.caption("Chưa có bước nào.")
        return
    for i, entry in enumerate(timeline, start=1):
        icon = _ICON.get(entry.get("status", "ok"), "•")
        node = entry.get("node", "?")
        note = entry.get("note", "")
        model = entry.get("model")
        lat = entry.get("latency_ms")
        suffix = f" · `{model}`" if model else ""
        if lat is not None:
            suffix += f" · {lat}ms"
        st.markdown(f"{i}. {icon} **{node}**{suffix} — {note}")
