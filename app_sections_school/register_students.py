# app_sections/register_students.py

import streamlit as st
import pandas as pd
from database_school import (
    get_active_session, get_classes_for_session,
    create_student, enroll_student, unenroll_student,
    get_enrolled_students, update_student, delete_student
)
from main_utils import clean_input, create_metric_4col, inject_login_css, render_page_header
from auth.activity_tracker import ActivityTracker
from utils.paginators import streamlit_filter

import logging
logger = logging.getLogger(__name__)

def register_students():
    ActivityTracker.init()

    if not st.session_state.get("authenticated", False):
        st.error("⚠️ Please log in first.")
        st.switch_page("main.py")
        return

    if st.session_state.role not in ["superadmin", "admin", "class_teacher"]:
        st.error("⚠️ Access denied. Admins and Class Teachers only.")
        return

    user_id = st.session_state.get('user_id')
    role = st.session_state.get('role')

    st.set_page_config(page_title="Register Students", layout="wide")
    inject_login_css("templates/tabs_styles.css")
    render_page_header("Manage Students Data")

    # Active session drives class list — teachers never pick session manually
    session = get_active_session()
    if not session:
        st.warning("⚠️ No active session configured. Please ask an admin to set the active session.")
        return

    classes = get_classes_for_session(session)
    if not classes:
        st.warning(f"⚠️ No classes found for session {session}.")
        return

    class_names = [c['class_name'] for c in classes]

    selected_class = st.selectbox(
        "Select Class",
        class_names,
        key="register_students_class"
    )
    if not selected_class:
        return

    ActivityTracker.watch_value("register_students_class_selector", f"{selected_class}_{session}")

    class_name = selected_class

    # Enrolled students for this class+session
    students = get_enrolled_students(class_name, session)  # → [{student_name, ...}]
    if not students:
        st.info("No students enrolled for this class. Add students below.")

    create_metric_4col(class_name, "", session, students, "student")

    # Build display DataFrame
    df_data = []
    for idx, student in enumerate(students, 1):
        df_data.append({
            "S/N": str(idx),
            "Name": student['student_name'],
            "Gender": student.get('gender', ''),
            "Email": student.get('email', ''),
            "Paid Fees": student.get('school_fees_paid', 'NO')
        })

    df = pd.DataFrame(df_data) if df_data else pd.DataFrame(columns=["S/N", "Name", "Gender", "Email", "Paid Fees"])

    tabs = st.tabs(["View/Edit Students", "Add New Student", "Batch Add Students", "Remove Student(s)"])

    if "register_students_tab_tracker" not in st.session_state:
        st.session_state.register_students_tab_tracker = 0

    # ── TAB 1: VIEW / EDIT ────────────────────────────────────────────────────
    with tabs[0]:
        if st.session_state.register_students_tab_tracker != 0:
            ActivityTracker.watch_tab("register_students_tabs", 0)
            st.session_state.register_students_tab_tracker = 0

        st.subheader("Student List")

        filtered_display_df = streamlit_filter(df, table_name="students_table")
        edited_df = st.data_editor(
            filtered_display_df,
            column_config={
                "S/N": st.column_config.TextColumn("S/N", disabled=True, width=10),
                "Name": st.column_config.TextColumn("Name", required=True, width=300),
                "Gender": st.column_config.SelectboxColumn("Gender", options=["M", "F"], required=True, width=50),
                "Email": st.column_config.TextColumn("Email", help="Valid email address", width=300),
                "Paid Fees": st.column_config.SelectboxColumn("Paid Fees", options=["NO", "YES"], width=80),
            },
            hide_index=True,
            width="stretch",
            key="student_editor",
            height=35 * len(filtered_display_df) + 38
        )

        if st.button("💾 Save Changes", key="save_changes"):
            ActivityTracker.update()
            errors = []
            success_count = 0

            for idx, row in edited_df.iterrows():
                old_name = students[idx]['student_name'] if idx < len(students) else None
                if not old_name:
                    errors.append(f"❌ Row {idx + 1}: Cannot determine original student name.")
                    continue

                name = clean_input(str(row.get("Name", "")), "name")
                gender = str(row.get("Gender", ""))
                email = clean_input(str(row.get("Email", "")), "email")
                school_fees_paid = str(row.get("Paid Fees", ""))

                if not name:
                    errors.append(f"❌ Row {idx + 1}: Name is required")
                    continue
                if gender not in ["M", "F"]:
                    errors.append(f"❌ Row {idx + 1}: Gender must be 'M' or 'F'")
                    continue
                if email and "@" not in email:
                    errors.append(f"❌ Row {idx + 1}: Invalid email format")
                    continue
                if school_fees_paid not in ["NO", "YES"]:
                    errors.append(f"❌ Row {idx + 1}: Paid Fees must be 'NO' or 'YES'")
                    continue

                try:
                    update_student(old_name, new_name=name, gender=gender, email=email, school_fees_paid=school_fees_paid)
                    success_count += 1
                except Exception as e:
                    logger.error(f"Failed to update student {old_name}: {e}")
                    errors.append(f"❌ Row {idx + 1}: Failed to update '{old_name}'")

            if errors:
                for err in errors:
                    st.error(err)
            if success_count > 0:
                st.markdown(f'<div class="success-container">✅ Successfully updated {success_count} student(s)!</div>', unsafe_allow_html=True)
                st.rerun()

    # ── TAB 2: ADD NEW STUDENT ────────────────────────────────────────────────
    with tabs[1]:
        if st.session_state.register_students_tab_tracker != 1:
            ActivityTracker.watch_tab("register_students_tabs", 1)
            st.session_state.register_students_tab_tracker = 1

        st.subheader("Add New Student")

        if 'student_form_counter' not in st.session_state:
            st.session_state.student_form_counter = 0

        with st.form(f"add_student_form_{st.session_state.student_form_counter}"):
            new_name = st.text_input("Name", placeholder="Enter student name")
            new_gender = st.selectbox("Gender", ["M", "F"])
            new_email = st.text_input("Email", placeholder="Enter student email")
            school_fees_paid = st.selectbox("Paid Fees", ["NO", "YES"])
            submit_button = st.form_submit_button("➕ Add Student")
            ActivityTracker.watch_form(submit_button)

            if submit_button:
                errors = []
                new_name = clean_input(new_name, "name")
                new_email = clean_input(new_email, "email")

                if not new_name:
                    errors.append("❌ Name is required")
                if new_email and "@" not in new_email:
                    errors.append("❌ Invalid email format")
                enrolled_names = {s['student_name'].lower() for s in students}
                if new_name.lower() in enrolled_names:
                    errors.append("❌ Student name already exists in this class")

                if not errors:
                    # Create in master registry then enroll
                    ok = create_student(new_name, new_gender, new_email, school_fees_paid)
                    if ok:
                        enroll_student(new_name, class_name, session)
                        st.markdown('<div class="success-container">✅ Student added and enrolled successfully!</div>', unsafe_allow_html=True)
                        st.session_state.student_form_counter += 1
                        st.rerun()
                    else:
                        # Student may already exist in registry — just enroll
                        enroll_student(new_name, class_name, session)
                        st.markdown('<div class="success-container">✅ Student enrolled successfully!</div>', unsafe_allow_html=True)
                        st.session_state.student_form_counter += 1
                        st.rerun()

                if errors:
                    for err in errors:
                        st.error(err)

    # ── TAB 3: BATCH ADD ──────────────────────────────────────────────────────
    with tabs[2]:
        if st.session_state.register_students_tab_tracker != 2:
            ActivityTracker.watch_tab("register_students_tabs", 2)
            st.session_state.register_students_tab_tracker = 2

        st.subheader("Batch Add Students")
        st.markdown("Enter multiple students below. Each row represents one student.")

        if 'batch_form_counter' not in st.session_state:
            st.session_state.batch_form_counter = 0

        batch_df = pd.DataFrame({
            "Name": [""] * 3, "Gender": [""] * 3,
            "Email": [""] * 3, "Paid Fees": [""] * 3
        })

        edited_batch_df = st.data_editor(
            batch_df,
            column_config={
                "Name": st.column_config.TextColumn("Name", required=True, width="medium"),
                "Gender": st.column_config.SelectboxColumn("Gender", options=["M", "F"], required=True, width="small"),
                "Email": st.column_config.TextColumn("Email", help="Valid email address", width="medium"),
                "Paid Fees": st.column_config.SelectboxColumn("Paid Fees", options=["NO", "YES"], width="small"),
            },
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            key=f"batch_student_editor_{st.session_state.batch_form_counter}"
        )

        if st.button("➕ Add Students in Batch", key=f"batch_add_{st.session_state.batch_form_counter}"):
            ActivityTracker.update()
            errors = []
            success_count = 0
            existing_names = {s['student_name'].lower() for s in students}
            processed_names = set()

            for idx, row in edited_batch_df.iterrows():
                name = clean_input(str(row.get("Name", "")), "name")
                gender = str(row.get("Gender", ""))
                email = clean_input(str(row.get("Email", "")), "email")
                school_fees_paid = str(row.get("Paid Fees", ""))

                if not name:
                    continue
                if name.lower() in processed_names:
                    errors.append(f"❌ Row {idx + 1}: Duplicate name '{name}' in batch")
                    continue
                if name.lower() in existing_names:
                    errors.append(f"❌ Row {idx + 1}: '{name}' already enrolled in this class")
                    continue
                if gender not in ["M", "F"]:
                    errors.append(f"❌ Row {idx + 1}: Gender must be 'M' or 'F'")
                    continue
                if email and "@" not in email:
                    errors.append(f"❌ Row {idx + 1}: Invalid email format")
                    continue
                if school_fees_paid not in ["NO", "YES"]:
                    errors.append(f"❌ Row {idx + 1}: Paid Fees must be 'NO' or 'YES'")
                    continue

                create_student(name, gender, email, school_fees_paid)
                enroll_student(name, class_name, session)
                success_count += 1
                processed_names.add(name.lower())
                existing_names.add(name.lower())

            if errors:
                for err in errors:
                    st.error(err)
            if success_count > 0:
                st.markdown(f'<div class="success-container">✅ Successfully added {success_count} student(s)!</div>', unsafe_allow_html=True)
                st.session_state.batch_form_counter += 1
                st.rerun()

    # ── TAB 4: REMOVE STUDENT(S) ──────────────────────────────────────────────
    with tabs[3]:
        if st.session_state.register_students_tab_tracker != 3:
            ActivityTracker.watch_tab("register_students_tabs", 3)
            st.session_state.register_students_tab_tracker = 3

        st.subheader("Remove Student")

        # Unenroll from this class/session (does NOT delete from master registry)
        with st.expander("**Remove Student from This Class**", expanded=True):
            if students:
                student_options = [s['student_name'] for s in students]
                student_to_remove = st.selectbox(
                    "Select student to remove",
                    student_options,
                    key="remove_student_select"
                )
                ActivityTracker.watch_value("remove_student_select_dropdown", student_to_remove)

                if st.button("🚫 Remove from Class", key="unenroll_student"):
                    ActivityTracker.update()

                    @st.dialog("Confirm Removal", width="small")
                    def confirm_unenroll():
                        st.warning(f"⚠️ Remove **{student_to_remove}** from {class_name} ({session})?")
                        st.info("The student record will be preserved in the registry.")
                        c1, c2 = st.columns(2)
                        if c1.button("✅ Remove", key="confirm_unenroll"):
                            ActivityTracker.update()
                            unenroll_student(student_to_remove, class_name, session)
                            st.markdown('<div class="success-container">✅ Student removed from class.</div>', unsafe_allow_html=True)
                            st.rerun()
                        elif c2.button("❌ Cancel", key="cancel_unenroll"):
                            st.info("Cancelled.")
                            st.rerun()
                    confirm_unenroll()
            else:
                st.info("No students available to remove.")

        st.markdown("---")

        # Permanently delete from master registry
        with st.expander("**Delete Student Permanently**", expanded=False):
            st.warning("⚠️ This permanently removes the student from the entire system.")
            if students:
                student_options_del = [s['student_name'] for s in students]
                student_to_delete = st.selectbox(
                    "Select student to delete",
                    student_options_del,
                    key="delete_student_select"
                )

                if st.button("❌ Delete Student Permanently", key="delete_student"):
                    ActivityTracker.update()

                    @st.dialog("Confirm Permanent Deletion", width="small")
                    def confirm_delete_student():
                        st.error(f"⚠️ Permanently delete **{student_to_delete}**?")
                        st.error("All scores, enrollments and records will be deleted.")
                        c1, c2 = st.columns(2)
                        if c1.button("✅ Delete", key="confirm_del_student"):
                            ActivityTracker.update()
                            delete_student(student_to_delete)
                            st.markdown('<div class="success-container">✅ Student deleted.</div>', unsafe_allow_html=True)
                            st.rerun()
                        elif c2.button("❌ Cancel", key="cancel_del_student"):
                            st.info("Cancelled.")
                            st.rerun()
                    confirm_delete_student()
            else:
                st.info("No students available.")
