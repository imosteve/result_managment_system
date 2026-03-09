# app_sections/manage_subjects.py

import streamlit as st
import pandas as pd
import time
import re
from database_school import (
    get_all_classes, get_active_session, get_active_term_name, get_classes_for_session,
    get_subjects_by_class, create_subject, delete_subject, update_subject, clear_all_subjects,
    get_enrolled_students, get_student_selected_subjects, save_student_subject_selections,
    get_all_student_subject_selections
)
from main_utils import clean_input, create_metric_4col, inject_login_css, render_page_header
from auth.activity_tracker import ActivityTracker

def add_subjects():
    ActivityTracker.init()

    if not st.session_state.get("authenticated", False):
        st.error("⚠️ Please log in first.")
        st.switch_page("main.py")
        return

    if st.session_state.role not in ["superadmin", "admin", "class_teacher", "subject_teacher"]:
        st.error("⚠️ Access denied.")
        return

    user_id = st.session_state.get("user_id", None)
    role = st.session_state.get("role", None)

    st.set_page_config(page_title="Manage Subjects", layout="wide")
    inject_login_css("templates/tabs_styles.css")
    render_page_header("Manage Subject Combination")

    for key in [
        "show_delete_subject_confirm", "show_clear_subjects_confirm",
        "show_clear_selections_confirm"
    ]:
        if key not in st.session_state:
            st.session_state[key] = False
    for key in ["subject_to_delete_info", "clear_subjects_info", "clear_selections_info"]:
        if key not in st.session_state:
            st.session_state[key] = None

    # Active session/term — teachers never pick these manually
    session = get_active_session()
    if not session:
        st.warning("⚠️ No active session configured. Ask an admin to set the active session.")
        return

    term = get_active_term_name()
    if not term:
        st.warning("⚠️ No active term configured. Ask an admin to set the active term.")
        return

    classes = get_classes_for_session(session)
    if not classes:
        st.warning(f"⚠️ No classes found for session {session}.")
        return

    class_names = [c['class_name'] for c in classes]

    selected_class = st.selectbox("Select Class", class_names, key="manage_subjects_class")
    if not selected_class:
        return

    ActivityTracker.watch_value("manage_subjects_class_selector", f"{selected_class}_{session}_{term}")

    class_name = selected_class

    # Subjects are per-class only (no term/session)
    subjects = get_subjects_by_class(class_name)

    is_senior_class = bool(re.match(r"SSS [23].*$", class_name))

    # ── DIALOGS ────────────────────────────────────────────────────────────────
    if st.session_state.show_delete_subject_confirm and st.session_state.subject_to_delete_info:
        @st.dialog("Confirm Subject Deletion")
        def confirm_delete_subject():
            info = st.session_state.subject_to_delete_info
            st.markdown("### Are you sure you want to delete this subject?")
            st.error(f"**Subject Name:** {info['subject_name']}")
            st.error(f"**Class:** {info['class_name']}")
            st.markdown("---")
            st.warning("⚠️ **This action cannot be undone!**")
            st.warning("All scores for this subject will be permanently deleted.")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🚫 Cancel", key="cancel_delete_subject", type="secondary", width="stretch"):
                    ActivityTracker.update()
                    st.session_state.show_delete_subject_confirm = False
                    st.session_state.subject_to_delete_info = None
                    st.rerun()
            with col2:
                if st.button("❌ Delete Subject", key="confirm_delete_subject", type="primary", width="stretch"):
                    ActivityTracker.update()
                    delete_subject(info['subject_id'])
                    st.session_state.show_delete_subject_confirm = False
                    st.session_state.subject_to_delete_info = None
                    st.success(f"✅ Subject '{info['subject_name']}' deleted.")
                    time.sleep(1)
                    st.rerun()
        confirm_delete_subject()

    if st.session_state.show_clear_subjects_confirm and st.session_state.clear_subjects_info:
        @st.dialog("Confirm Clear All Subjects")
        def confirm_clear_subjects():
            info = st.session_state.clear_subjects_info
            st.markdown("### Are you sure you want to clear all subjects?")
            st.error(f"**Class:** {info['class_name']}")
            st.error(f"**Total Subjects:** {info['subject_count']}")
            st.markdown("---")
            st.warning("⚠️ **THIS ACTION CANNOT BE UNDONE!**")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🚫 Cancel", key="cancel_clear_subjects", type="secondary", width="stretch"):
                    ActivityTracker.update()
                    st.session_state.show_clear_subjects_confirm = False
                    st.session_state.clear_subjects_info = None
                    st.rerun()
            with col2:
                if st.button("🗑️ Clear All Subjects", key="confirm_clear_subjects", type="primary", width="stretch"):
                    ActivityTracker.update()
                    # New schema: clear_all_subjects(class_name) — no term/session
                    success = clear_all_subjects(info['class_name'])
                    st.session_state.show_clear_subjects_confirm = False
                    st.session_state.clear_subjects_info = None
                    if success:
                        st.success(f"✅ All subjects cleared for {info['class_name']}!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Failed to clear subjects. Please try again.")
        confirm_clear_subjects()

    if st.session_state.show_clear_selections_confirm and st.session_state.clear_selections_info:
        @st.dialog("Confirm Clear All Subject Selections")
        def confirm_clear_selections():
            info = st.session_state.clear_selections_info
            st.markdown("### Are you sure you want to clear all subject selections?")
            st.error(f"**Class:** {info['class_name']}")
            st.error(f"**Total Students:** {info['student_count']}")
            st.markdown("---")
            st.warning("⚠️ **This action cannot be undone!**")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🚫 Cancel", key="cancel_clear_selections", type="secondary", width="stretch"):
                    ActivityTracker.update()
                    st.session_state.show_clear_selections_confirm = False
                    st.session_state.clear_selections_info = None
                    st.rerun()
            with col2:
                if st.button("🗑️ Clear All Selections", key="confirm_clear_selections", type="primary", width="stretch"):
                    ActivityTracker.update()
                    try:
                        for student in info['students']:
                            save_student_subject_selections(
                                student['student_name'], [],
                                info['class_name'], info['session'], info['term']
                            )
                        st.session_state.show_clear_selections_confirm = False
                        st.session_state.clear_selections_info = None
                        st.success("✅ All subject selections cleared.")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
        confirm_clear_selections()

    # ── TABS ───────────────────────────────────────────────────────────────────
    if is_senior_class:
        tabs = st.tabs(["View/Edit Subjects", "Add Subjects", "Clear All Subjects", "Student Subject Selection"])
    else:
        tabs = st.tabs(["View/Edit Subjects", "Add Subjects", "Clear All Subjects"])

    if "manage_subjects_tab_tracker" not in st.session_state:
        st.session_state.manage_subjects_tab_tracker = 0

    # ── TAB 1: VIEW / EDIT SUBJECTS ───────────────────────────────────────────
    with tabs[0]:
        if st.session_state.manage_subjects_tab_tracker != 0:
            ActivityTracker.watch_tab("manage_subjects_tabs", 0)
            st.session_state.manage_subjects_tab_tracker = 0

        st.subheader("View/Edit Subjects")
        if subjects:
            create_metric_4col(class_name, term, session, subjects, "subject")

            header_cols = st.columns([0.5, 5, 1, 1])
            header_cols[0].markdown("**S/N**")
            header_cols[1].markdown("**Subject Name**")
            header_cols[2].markdown("**Update**")
            header_cols[3].markdown("**Delete**")

            for i, subject in enumerate(subjects):
                col1, col2, col3, col4 = st.columns([0.5, 5, 1, 1], gap="small", vertical_alignment="bottom")
                col1.markdown(f"**{i+1}**")

                new_subject_name = col2.text_input(
                    "Subject",
                    value=subject['subject_name'] if isinstance(subject, dict) else subject[1],
                    key=f"subject_name_{i}",
                    label_visibility="collapsed"
                ).upper()

                subj_id = subject['id'] if isinstance(subject, dict) else subject[0]
                subj_name = subject['subject_name'] if isinstance(subject, dict) else subject[1]

                update_disabled = role == "subject_teacher"
                if col3.button("💾", key=f"update_{i}", disabled=update_disabled):
                    ActivityTracker.update()
                    new_upper = clean_input(new_subject_name, "subject").strip().upper()
                    if any(
                        (s['subject_name'] if isinstance(s, dict) else s[1]).strip().upper() == new_upper
                        and (s['id'] if isinstance(s, dict) else s[0]) != subj_id
                        for s in subjects
                    ):
                        st.markdown(
                            f'<div class="error-container">⚠️ Subject "{new_upper}" already exists.</div>',
                            unsafe_allow_html=True
                        )
                    else:
                        # New schema: update_subject(id, new_name, class_name) — no term/session
                        success = update_subject(subj_id, new_upper, class_name)
                        if success:
                            st.markdown(f'<div class="success-container">✅ Updated to {new_upper}</div>', unsafe_allow_html=True)
                            st.rerun()
                        else:
                            st.markdown(f'<div class="error-container">⚠️ Failed to update. May already exist.</div>', unsafe_allow_html=True)

                delete_disabled = role == "subject_teacher"
                if col4.button("❌", key=f"delete_{i}", disabled=delete_disabled):
                    ActivityTracker.update()
                    st.session_state.show_delete_subject_confirm = True
                    st.session_state.subject_to_delete_info = {
                        "subject_id": subj_id,
                        "subject_name": subj_name,
                        "class_name": class_name
                    }
                    st.rerun()
        else:
            st.info("No subjects found. Add subjects in the 'Add Subjects' tab.")

    # ── TAB 2: ADD SUBJECTS ───────────────────────────────────────────────────
    with tabs[1]:
        if st.session_state.manage_subjects_tab_tracker != 1:
            ActivityTracker.watch_tab("manage_subjects_tabs", 1)
            st.session_state.manage_subjects_tab_tracker = 1

        st.subheader("Add Subjects")
        if role == "subject_teacher":
            st.info("Subject Teachers cannot add new subjects.")
        else:
            if 'subject_form_counter' not in st.session_state:
                st.session_state.subject_form_counter = 0

            with st.form(f"add_subject_form_{st.session_state.subject_form_counter}"):
                new_subjects_input = st.text_area(
                    "Enter subject names (one per line)",
                    height=150,
                    placeholder="Mathematics\nEnglish Language\nPhysics"
                )
                submitted = st.form_submit_button("➕ Add Subjects")
                ActivityTracker.watch_form(submitted)

                if submitted:
                    new_subjects_raw = [
                        clean_input(s, "subject").strip().upper()
                        for s in new_subjects_input.split("\n") if s.strip()
                    ]
                    unique_new = list(set(new_subjects_raw))
                    existing_names = {
                        (s['subject_name'] if isinstance(s, dict) else s[1]).upper()
                        for s in subjects
                    }
                    if not unique_new:
                        st.markdown('<div class="error-container">⚠️ Please enter at least one subject.</div>', unsafe_allow_html=True)
                    else:
                        added, skipped = [], []
                        for subj in unique_new:
                            if subj in existing_names:
                                skipped.append(subj)
                            else:
                                # New schema: create_subject(name, class_name) — no term/session
                                success = create_subject(subj, class_name)
                                if success:
                                    added.append(subj)
                                else:
                                    skipped.append(subj)
                        if added:
                            st.markdown(f'<div class="success-container">✅ Added: {", ".join(added)}</div>', unsafe_allow_html=True)
                            st.session_state.subject_form_counter += 1
                            st.rerun()
                        if skipped:
                            st.markdown(f'<div class="error-container">⚠️ Skipped: {", ".join(skipped)}</div>', unsafe_allow_html=True)

    # ── TAB 3: CLEAR ALL SUBJECTS ─────────────────────────────────────────────
    with tabs[2]:
        if st.session_state.manage_subjects_tab_tracker != 2:
            ActivityTracker.watch_tab("manage_subjects_tabs", 2)
            st.session_state.manage_subjects_tab_tracker = 2

        st.subheader("Clear All Subjects")
        if role == "subject_teacher":
            st.info("Subject Teachers cannot clear subjects.")
        else:
            st.warning("⚠️ This permanently deletes all subjects and associated scores. Cannot be undone.")
            if subjects:
                if st.button("🗑️ Clear All Subjects", key="clear_all_subjects_btn"):
                    ActivityTracker.update()
                    st.session_state.show_clear_subjects_confirm = True
                    st.session_state.clear_subjects_info = {
                        "class_name": class_name,
                        "subject_count": len(subjects)
                    }
                    st.rerun()
            else:
                st.info("No subjects available to clear.")

    # ── TAB 4: STUDENT SUBJECT SELECTION (senior classes only) ────────────────
    if is_senior_class:
        with tabs[3]:
            if st.session_state.manage_subjects_tab_tracker != 3:
                ActivityTracker.watch_tab("manage_subjects_tabs", 3)
                st.session_state.manage_subjects_tab_tracker = 3

            st.subheader("Student Subject Selection")
            if role == "subject_teacher":
                st.info("Subject Teachers cannot manage subject selections.")
            else:
                students = get_enrolled_students(class_name, session)
                if not students:
                    st.warning(f"⚠️ No students enrolled for {class_name} - {session}.")
                    return
                if not subjects:
                    st.warning("⚠️ No subjects available. Please add subjects first.")
                    return

                # Summary table
                # New schema: get_all_student_subject_selections(class_name, session, term)
                selections = get_all_student_subject_selections(class_name, session, term)
                if selections:
                    selection_map = {}
                    for row in selections:
                        sname = row['student_name'] if isinstance(row, dict) else row[0]
                        subj = row['subject_name'] if isinstance(row, dict) else row[1]
                        selection_map.setdefault(sname, []).append(subj)

                    summary_data = []
                    for i, student in enumerate(students, 1):
                        sn = student['student_name']
                        sels = selection_map.get(sn, [])
                        summary_data.append({
                            "S/N": str(i),
                            "Student Name": sn,
                            "Selected Subjects": ", ".join(sels) if sels else "None",
                            "Number of Subjects": len(sels)
                        })
                    st.dataframe(
                        pd.DataFrame(summary_data),
                        column_config={
                            "S/N": st.column_config.TextColumn("S/N", width=10),
                            "Student Name": st.column_config.TextColumn("Student Name", width=150),
                            "Selected Subjects": st.column_config.TextColumn("Selected Subjects", width=500),
                            "Number of Subjects": st.column_config.NumberColumn("Number of Subjects", width=80)
                        },
                        hide_index=True, width="stretch",
                        height=35 * len(summary_data) + 38
                    )
                else:
                    st.info("No subject selections made yet.")

                st.markdown("---")
                st.markdown("### Manage Individual Student Selections")

                student_names = [s['student_name'] for s in students]
                selected_student = st.selectbox("Select Student", [""] + student_names, key="student_select")
                ActivityTracker.watch_value("student_select_dropdown", selected_student)

                if selected_student:
                    st.markdown(f"#### Subject Selection for **{selected_student}**")
                    # New schema: get_student_selected_subjects(name, class_name, session, term)
                    current_selections = get_student_selected_subjects(selected_student, class_name, session, term)
                    subject_names = [
                        s['subject_name'] if isinstance(s, dict) else s[1]
                        for s in subjects
                    ]

                    col1, col2 = st.columns(2)
                    selected_subjects = []
                    for i, subj_name in enumerate(subject_names):
                        is_sel = subj_name in current_selections
                        col = col1 if i % 2 == 0 else col2
                        ck = f"subject_{selected_student}_{subj_name}"
                        val = col.checkbox(subj_name, value=is_sel, key=ck)
                        ActivityTracker.watch_value(ck, val)
                        if val:
                            selected_subjects.append(subj_name)

                    if st.button("💾 Save Subject Selections", key="save_selections"):
                        ActivityTracker.update()
                        try:
                            # New schema: save_student_subject_selections(name, subjects, class_name, session, term)
                            save_student_subject_selections(
                                selected_student, selected_subjects, class_name, session, term
                            )
                            st.success(f"✅ Subject selections saved for {selected_student}")
                            if "student_select" in st.session_state:
                                del st.session_state["student_select"]
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error saving selections: {str(e)}")

                st.markdown("---")
                st.markdown("### Batch Operations")
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("#### Assign All Subjects to All Students")
                    if st.button("📚 Assign All Subjects", key="assign_all"):
                        ActivityTracker.update()
                        try:
                            all_names = [
                                s['subject_name'] if isinstance(s, dict) else s[1]
                                for s in subjects
                            ]
                            for student in students:
                                save_student_subject_selections(
                                    student['student_name'], all_names, class_name, session, term
                                )
                            st.success("✅ All subjects assigned to all students.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")

                with col2:
                    st.markdown("#### Clear All Selections")
                    if st.button("🗑️ Clear All Selections", key="clear_all_selections_btn"):
                        ActivityTracker.update()
                        st.session_state.show_clear_selections_confirm = True
                        st.session_state.clear_selections_info = {
                            "class_name": class_name,
                            "session": session,
                            "term": term,
                            "students": students,
                            "student_count": len(students)
                        }
                        st.rerun()
