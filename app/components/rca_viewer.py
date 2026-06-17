"""Render RCA report markdown."""

from __future__ import annotations

import streamlit as st


def render_rca(rca_markdown: str | None) -> None:
    if not rca_markdown:
        return
    with st.expander("RCA Report (markdown)", expanded=True):
        st.markdown(rca_markdown)
