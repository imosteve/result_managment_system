# app_sections_master/_audit.py
"""
Audit Log section.

Features:
  - Filter by school code and/or action keyword
  - Configurable row limit (50 / 100 / 200 / 500)
  - Action frequency summary metrics for the current result set
  - CSV download of current view
"""

import streamlit as st
import pandas as pd
import logging
from datetime import datetime

from master_database import get_audit_log, get_audit_log_by_school

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
# Entry point
# ═════════════════════════════════════════════════════════════════════════════

def render_audit_section():
    st.caption("Immutable record of all platform-level actions — append-only.")

    # ── Filter controls ───────────────────────────────────────────────────
    fc1, fc2, fc3 = st.columns([2, 2, 1])

    with fc1:
        school_filter = st.text_input(
            "Filter by school code",
            placeholder="suis    (blank = all schools)",
            key="audit_school_filter",
        )
    with fc2:
        action_filter = st.text_input(
            "Filter by action keyword",
            placeholder="REGISTERED · BACKUP · ADMIN_CREATED…",
            key="audit_action_filter",
        )
    with fc3:
        limit = st.selectbox(
            "Show rows",
            [50, 100, 200, 500],
            index=1,
            key="audit_limit",
        )

    # ── Fetch ─────────────────────────────────────────────────────────────
    school_code = school_filter.strip().lower()
    action_kw   = action_filter.strip()

    if school_code:
        entries = get_audit_log_by_school(school_code, limit=limit)
        # apply action keyword client-side
        if action_kw:
            entries = [e for e in entries
                       if action_kw.upper() in e["action"].upper()]
    else:
        entries = get_audit_log(
            limit=limit,
            action_filter=action_kw or None,
        )

    if not entries:
        st.info("No audit entries match your filters.")
        return

    # ── Action frequency summary bar ──────────────────────────────────────
    action_counts: dict[str, int] = {}
    for e in entries:
        action_counts[e["action"]] = action_counts.get(e["action"], 0) + 1

    top = sorted(action_counts.items(), key=lambda x: x[1], reverse=True)[:4]
    if top:
        cols = st.columns(len(top))
        for i, (action, count) in enumerate(top):
            cols[i].metric(action.replace("_", " ").title(), count)

    st.divider()

    # ── Results table ─────────────────────────────────────────────────────
    df = pd.DataFrame(entries)[[
        "created_at", "school_code", "action", "performed_by", "details"
    ]]
    df.columns = ["Timestamp", "School", "Action", "Performed By", "Details"]

    table_height = len(df)-5 if len(df) > 40 else len(df)-1 if len(df) > 10 else len(df)+1

    st.dataframe(df, width="stretch", hide_index=True, height=40*table_height)

    # ── Footer: count + CSV export ────────────────────────────────────────
    foot_left, foot_right = st.columns([3, 1])
    with foot_left:
        st.caption(f"Showing **{len(entries)}** entries.")
    with foot_right:
        csv = df.to_csv(index=False)
        st.download_button(
            label="⬇️ Export CSV",
            data=csv,
            file_name=f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            width="stretch",
        )
