# app_sections_master/_db_ops.py
"""
Database Operations section — 3 sub-tabs:
  1. Backup & Download  — create backup, list backups, download any, delete old ones
  2. Restore            — select backup, typed confirmation, auto safety-backup
  3. Health & Maintenance — integrity check, FK check, vacuum, live stats
"""

import os
import streamlit as st
import pandas as pd
import logging
import time
from datetime import datetime

from master_database import (
    backup_master_db,
    restore_master_db,
    get_master_db_info,
    vacuum_master_db,
    master_db_health_check,
)
from master_database.db_ops    import list_master_backups, delete_master_backup
from master_database.connection import MASTER_DB_PATH
from main_utils import inject_login_css

logger = logging.getLogger(__name__)


def _actor() -> str:
    return st.session_state.get("username", "platform_admin")


# ═════════════════════════════════════════════════════════════════════════════
# Entry point
# ═════════════════════════════════════════════════════════════════════════════

def render_db_ops_section():
    st.caption(
        "All operations here target **master.db** only.  "
        "For school-level database operations use the System Dashboard "
        "inside each school."
    )
    inject_login_css("templates/tabs_styles.css")

    sub1, sub2, sub3 = st.tabs([
        "📦 Backup & Download",
        "🔄 Restore",
        "🔧 Health & Maintenance",
    ])

    with sub1:
        _backup_tab()
    with sub2:
        _restore_tab()
    with sub3:
        _health_tab()


# ═════════════════════════════════════════════════════════════════════════════
# Sub-tab 1  ·  Backup & Download
# ═════════════════════════════════════════════════════════════════════════════

def _backup_tab():
    left1, right1 = st.columns([1, 1], gap="large")

    # ── CREATE backup ─────────────────────────────────────────────────────
    with left1:
        st.markdown("#### 💾 Create Backup")
        
        custom_name = st.text_input(
            "Backup filename (optional — auto-named if blank)",
            placeholder=f"master_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            key="backup_name_input",
        )

        if st.button("💾 Create Backup Now",
                     type="primary", width="stretch",
                     key="create_backup_btn"):
            with st.spinner("Creating backup…"):
                result = backup_master_db(
                    backup_name=custom_name.strip() or None,
                    performed_by=_actor(),
                )
            if result["success"]:
                st.success(
                    f"✅ Backup saved  \n"
                    f"**{result['name']}**  ·  {result['size']}"
                )
                time.sleep(0.4); st.rerun()
            else:
                st.error(f"❌ Backup failed: {result['error']}")

    with right1:
        st.markdown("#### ⬇️ Download Live master.db")
        st.caption(
            "Downloads a snapshot of the live database file directly to your browser."
        )
        try:
            if os.path.exists(MASTER_DB_PATH):
                info = get_master_db_info()
                with open(MASTER_DB_PATH, "rb") as f:
                    raw = f.read()
                st.download_button(
                    label=f"⬇️ Download master.db  ({info['size']})",
                    data=raw,
                    file_name=f"master_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
                    mime="application/octet-stream",
                    width="stretch",
                )
            else:
                st.error("master.db not found on disk.")
        except Exception as e:
            st.error(f"Cannot read master.db: {e}")

    # ── EXISTING backups ──────────────────────────────────────────────────
    
    st.markdown("---")
    st.markdown("#### 📋 Existing Backups")

    backups = list_master_backups()

    if not backups:
        st.info("No backups yet. Create one on the left.")
    else:
        bdf = pd.DataFrame(backups)[["name", "size", "created", "age"]]
        bdf.columns = ["Filename", "Size", "Created", "Age"]
        st.dataframe(bdf, width="stretch", hide_index=True)

        st.markdown("---")

        left2, right2 = st.columns([1, 1], gap="large")

        with left2:
            # Download a specific backup file
            st.markdown("**⬇️ Download a specific backup**")
            dl_name = st.selectbox(
                "Backup to download",
                [b["name"] for b in backups],
                key="dl_backup_select",
                label_visibility="collapsed",
            )
            sel = next((b for b in backups if b["name"] == dl_name), None)
            if sel:
                try:
                    with open(sel["path"], "rb") as f:
                        bdata = f.read()
                    st.download_button(
                        label=f"⬇️ Download",
                        data=bdata,
                        file_name=dl_name,
                        mime="application/octet-stream",
                        width="stretch",
                    )
                except Exception as e:
                    st.error(f"Cannot read file: {e}")

        with right2:
            # Delete a backup
            st.markdown("**🗑️ Delete a backup**")
            del_name = st.selectbox(
                "Backup to delete",
                [b["name"] for b in backups],
                key="del_backup_select",
                label_visibility="collapsed",
            )

            if st.button("🗑️ Delete This Backup",
                            key="del_backup_btn", width="stretch"):
                st.session_state["pending_del_backup"] = del_name

            if st.session_state.get("pending_del_backup") == del_name:
                st.warning(f"Delete **{del_name}**? Cannot be undone.")
                cc1, cc2 = st.columns(2)
                with cc1:
                    if st.button("✅ Yes, Delete",
                                    key="confirm_del_backup_yes",
                                    type="primary", width="stretch"):
                        ok = delete_master_backup(del_name, performed_by=_actor())
                        st.session_state.pop("pending_del_backup", None)
                        if ok:
                            st.success(f"✅ Deleted: {del_name}")
                            time.sleep(0.4); st.rerun()
                        else:
                            st.error("Delete failed.")
                with cc2:
                    if st.button("Cancel", key="confirm_del_backup_no",
                                    width="stretch"):
                        st.session_state.pop("pending_del_backup", None)
                        st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# Sub-tab 2  ·  Restore
# ═════════════════════════════════════════════════════════════════════════════

def _restore_tab():
    st.markdown("#### 🔄 Restore master.db from Backup")
    st.caption(
        "A safety backup of the current database is created automatically "
        "before the restore begins, so you can roll back if needed."
    )

    backups = list_master_backups()

    if not backups:
        st.info(
            "No backups available. "
            "Create one first in the **Backup & Download** tab."
        )
        return

    # Warning banner
    st.error(
        "🚨 **Restoring replaces the live master.db immediately.**  \n"
        "All schools, users, and audit history will reflect the restored state.  \n"
        "**Restart the application after a successful restore.**"
    )

    chosen = st.selectbox(
        "Select backup to restore",
        backups,
        format_func=lambda b: f"{b['name']}   ({b['size']} · {b['age']})",
        key="restore_choice",
    )

    if chosen:
        ri1, ri2, ri3 = st.columns(3)
        ri1.info(f"📅 **Created:** {chosen['created']}")
        ri2.info(f"📦 **Size:** {chosen['size']}")
        ri3.info(f"⏱️ **Age:** {chosen['age']}")

        st.markdown("---")
        confirm = st.text_input(
            'Type  **RESTORE**  to confirm',
            placeholder="RESTORE",
            key="restore_confirm_input",
        )

        if st.button("🔄 Restore Database",
                     type="primary", width="stretch",
                     key="restore_btn"):
            if confirm.strip() != "RESTORE":
                st.error("❌ Type exactly **RESTORE** (uppercase) to proceed.")
            else:
                with st.spinner("Creating safety backup, then restoring…"):
                    result = restore_master_db(
                        chosen["name"], performed_by=_actor()
                    )

                if result["success"]:
                    st.success(
                        f"✅ **Restore complete.**  \n"
                        f"Restored from: `{chosen['name']}`  \n"
                        f"Safety backup: `{result['safety_backup']}`  \n\n"
                        "⚠️  **Please restart the application now.**"
                    )
                else:
                    st.error(f"❌ Restore failed: {result['error']}")
                    if result.get("safety_backup"):
                        st.info(
                            f"Safety backup was saved: `{result['safety_backup']}`"
                        )


# ═════════════════════════════════════════════════════════════════════════════
# Sub-tab 3  ·  Health & Maintenance
# ═════════════════════════════════════════════════════════════════════════════

def _health_tab():
    left, right = st.columns([1, 1], gap="large")

    # ── Left: health check + vacuum ───────────────────────────────────────
    with left:
        st.markdown("#### 🏥 Database Health Check")
        st.caption(
            "Runs `PRAGMA integrity_check` and `PRAGMA foreign_key_check` "
            "on master.db."
        )

        if st.button("🏥 Run Health Check",
                     width="stretch", key="run_health_btn"):
            with st.spinner("Running…"):
                r = master_db_health_check()
            st.session_state["health_result"] = r

            if "health_result" in st.session_state:
                r = st.session_state["health_result"]
                if r["status"] == "healthy":
                    st.success(f"🟢 **Healthy**  —  {r['details']}")
                elif r["status"] == "degraded":
                    st.warning(f"🟡 **Degraded**  —  {r['details']}")
                    if r["fk_violations"]:
                        st.markdown("**Foreign Key Violations:**")
                        st.json(r["fk_violations"])
                else:
                    st.error(f"🔴 **Error**  —  {r['details']}")

    with right:
        st.markdown("#### 🧹 Vacuum")
        st.caption(
            "Rebuilds master.db to reclaim unused space and defragment pages. "
            "Safe to run at any time — does not alter any data."
        )

        if st.button("🧹 Vacuum Database",
                     width="stretch", key="vacuum_btn"):
            with st.spinner("Vacuuming…"):
                ok = vacuum_master_db(performed_by=_actor())
            if ok:
                st.success("✅ Vacuum complete — database optimised.")
            else:
                st.error("❌ Vacuum failed — check application logs.")
        
    st.markdown("---")

    left2, right2 = st.columns([3, 1], gap="large")

    with left2:
        st.markdown("#### 📊 Database Statistics")

    with right2:
        if st.button("🔄 Refresh Stats",
                        width="stretch", key="refresh_stats_btn"):
            st.rerun()

    try:
        info    = get_master_db_info()
        backups = list_master_backups()

        s1, s2, s3, s4 = st.columns(4)
        s1.metric("File Size",       info["size"])
        s2.metric("Tables",          info["table_count"])
        s3.metric("Total Schools",   info["schools_total"])
        s4.metric("Active Schools",  info["schools_active"])
        s1.metric("Platform Admins", info["platform_admins"])
        s2.metric("Audit Entries",   info["audit_entries"])
        s3.metric("Backups on Disk", len(backups))
        s4.metric("Last Backup",     info["last_backup"])
        
    except Exception as e:
        st.error(f"Could not load stats: {e}")
