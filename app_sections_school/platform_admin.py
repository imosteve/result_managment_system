# app_sections/platform_admin.py  — FINAL VERSION
"""
Platform-level admin panel.
Only accessible to accounts with role = 'superadmin' on the MASTER system
(i.e. the person who operates the hosting platform, not a school admin).

Tabs:
  1. Registered Schools — view all, activate/deactivate
  2. Register New School — form to add a school
  3. Audit Log — immutable history of platform actions
"""

import streamlit as st
import logging
import time
from master_database import (
    register_school,
    get_all_schools,
    update_school_status,
    get_master_connection,
)
from main_utils import inject_login_css, inject_metric_css


logger = logging.getLogger(__name__)


def platform_admin():
    """Platform admin panel — manage all schools"""
    st.title("🌐 Platform Administration")
    st.caption("Manage all schools registered on this platform.")

    inject_login_css("templates/tabs_styles.css")

    tab1, tab2, tab3 = st.tabs([
        "🏫 Registered Schools",
        "➕ Register New School",
        "📋 Audit Log",
    ])

    with tab1:
        _render_schools_list()

    with tab2:
        _render_register_form()

    with tab3:
        _render_audit_log()


# ─────────────────────────────────────────────
# Tab 1 — Schools list
# ─────────────────────────────────────────────

def _render_schools_list():
    st.subheader("All Registered Schools")

    schools = get_all_schools()

    if not schools:
        st.info("No schools registered yet. Use the 'Register New School' tab.")
        return

    # Summary metrics
    total    = len(schools)
    active   = sum(1 for s in schools if s["status"] == "active")
    inactive = total - active

    inject_metric_css()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Schools", total)
    col2.metric("Active",   active,   delta=None)
    col3.metric("Inactive", inactive, delta=None)

    st.divider()

    for school in schools:
        is_active   = school["status"] == "active"
        status_icon = "🟢" if is_active else "🔴"
        status_label = "Active" if is_active else "Inactive"

        with st.expander(
            f"{status_icon} **{school['school_name']}**  "
            f"— `{school['school_code']}`  "
            f"· {status_label}"
        ):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown(f"**Status:** {status_icon} {status_label}")
                st.markdown(f"**Email Domain:** `{school['email_domain']}`")
                st.markdown(f"**Database File:** `data/schools/{school['database_name']}`")
                st.markdown(f"**Contact:** {school.get('contact_email') or '—'}")

            with col2:
                st.markdown(f"**Address:** {school.get('address') or '—'}")
                st.markdown(f"**Phone:** {school.get('phone') or '—'}")
                st.markdown(f"**Registered:** {school['created_at']}")
                st.markdown(f"**Last Updated:** {school.get('updated_at') or '—'}")

            st.divider()

            # Status toggle
            if is_active:
                st.warning(
                    "⚠️ Deactivating this school will immediately prevent all "
                    "its users from logging in. The database is preserved."
                )
                if st.button(
                    "🔴 Deactivate School",
                    key=f"deactivate_{school['school_code']}",
                    type="secondary",
                ):
                    if update_school_status(
                        school["school_code"], "inactive",
                        performed_by=st.session_state.get("username", "platform_admin")
                    ):
                        st.error(
                            f"School **{school['school_name']}** has been deactivated."
                        )
                        st.rerun()
                    else:
                        st.error("Failed to update status. Check logs.")
            else:
                st.info(
                    "ℹ️ Activating this school will immediately restore "
                    "login access for all its users."
                )
                if st.button(
                    "🟢 Activate School",
                    key=f"activate_{school['school_code']}",
                    type="primary",
                ):
                    if update_school_status(
                        school["school_code"], "active",
                        performed_by=st.session_state.get("username", "platform_admin")
                    ):
                        st.success(
                            f"School **{school['school_name']}** has been activated."
                        )
                        st.rerun()
                    else:
                        st.error("Failed to update status. Check logs.")


# ─────────────────────────────────────────────
# Tab 2 — Register new school
# ─────────────────────────────────────────────

def _render_register_form():
    st.subheader("Register a New School")
    """
        "Each school gets its own isolated database, created once at registration. "
        "Staff log in using their school email — the domain is used to identify "
        "which school database to authenticate against."
    """

    with st.form("register_school_form", clear_on_submit=True):
        school_name   = st.text_input(
            "School Name *",
            placeholder="Greenfield Academy"
        )
        school_code   = st.text_input(
            "School Code *",
            placeholder="greenfield",
            help="Short unique identifier. Lowercase, no spaces. "
                 "Becomes the database filename: greenfield → greenfield.db"
        )
        email_domain  = st.text_input(
            "Staff Email Domain *",
            placeholder="greenfield.edu",
            help="Domain part only — e.g. 'greenfield.edu', not 'admin@greenfield.edu'"
        )
        contact_email = st.text_input(
            "Platform Contact Email",
            placeholder="contact-us@greenfield.edu"
        )
        phone = st.text_input("Phone Number")
        address = st.text_area("School Address", height=80)

        submitted = st.form_submit_button("✅ Register School", type="primary")

    if submitted:
        # Validation
        errors = []
        if not school_name.strip():
            errors.append("School Name is required.")
        if not school_code.strip():
            errors.append("School Code is required.")
        elif " " in school_code.strip():
            errors.append("School Code cannot contain spaces.")
        if not email_domain.strip():
            errors.append("Email Domain is required.")
        elif "@" in email_domain.strip():
            errors.append(
                "Enter only the domain part, e.g. 'greenfield.edu' "
                "— not 'admin@greenfield.edu'."
            )

        if errors:
            for err in errors:
                st.error(f"⚠️ {err}")
            return

        try:
            result = register_school(
                school_name=school_name.strip(),
                school_code=school_code.strip(),
                email_domain=email_domain.strip(),
                contact_email=contact_email.strip(),
                address=address.strip(),
                phone=phone.strip(),
                performed_by=st.session_state.get("username", "platform_admin"),
            )
            st.success(
                f"✅ **{school_name}** registered successfully!\n\n"
                f"- School code: `{result['school_code']}`\n"
                f"- Database: `{result['db_name']}`\n\n"
                f"**Default credentials** (change immediately after first login):\n"
                f"- `superadmin@{email_domain}` / `superadmin`\n"
                f"- `admin@{email_domain}` / `admin`"
            )
            time.sleep(1)
            st.rerun()
        except ValueError as e:
            st.error(f"❌ {e}")
        except FileExistsError as e:
            st.error(f"❌ {e}")
        except Exception as e:
            logger.error(f"Unexpected error registering school: {e}")
            st.error("An unexpected error occurred. Please check the application logs.")


# ─────────────────────────────────────────────
# Tab 3 — Audit log
# ─────────────────────────────────────────────

def _render_audit_log():
    st.subheader("Platform Audit Log")
    st.caption("Immutable record of all platform-level actions.")

    try:
        conn = get_master_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT school_code, action, performed_by, details, created_at
            FROM   school_audit_log
            ORDER  BY created_at DESC
            LIMIT  200
        """)
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            st.info("No audit events recorded yet.")
            return

        import pandas as pd
        df = pd.DataFrame(
            [dict(r) for r in rows],
            columns=["school_code", "action", "performed_by", "details", "created_at"]
        )
        df.columns = ["School Code", "Action", "Performed By", "Details", "Timestamp"]
        st.dataframe(df, use_container_width=True, hide_index=True)

    except Exception as e:
        logger.error(f"Error loading audit log: {e}")
        st.error("Could not load audit log. Check application logs.")
