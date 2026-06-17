"""Render patch + review + validation result."""

from __future__ import annotations

import streamlit as st


def render_patch(patch: dict | None, review: dict | None) -> None:
    if not patch:
        return
    st.subheader("Safe Patch")
    st.caption(f"{patch.get('target_file')} · risk={patch.get('risk_level')} · "
               f"approval={'required' if patch.get('requires_approval') else 'no'}")
    st.markdown("**Old**")
    st.code(patch.get("old_code", ""), language="sql")
    st.markdown("**New**")
    st.code(patch.get("new_code", ""), language="sql")
    st.caption(f"Reason: {patch.get('reason')}")
    if review:
        st.markdown(f"**Review:** {review.get('comment')}")
        st.caption("Suggested tests: " + ", ".join(review.get("suggested_tests", [])))


def render_validation(validation: dict | None) -> None:
    if not validation:
        return
    st.subheader(f"Validation — {validation.get('validation_status')} "
                 f"({validation.get('passed')}/{validation.get('total')})")
    for t in validation.get("tests", []):
        icon = "🟢" if t["status"] == "PASS" else "🔴"
        extra = ""
        if t["name"] == "revenue_reconciliation_check":
            extra = f" — before {t['before_fix_diff']*100:.2f}% → after {t['after_fix_diff']*100:.2f}%"
        st.markdown(f"{icon} {t['name']}{extra}")
