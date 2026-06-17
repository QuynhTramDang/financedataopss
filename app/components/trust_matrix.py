"""Render Trust Matrix + claim verification table."""

from __future__ import annotations

import streamlit as st

_ICON = {"High": "🟢", "Medium": "🟡", "Low": "🔴"}


def render_trust(trust_matrix: dict | None) -> None:
    if not trust_matrix:
        return
    st.subheader("Trust Matrix")
    for k, v in trust_matrix.items():
        st.markdown(f"{_ICON.get(v, '•')} **{k}**: {v}")


def render_claims(claims: list[dict] | None) -> None:
    if not claims:
        return
    st.subheader("Claim Verification")
    rows = [{"claim": c["claim"], "evidence": ", ".join(c.get("required_evidence", [])),
             "status": c["status"]} for c in claims]
    st.table(rows)
