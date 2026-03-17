# app_sections/manage_classes.py

import streamlit as st
import time
from database_school import (
    get_all_classes, create_class, delete_class, update_class,
    get_subjects_by_class,
    get_class_score_system, set_class_score_system,
    get_all_score_systems_for_class,
    get_all_sessions, get_classes_for_session,
    open_class_for_session, close_class_for_session,
    reopen_class_for_session, delete_class_session,
)
from main_utils import inject_login_css, render_page_header, inject_metric_css
from auth.activity_tracker import ActivityTracker

def create_class_section():
    if not st.session_state.get("authenticated", False):
        st.error("⚠️ Please log in first.")
        st.switch_page("main.py")
        return

    if st.session_state.role not in ["superadmin", "admin"]:
        st.error("⚠️ Access denied. Admins only.")
        return

    ActivityTracker.init()

    st.set_page_config(page_title="Manage Classes", layout="wide")
    inject_login_css("templates/tabs_styles.css")
    render_page_header("Manage Class")

    # New schema: get_all_classes() → [{id, class_name, description, created_at}]
    classes = get_all_classes()

    tab1, tab2, tab3, tab4 = st.tabs(["View/Edit Classes", "Add Class", "📐 Score System", "🔓 Session Enrollment"])

    active_tab = st.session_state.get("manage_classes_active_tab", 0)
    ActivityTracker.watch_tab("manage_classes", active_tab)

    # ── TAB 1: VIEW / EDIT ─────────────────────────────────────────────────────
    with tab1:
        st.session_state.manage_classes_active_tab = 0
        st.subheader("View/Edit Classes")

        with st.container(border=True):
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                filter_type = st.selectbox(
                    "Filter by Class",
                    ["All", "Kindergarten", "Nursery", "Primary", "JSS", "SSS"],
                    key="filter_class_view"
                )
                ActivityTracker.watch_value("filter_class_view", filter_type)
            with col3:
                search_query = st.text_input(
                    "🔍 Search",
                    placeholder="Search class...",
                    key="search_class_view"
                )
                if search_query:
                    ActivityTracker.watch_value("search_class_view", search_query)

        filtered_classes = classes

        if filter_type != "All":
            filtered_classes = [
                cls for cls in filtered_classes
                if cls['class_name'].upper().startswith(filter_type.upper())
            ]

        if search_query:
            filtered_classes = [
                cls for cls in filtered_classes
                if search_query.lower() in cls['class_name'].lower()
            ]

        if filtered_classes:
            header_cols = st.columns([3, 4, 1.2, 1.2])
            header_cols[0].markdown("**Class Name**")
            header_cols[1].markdown("**Description**")
            header_cols[2].markdown("**Update**")
            header_cols[3].markdown("**Delete**")

            for i, cls in enumerate(filtered_classes):
                col1, col2, col3, col4 = st.columns([3, 4, 1.2, 1.2], gap="small", vertical_alignment="bottom")

                new_class = col1.text_input(
                    "Class",
                    value=cls['class_name'],
                    key=f"class_name_{i}",
                    label_visibility="collapsed"
                ).strip().upper()

                new_desc = col2.text_input(
                    "Description",
                    value=cls.get('description') or "",
                    key=f"desc_{i}",
                    label_visibility="collapsed"
                ).strip()

                if col3.button("💾", key=f"update_{i}"):
                    ActivityTracker.update()
                    new_class_upper = new_class.strip().upper()
                    # Duplicate check (exclude self)
                    if any(
                        c["class_name"].strip().upper() == new_class_upper
                        and c["class_name"] != cls["class_name"]
                        for c in classes
                    ):
                        st.markdown(
                            f'<div class="error-container">⚠️ A class named "{new_class_upper}" already exists.</div>',
                            unsafe_allow_html=True
                        )
                    else:
                        update_class(
                            class_name=cls['class_name'],
                            new_name=new_class_upper,
                            description=new_desc or None
                        )
                        st.markdown(
                            f'<div class="success-container">✅ Updated to {new_class_upper}</div>',
                            unsafe_allow_html=True
                        )
                        st.rerun()

                if col4.button("❌", key=f"delete_{i}"):
                    ActivityTracker.update()
                    st.session_state["delete_pending"] = {
                        "class_name": cls["class_name"],
                        "index": i
                    }

                if "delete_pending" in st.session_state:
                    @st.dialog("Confirm Class Deletion", width="small")
                    def confirm_delete_class():
                        pending = st.session_state["delete_pending"]
                        if pending["index"] == i:
                            st.warning(f"⚠️ Are you sure you want to delete '{pending['class_name']}'?")
                            st.error("This will also delete all associated students, subjects, and scores.")
                            confirm_col1, confirm_col2 = st.columns(2)
                            if confirm_col1.button("✅ Delete", key=f"confirm_delete_{i}"):
                                ActivityTracker.update()
                                success, msg = delete_class(pending["class_name"])
                                if success:
                                    st.markdown(
                                        f'<div class="success-container">❌ Deleted {pending["class_name"]}</div>',
                                        unsafe_allow_html=True
                                    )
                                else:
                                    st.error(f"❌ {msg}")
                                del st.session_state["delete_pending"]
                                st.rerun()
                            elif confirm_col2.button("❌ Cancel", key=f"cancel_delete_{i}"):
                                del st.session_state["delete_pending"]
                                st.info("Deletion cancelled.")
                                st.rerun()
                    confirm_delete_class()
                    break
        else:
            st.info("No classes found matching your filters.")

    # ── TAB 2: ADD CLASS ───────────────────────────────────────────────────────
    with tab2:
        st.session_state.manage_classes_active_tab = 1
        st.subheader("Add Class")

        if st.session_state.get("reset_add_class", False):
            st.session_state["class_input"] = ""
            st.session_state["arm_input"] = ""
            st.session_state["reset_add_class"] = False

        for key, default in [("class_input", ""), ("arm_input", "")]:
            if key not in st.session_state:
                st.session_state[key] = default

        with st.form("add_class_form"):
            col1, col2 = st.columns([2, 2])
            class_name = col1.selectbox(
                "Class",
                ["", "Kindergarten", "Nursery", "Primary", "JSS", "SSS"],
                key="class_input"
            )
            class_arm = col2.text_input(
                "Arm (e.g. 4, 4A, 4B)",
                key="arm_input"
            ).strip().upper()

            new_class = f'{class_name.upper()} {class_arm}'.strip()

            description = st.text_input(
                "Description (optional)",
                placeholder="e.g. Morning class"
            ).strip()

            submitted = st.form_submit_button("➕ Add Class")
            ActivityTracker.watch_form(submitted)

            if submitted:
                if not class_name or not class_arm:
                    st.markdown(
                        '<div class="error-container">⚠️ Please fill all required fields.</div>',
                        unsafe_allow_html=True
                    )
                elif any(
                    cls["class_name"].strip().upper() == new_class.upper()
                    for cls in classes
                ):
                    st.markdown(
                        f'<div class="error-container">⚠️ Class "{new_class}" already exists.</div>',
                        unsafe_allow_html=True
                    )
                else:
                    success = create_class(new_class, description or None)
                    if success:
                        st.markdown(
                            f'<div class="success-container">✅ Class "{new_class}" added.</div>',
                            unsafe_allow_html=True
                        )
                        st.session_state["reset_add_class"] = True
                        st.rerun()
                    else:
                        st.markdown(
                            f'<div class="error-container">❌ Failed to add class "{new_class}". It may already exist.</div>',
                            unsafe_allow_html=True
                        )
                        st.rerun()

    # ── TAB 3: SCORE SYSTEM ────────────────────────────────────────────────────
    with tab3:
        st.session_state.manage_classes_active_tab = 2
        _render_score_system_tab(classes)

    # ── TAB 4: SESSION ENROLLMENT ──────────────────────────────────────────────
    with tab4:
        st.session_state.manage_classes_active_tab = 3
        _render_session_enrollment_tab(classes)



# ─────────────────────────────────────────────────────────────────────────────
# Score System Tab  (per-class, per-term)
# ─────────────────────────────────────────────────────────────────────────────

def _render_score_system_tab(classes: list):
    """
    Tab 3 — Set score system per class and per term.

    30/70 is the default valid system — it does NOT mean "not configured".
    Only 40/60 classes need an explicit change here.
    Each term can have a different system.
    """
    TERMS = ["First", "Second", "Third"]
    SYSTEMS = {"30/70": (30, 70), "40/60": (40, 60)}
    SYSTEM_LABELS = list(SYSTEMS.keys())

    st.subheader("Class Score Systems")
    st.caption(
        "Each class/term defaults to **30 CA / 70 Exam**.  "
        "Change any term to 40/60 here if needed.  "
        "Teachers can enter scores immediately — no configuration required.  "
        "Changing a system does **not** delete existing scores."
    )

    if not classes:
        st.warning("No classes found. Add a class first.")
        return

    # ── Bulk setter ───────────────────────────────────────────────────────
    with st.expander("⚡ Bulk Set — apply one system to all classes", expanded=False):
        bc1, bc2, bc3 = st.columns([2, 3, 1], vertical_alignment="bottom")
        with bc1:
            bulk_system = st.selectbox("System", SYSTEM_LABELS, key="bulk_score_system_choice")
        with bc2:
            bulk_terms  = st.multiselect("Apply to terms", TERMS, default=TERMS, key="bulk_score_terms")
        with bc3:
            if st.button("Apply", key="bulk_apply_btn", type="primary", use_container_width=True):
                if not bulk_terms:
                    st.warning("Select at least one term.")
                else:
                    max_ca, max_exam = SYSTEMS[bulk_system]
                    ok = sum(
                        1 for cls in classes for t in bulk_terms
                        if set_class_score_system(cls["class_name"], t, max_ca, max_exam)
                    )
                    st.success(f"✅ Set {max_ca}/{max_exam} for {ok} class-term combination(s).")
                    time.sleep(0.3); st.rerun()

    st.divider()

    # ── Search ────────────────────────────────────────────────────────────
    search = st.text_input(
        "🔍 Filter classes", placeholder="Search by class name…",
        key="score_sys_search", label_visibility="collapsed",
    )
    visible = [c for c in classes
               if not search or search.lower() in c["class_name"].lower()]
    if not visible:
        st.warning("No classes match your search.")
        return

    # ── Per-class cards ───────────────────────────────────────────────────
    for cls in visible:
        class_name = cls["class_name"]
        systems    = get_all_score_systems_for_class(class_name)

        with st.expander(f"**{class_name}**", expanded=False):
            # Table header
            hc = st.columns([2, 2, 1])
            hc[0].markdown("**Term**")
            hc[1].markdown("**Current System**")
            hc[2].markdown("**Save**")

            for term in TERMS:
                s       = systems[term]
                cur_key = s["system_key"]
                cur_idx = SYSTEM_LABELS.index(cur_key)

                tc = st.columns([2, 2, 1], vertical_alignment="bottom")
                tc[0].markdown(term)

                new_choice = tc[1].selectbox(
                    f"System for {term}",
                    SYSTEM_LABELS,
                    index=cur_idx,
                    key=f"ss_{class_name}_{term}",
                    label_visibility="collapsed",
                )

                if tc[2].button("💾", key=f"ss_save_{class_name}_{term}",
                                use_container_width=True):
                    ActivityTracker.update()
                    ca, ex = SYSTEMS[new_choice]
                    if set_class_score_system(class_name, term, ca, ex):
                        st.success(f"✅ {class_name} — {term}: {new_choice} saved.")
                        time.sleep(0.2); st.rerun()
                    else:
                        st.error(f"❌ Failed to save {term} for {class_name}.")



# ─────────────────────────────────────────────────────────────────────────────
# Session Enrollment Tab
# ─────────────────────────────────────────────────────────────────────────────

def _render_session_enrollment_tab(classes: list):
    """
    Tab 4 — Open / close / remove classes from a session.

    Open:   creates a class_sessions row (idempotent)
    Close:  sets is_active=0 (soft — data kept, marks class inactive)
    Remove: DELETES the class_sessions row and all cascaded data
            (students, scores, comments, etc. for that session)
            This is what unblocks delete_class().
    """
    st.subheader("Session Enrollment")
    st.caption(
        "Control which classes are open for each session.  "
        "**Remove** permanently deletes all data for that class in that session "
        "and is the prerequisite for deleting the class itself."
    )

    sessions = get_all_sessions()
    if not sessions:
        st.warning("No sessions found. Create a session in Admin Panel first.")
        return

    session_names = [s["session"] if isinstance(s, dict) else s for s in sessions]

    selected_session = st.selectbox(
        "Select Session", session_names, key="sess_enroll_session_select"
    )

    if not selected_session:
        return

    open_classes = get_classes_for_session(selected_session)
    open_names   = {c["class_name"] for c in open_classes}
    closed_names = {c["class_name"] for c in open_classes if not c["is_active"]}

    st.divider()

    # ── Open new classes ──────────────────────────────────────────────────
    st.markdown("#### 🔓 Open Classes for This Session")
    not_open = [c for c in classes if c["class_name"] not in open_names]

    if not not_open:
        st.info("All classes are already open for this session.")
    else:
        cls_cols = st.columns(3)
        checks   = {}
        for i, c in enumerate(not_open):
            checks[c["class_name"]] = cls_cols[i % 3].checkbox(
                c["class_name"], key=f"open_chk_{c['class_name']}"
            )
        to_open = [cn for cn, v in checks.items() if v]
        if st.button("🔓 Open Selected", key="open_sel_btn",
                     type="primary", disabled=not to_open):
            for cn in to_open:
                open_class_for_session(cn, selected_session)
            st.success(f"✅ Opened {len(to_open)} class(es).")
            time.sleep(0.3); st.rerun()

    st.divider()

    # ── Manage open classes ───────────────────────────────────────────────
    st.markdown("#### 📋 Currently Open Classes")

    if not open_classes:
        st.info("No classes open for this session yet.")
        return

    # Column headers
    hc = st.columns([3, 2, 1, 1, 1])
    hc[0].markdown("**Class**")
    hc[1].markdown("**Status**")
    hc[2].markdown("**Close**")
    hc[3].markdown("**Re-open**")
    hc[4].markdown("**Remove**")

    for cls in open_classes:
        cname    = cls["class_name"]
        is_active = cls["is_active"]
        enrolled = cls.get("student_count", 0)

        row = st.columns([3, 2, 1, 1, 1], vertical_alignment="bottom")
        row[0].markdown(f"**{cname}**  \n*{enrolled} student(s) enrolled*")
        row[1].markdown("🟢 Active" if is_active else "🔴 Closed")

        # Close (soft)
        if row[2].button("🔒", key=f"close_{cname}_{selected_session}",
                          disabled=not is_active,
                          use_container_width=True,
                          help="Soft-close — data preserved, marks inactive"):
            ActivityTracker.update()
            close_class_for_session(cname, selected_session)
            st.info(f"🔒 {cname} closed for {selected_session}.")
            time.sleep(0.3); st.rerun()

        # Re-open
        if row[3].button("🔓", key=f"reopen_{cname}_{selected_session}",
                          disabled=bool(is_active),
                          use_container_width=True,
                          help="Re-open a closed class"):
            ActivityTracker.update()
            if reopen_class_for_session(cname, selected_session):
                st.success(f"🔓 {cname} re-opened.")
                time.sleep(0.3); st.rerun()
            else:
                st.error(f"❌ Could not re-open {cname}.")

        # Remove (hard delete with confirmation)
        if row[4].button("🗑️", key=f"rm_{cname}_{selected_session}",
                          use_container_width=True,
                          help="Permanently remove — deletes all student/score data"):
            ActivityTracker.update()
            st.session_state["confirm_remove_session"] = {
                "class_name": cname,
                "session":    selected_session,
                "enrolled":   enrolled,
            }

    # ── Removal confirmation dialog ───────────────────────────────────────
    pending = st.session_state.get("confirm_remove_session")
    if pending:
        @st.dialog("⚠️ Confirm Session Removal", width="small")
        def _confirm_remove():
            p = st.session_state["confirm_remove_session"]
            st.error(
                f"Remove **{p['class_name']}** from **{p['session']}**?  \n\n"
                f"This will permanently delete **{p['enrolled']} enrollment(s)** "
                "and all their scores, comments, and psychomotor ratings.  \n\n"
                "The class definition is preserved — only this session's data is erased."
            )
            typed = st.text_input(
                f"Type the class name **{p['class_name']}** to confirm:",
                key="rm_session_confirm_input"
            )
            c1, c2 = st.columns(2)
            if c1.button("🗑️ Remove", type="primary",
                         use_container_width=True, key="rm_sess_yes"):
                if typed.strip() == p["class_name"]:
                    ok, msg = delete_class_session(p["class_name"], p["session"])
                    del st.session_state["confirm_remove_session"]
                    if ok:
                        st.success(f"✅ {msg}")
                    else:
                        st.error(f"❌ {msg}")
                    time.sleep(0.5); st.rerun()
                else:
                    st.error("Class name does not match.")
            if c2.button("Cancel", use_container_width=True, key="rm_sess_no"):
                del st.session_state["confirm_remove_session"]
                st.rerun()

        _confirm_remove()