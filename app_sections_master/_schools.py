# app_sections_master/_schools.py
"""
Schools section — 3 sub-tabs:
  1. All Schools      — searchable list with activate/deactivate, edit info,
                        per-school audit preview, delete with confirmation
  2. Register School  — validated registration form
  3. Platform Admins  — full CRUD: add, change password, change email, delete
"""

import streamlit as st
import pandas as pd
import logging
import time
from main_utils import inject_login_css

from database_master import (
    get_all_schools,
    register_school,
    update_school_status,
    update_school_info,
    delete_school,
    get_audit_log_by_school,
    get_all_platform_admins,
    create_platform_admin,
    update_platform_admin_password,
    update_platform_admin_email,
    delete_platform_admin,
)

logger = logging.getLogger(__name__)


def _actor() -> str:
    return st.session_state.get("username", "platform_admin")


# ═════════════════════════════════════════════════════════════════════════════
# Entry point
# ═════════════════════════════════════════════════════════════════════════════

def render_schools_section():

    inject_login_css("templates/tabs_styles.css")

    sub1, sub2, sub3 = st.tabs([
        "🏫 All Schools",
        "➕ Register School",
        "👤 Platform Admins",
    ])
    with sub1:
        _all_schools()
    with sub2:
        _register_school()
    with sub3:
        _platform_admins()


# ═════════════════════════════════════════════════════════════════════════════
# Sub-tab 1  ·  All Schools
# ═════════════════════════════════════════════════════════════════════════════

def _all_schools():
    schools = get_all_schools()

    if not schools:
        st.info(
            "No schools registered yet.  "
            "Use the **Register School** tab to add one."
        )
        return

    # ── Summary counts ────────────────────────────────────────────────────
    total    = len(schools)
    active   = sum(1 for s in schools if s["status"] == "active")
    inactive = total - active

    mc1, mc2, mc3 = st.columns(3)
    mc1.metric("Total", total)
    mc2.metric("🟢 Active",   active)
    mc3.metric("🔴 Inactive", inactive)

    st.divider()

    # ── Search / status filter ────────────────────────────────────────────
    fc1, fc2 = st.columns([4, 1])
    with fc1:
        q = st.text_input(
            "Search schools",
            placeholder="Name, code or email domain…",
            label_visibility="collapsed",
        )
    with fc2:
        status_f = st.selectbox(
            "Status filter",
            ["All", "Active", "Inactive"],
            label_visibility="collapsed",
        )

    visible = schools
    if q:
        ql = q.lower()
        visible = [s for s in visible
                   if ql in s["school_name"].lower()
                   or ql in s["school_code"].lower()
                   or ql in s["email_domain"].lower()]
    if status_f != "All":
        visible = [s for s in visible if s["status"] == status_f.lower()]

    if not visible:
        st.warning("No schools match your search.")
        return

    # ── One card per school ───────────────────────────────────────────────
    for school in visible:
        _school_card(school)


def _school_card(school: dict):
    code         = school["school_code"]
    is_active    = school["status"] == "active"
    icon         = "🟢" if is_active else "🔴"
    status_label = "Active" if is_active else "Inactive"

    with st.expander(
        f"{icon} **{school['school_name']}** — `{code}` · {status_label}",
        expanded=False,
    ):
        # ── Info grid ─────────────────────────────────────────────────────
        ic1, ic2 = st.columns(2)
        with ic1:
            st.markdown(f"**Status:** {icon} {status_label}")
            st.markdown(f"**Email Domain:** `{school['email_domain']}`")
            st.markdown(f"**Database:** `data/schools/{school['database_name']}`")
            st.markdown(f"**Contact:** {school.get('contact_email') or '—'}")
        with ic2:
            st.markdown(f"**Phone:** {school.get('phone') or '—'}")
            st.markdown(f"**Address:** {school.get('address') or '—'}")
            st.markdown(f"**Registered:** {school['created_at']}")
            st.markdown(f"**Updated:** {school.get('updated_at') or '—'}")


        # ── Action buttons ────────────────────────────────────────────────
        btn1, btn2, btn3, btn4 = st.columns(4)

        with btn1:
            if is_active:
                if st.button("🔴 Deactivate", key=f"deact_{code}",
                             use_container_width=True):
                    st.session_state[f"confirm_deact_{code}"] = True
            else:
                if st.button("🟢 Activate", key=f"act_{code}",
                             type="primary", use_container_width=True):
                    if update_school_status(code, "active", _actor()):
                        st.success(f"✅ **{school['school_name']}** activated.")
                        time.sleep(0.5); st.rerun()
                    else:
                        st.error("Failed — check logs.")

        with btn2:
            if st.button("✏️ Edit Info", key=f"edit_btn_{code}",
                         use_container_width=True):
                key = f"editing_{code}"
                st.session_state[key] = not st.session_state.get(key, False)

        with btn3:
            if st.button("📋 Audit", key=f"audit_btn_{code}",
                         use_container_width=True):
                key = f"show_audit_{code}"
                st.session_state[key] = not st.session_state.get(key, False)

        with btn4:
            if st.button("🗑️ Delete", key=f"del_btn_{code}",
                         use_container_width=True):
                st.session_state[f"confirm_del_{code}"] = True

        # ── Deactivate confirmation ───────────────────────────────────────
        if st.session_state.get(f"confirm_deact_{code}"):
            st.warning(
                f"⚠️ Deactivating **{school['school_name']}** will immediately "
                "block all its users from logging in. The database is preserved."
            )
            dc1, dc2 = st.columns(2)
            with dc1:
                if st.button("✅ Yes, Deactivate", key=f"yes_deact_{code}",
                             type="primary", use_container_width=True):
                    if update_school_status(code, "inactive", _actor()):
                        st.session_state.pop(f"confirm_deact_{code}", None)
                        st.error(f"🔴 **{school['school_name']}** deactivated.")
                        time.sleep(0.5); st.rerun()
                    else:
                        st.error("Failed — check logs.")
            with dc2:
                if st.button("Cancel", key=f"no_deact_{code}",
                             use_container_width=True):
                    st.session_state.pop(f"confirm_deact_{code}", None)
                    st.rerun()

        # ── Edit info form ────────────────────────────────────────────────
        if st.session_state.get(f"editing_{code}"):
            st.markdown("##### ✏️ Edit School Info")
            st.caption("School Code and Email Domain cannot be changed here.")
            with st.form(f"edit_form_{code}"):
                ef1, ef2 = st.columns(2)
                with ef1:
                    new_name    = st.text_input("School Name",
                                                value=school.get("school_name", ""))
                    new_contact = st.text_input("Contact Email",
                                                value=school.get("contact_email") or "")
                with ef2:
                    new_phone   = st.text_input("Phone",
                                                value=school.get("phone") or "")
                    new_address = st.text_area("Address",
                                               value=school.get("address") or "",
                                               height=68)
                sc1, sc2 = st.columns(2)
                with sc1:
                    save   = st.form_submit_button("💾 Save", type="primary",
                                                   use_container_width=True)
                with sc2:
                    cancel = st.form_submit_button("Cancel", use_container_width=True)

            if save:
                ok = update_school_info(
                    school_code=code,
                    school_name=new_name.strip() or None,
                    contact_email=new_contact.strip() or None,
                    phone=new_phone.strip() or None,
                    address=new_address.strip() or None,
                    performed_by=_actor(),
                )
                if ok:
                    st.session_state.pop(f"editing_{code}", None)
                    st.success("✅ Updated.")
                    time.sleep(0.4); st.rerun()
                else:
                    st.error("Update failed — check logs.")
            if cancel:
                st.session_state.pop(f"editing_{code}", None)
                st.rerun()

        # ── Per-school audit preview ──────────────────────────────────────
        if st.session_state.get(f"show_audit_{code}"):
            st.markdown("##### 📋 Recent Activity")
            entries = get_audit_log_by_school(code, limit=15)
            if entries:
                df = pd.DataFrame(entries)[
                    ["created_at", "action", "performed_by", "details"]
                ]
                df.columns = ["Timestamp", "Action", "By", "Details"]
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No audit entries for this school yet.")

        # ── Delete confirmation ───────────────────────────────────────────
        if st.session_state.get(f"confirm_del_{code}"):
            st.error(
                f"🚨 **Delete {school['school_name']}** from the platform registry?"
            )
            also_del = st.checkbox(
                "⚠️ Also permanently erase the school's database file "
                "(irreversible — all student data will be lost)",
                key=f"also_del_{code}",
            )
            dd1, dd2 = st.columns([2, 1])
            with dd1:
                typed = st.text_input(
                    f"Type `{code}` to confirm",
                    placeholder=code,
                    key=f"del_confirm_{code}",
                )
            with dd2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🗑️ Delete", key=f"yes_del_{code}",
                             type="primary", use_container_width=True):
                    if typed.strip() == code:
                        if delete_school(code, delete_db_file=also_del,
                                         performed_by=_actor()):
                            st.session_state.pop(f"confirm_del_{code}", None)
                            st.success(f"✅ {school['school_name']} deleted.")
                            time.sleep(0.8); st.rerun()
                        else:
                            st.error("Delete failed — check logs.")
                    else:
                        st.error(f"Code does not match. Type exactly: `{code}`")
            if st.button("Cancel deletion", key=f"no_del_{code}"):
                st.session_state.pop(f"confirm_del_{code}", None)
                st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# Sub-tab 2  ·  Register School
# ═════════════════════════════════════════════════════════════════════════════

def _register_school():
    st.markdown(
        "Each school gets an **isolated SQLite database** created at registration. "
        "Staff log in with their school email — the domain automatically routes "
        "the login to the correct school database."
    )

    with st.form("register_school_form", clear_on_submit=True):
        rc1, rc2 = st.columns(2)
        with rc1:
            school_name   = st.text_input("School Name *",
                                          placeholder="SUIS International School")
            email_domain  = st.text_input(
                "Staff Email Domain *", placeholder="suis.edu.ng",
                help="Domain only — e.g. 'suis.edu.ng', NOT 'admin@suis.edu.ng'",
            )
            contact_email = st.text_input("Contact Email",
                                          placeholder="info@suis.edu.ng")
        with rc2:
            school_code = st.text_input(
                "School Code *", placeholder="suis",
                help="Lowercase, no spaces. Becomes the DB filename: suis → suis.db",
            )
            phone   = st.text_input("Phone Number")
            address = st.text_area("Address *", height=82)

        submitted = st.form_submit_button(
            "✅ Register School", type="primary", use_container_width=True
        )

    if submitted:
        errors = []
        if not school_name.strip():
            errors.append("School Name is required.")
        if not school_code.strip():
            errors.append("School Code is required.")
        if not address.strip():
            errors.append("Address is required.")
        elif " " in school_code.strip():
            errors.append("School Code cannot contain spaces.")
        if not email_domain.strip():
            errors.append("Email Domain is required.")
        elif "@" in email_domain.strip():
            errors.append("Enter the domain only — e.g. 'suis.edu.ng'.")

        if errors:
            for e in errors:
                st.error(f"⚠️ {e}")
            return

        try:
            result = register_school(
                school_name=school_name.strip(),
                school_code=school_code.strip(),
                email_domain=email_domain.strip(),
                contact_email=contact_email.strip(),
                address=address.strip(),
                phone=phone.strip(),
                performed_by=_actor(),
            )
            st.success(
                f"✅ **{school_name}** registered.\n\n"
                f"**Code:** `{result['school_code']}`  \n"
                f"**Database:** `data/schools/{result['db_name']}`\n\n"
                "**Default credentials** (change immediately after first login):\n"
                f"- `superadmin@{email_domain}` / `superadmin`\n"
                f"- `admin@{email_domain}` / `admin`"
            )
            time.sleep(1); st.rerun()
        except ValueError as e:
            st.error(f"❌ {e}")
        except FileExistsError as e:
            st.error(f"❌ {e}")
        except Exception as e:
            logger.error(f"register_school unexpected error: {e}")
            st.error("Unexpected error — check application logs.")


# ═════════════════════════════════════════════════════════════════════════════
# Sub-tab 3  ·  Platform Admins
# ═════════════════════════════════════════════════════════════════════════════

def _platform_admins():
    st.markdown("### Platform admins")

    admins      = get_all_platform_admins()
    my_username = st.session_state.get("username")

    # ── Current admins table ──────────────────────────────────────────────
    if admins:
        df = pd.DataFrame(admins)[["id", "username", "email", "role", "password", "created_at"]]
        df.columns = ["ID", "Username", "Email", "Role", "Password", "Created"]
        st.dataframe(df, width="stretch", hide_index=True)
    else:
        st.warning("⚠️ No platform admins found — this should never happen.")

    st.divider()

    # ── Operations — nested sub-tabs ─────────────────────────────────────
    op1, op2, op3, op4 = st.tabs([
        "➕ Add Admin",
        "🔑 Change Password",
        "📧 Change Email",
        "🗑️ Remove Admin",
    ])

    # ── Add ───────────────────────────────────────────────────────────────
    with op1:
        with st.form("add_admin_form"):
            a1, a2, a3 = st.columns(3)
            with a1:
                new_uname = st.text_input("Username *")
            with a2:
                new_email = st.text_input("Email *", placeholder="admin@rms.com")
            with a3:
                new_pw    = st.text_input("Password *", type="password")
            add_ok = st.form_submit_button(
                "➕ Add Admin", type="primary", use_container_width=True
            )

        if add_ok:
            errs = []
            if not new_uname.strip():
                errs.append("Username is required.")
            if not new_email.strip() or "@" not in new_email:
                errs.append("A valid email is required.")
            if len(new_pw) < 4:
                errs.append("Password must be at least 4 characters.")
            if errs:
                for e in errs:
                    st.error(f"⚠️ {e}")
            else:
                ok = create_platform_admin(
                    email=new_email.strip(),
                    username=new_uname.strip(),
                    password=new_pw,
                    performed_by=_actor(),
                )
                if ok:
                    st.success(f"✅ Admin **{new_uname}** created.")
                    time.sleep(0.5); st.rerun()
                else:
                    st.error("❌ Failed — username or email already exists.")

    # ── Change password ───────────────────────────────────────────────────
    with op2:
        if not admins:
            st.info("No admins available.")
        else:
            with st.form("chpw_form"):
                sel_email = st.selectbox(
                    "Select admin",
                    [a["email"] for a in admins],
                )
                p1, p2 = st.columns(2)
                with p1:
                    pw1 = st.text_input("New password *", type="password")
                with p2:
                    pw2 = st.text_input("Confirm password *", type="password")
                pw_ok = st.form_submit_button(
                    "🔑 Update Password", type="primary", use_container_width=True
                )

            if pw_ok:
                if not pw1:
                    st.error("⚠️ Password cannot be empty.")
                elif len(pw1) < 4:
                    st.error("⚠️ Minimum 4 characters.")
                elif pw1 != pw2:
                    st.error("⚠️ Passwords do not match.")
                else:
                    ok = update_platform_admin_password(sel_email, pw1, _actor())
                    if ok:
                        st.success(f"✅ Password updated for `{sel_email}`.")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Failed — check logs.")

    # ── Change email ──────────────────────────────────────────────────────
    with op3:
        if not admins:
            st.info("No admins available.")
        else:
            with st.form("chemail_form"):
                sel_admin = st.selectbox(
                    "Select admin",
                    admins,
                    format_func=lambda a: f"{a['username']}  ({a['email']})",
                )
                new_admin_email = st.text_input("New email *",
                                                placeholder="new@rms.com")
                email_ok = st.form_submit_button(
                    "📧 Update Email", type="primary", use_container_width=True
                )

            if email_ok:
                if not new_admin_email.strip() or "@" not in new_admin_email:
                    st.error("⚠️ Enter a valid email address.")
                else:
                    ok = update_platform_admin_email(
                        admin_id=sel_admin["id"],
                        new_email=new_admin_email.strip(),
                        performed_by=_actor(),
                    )
                    if ok:
                        st.success("✅ Email updated.")
                        time.sleep(0.5); st.rerun()
                    else:
                        st.error("❌ Failed — email may already be in use.")

    # ── Delete ────────────────────────────────────────────────────────────
    with op4:
        if len(admins) <= 1:
            st.warning(
                "⚠️ Only one platform admin exists. "
                "Add another admin first before removing this one."
            )
        else:
            # Can't delete your own account
            deletable = [a for a in admins if a["username"] != my_username]
            if not deletable:
                st.info("You cannot delete your own account from here.")
            else:
                with st.form("del_admin_form"):
                    to_del = st.selectbox(
                        "Select admin to remove",
                        deletable,
                        format_func=lambda a: f"{a['username']}  ({a['email']})",
                    )
                    st.warning(
                        "⚠️ This is irreversible. "
                        "The admin loses platform access immediately."
                    )
                    del_ok = st.form_submit_button(
                        "🗑️ Remove Admin", type="primary", use_container_width=True
                    )

                if del_ok:
                    ok = delete_platform_admin(
                        admin_id=to_del["id"], performed_by=_actor()
                    )
                    if ok:
                        st.success(f"✅ Admin **{to_del['username']}** removed.")
                        time.sleep(0.5); st.rerun()
                    else:
                        st.error("❌ Delete failed — check logs.")
