# app_sections_master/platform_admin.py
"""
Platform header and summary metrics bar.

render_platform_header() is called once at the top of every platform
admin page render (injected by app_manager.py before the nav callable).

The three section callables are imported directly from their modules:
  platform_schools_section  →  _schools.render_schools_section
  platform_db_section       →  _db_ops.render_db_ops_section
  platform_audit_section    →  _audit.render_audit_section

Each is wired as a standalone sidebar nav item — same pattern as school sections.
"""

import streamlit as st
import logging

from database_master import get_master_db_info
from main_utils import inject_metric_css

logger = logging.getLogger(__name__)


def render_platform_header():
    """
    Renders the platform title + live 4-metric summary bar.
    Called by app_manager.py before every platform section render.
    """
    inject_metric_css()

    st.title("🌐 Platform Administration")
    st.caption(
        f"Logged in as **{st.session_state.get('username', 'platform_admin')}** "
        "· Platform Superadmin"
    )

    info = get_master_db_info()
    c1, c2, c3, c4, = st.columns(4)
    c1.metric("Schools",     info["schools_total"])
    c2.metric("Admins",      info["platform_admins"])
    c3.metric("master.db",   info["size"])
    c4.metric("Last Backup", info["last_backup"])

    # st.divider()