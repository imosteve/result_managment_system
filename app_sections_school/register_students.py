# app_sections/register_students.py

import streamlit as st
import pandas as pd
from database_school import (
    get_all_classes, get_active_session, get_active_term_name,
    get_enrolled_students, enroll_student, unenroll_student,
    create_student, update_student, delete_student,
    open_class_for_session, get_user_assignments,
    get_all_sessions,
    get_classes_for_session)
from main_utils import (
    clean_input, inject_login_css, render_page_header,
    inject_metric_css, render_class_term_session_selector
)
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

    inject_login_css("templates/tabs_styles.css")
    render_page_header("Manage Students Data")

    # ── Session / term context ────────────────────────────────────────────────
    role = st.session_state.role
    _ctx = render_class_term_session_selector("register_students", allow_term_session_override=True)
    if _ctx is None:
        return
    class_name = _ctx["class_name"]
    term       = _ctx["term"]
    session    = _ctx["session"]
    ActivityTracker.watch_value("register_students_class_selector", class_name)

    # ── Ensure class is open for this session ──────────────────────────────────
    open_class_for_session(class_name, session)

    # ── Load enrolled students ─────────────────────────────────────────────────
    students = get_enrolled_students(class_name, session, term)

    inject_metric_css()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Class", class_name)
    col2.metric("Session", session)
    col3.metric("Enrolled Students", len(students))

    # ── Build DataFrame ────────────────────────────────────────────────────────
    df_data = []
    for idx, s in enumerate(students, 1):
        df_data.append({
            "_name": s["student_name"],   # hidden key for edits
            "S/N": str(idx),
            "Name": s["student_name"],
            "Gender": s.get("gender") or "",
            "Email": s.get("email") or "",
            "Admission No": s.get("admission_number") or "",
            "Paid Fees": s.get("school_fees_paid") or "NO",
        })

    df = pd.DataFrame(df_data) if df_data else pd.DataFrame(
        columns=["_name", "S/N", "Name", "Gender", "Email", "Admission No", "Paid Fees"]
    )

    tabs = st.tabs(["👁️ View / Edit", "➕ Add Student", "📋 Batch Add", "🗑️ Remove Student"])

    if "register_students_tab_tracker" not in st.session_state:
        st.session_state.register_students_tab_tracker = 0

    # ── Tab 1: View / Edit ────────────────────────────────────────────────────
    with tabs[0]:
        if st.session_state.register_students_tab_tracker != 0:
            ActivityTracker.watch_tab("register_students_tabs", 0)
            st.session_state.register_students_tab_tracker = 0

        st.subheader("Student List")
        display_df = df[["S/N", "Name", "Gender", "Email", "Admission No", "Paid Fees"]] if not df.empty else \
            pd.DataFrame(columns=["S/N", "Name", "Gender", "Email", "Admission No", "Paid Fees"])
        original_names = df["_name"].tolist() if not df.empty else []

        filtered_df = streamlit_filter(display_df, table_name="students_table")
        edited_df = st.data_editor(
            filtered_df,
            column_config={
                "S/N": st.column_config.TextColumn("S/N", disabled=True, width=20),
                "Name": st.column_config.TextColumn("Name", required=True, width=250),
                "Gender": st.column_config.SelectboxColumn("Gender", options=["M", "F"], width=70),
                "Email": st.column_config.TextColumn("Email", width=200),
                "Admission No": st.column_config.TextColumn("Admission No", width=100),
                "Paid Fees": st.column_config.SelectboxColumn("Paid Fees", options=["NO", "YES"], width=80),
            },
            hide_index=True,
            width="stretch",
            key="student_editor",
            height=35 * len(filtered_df) + 38 if len(filtered_df) > 0 else 80,
        )

        if st.button("💾 Save Changes", key="save_changes"):
            ActivityTracker.update()
            errors, success_count = [], 0
            for idx, row in edited_df.iterrows():
                try:
                    old_name = original_names[idx]
                except IndexError:
                    errors.append(f"❌ Row {idx + 1}: Cannot determine student — skipped.")
                    continue
                new_name      = clean_input(str(row.get("Name", "") or ""), "name")
                _gender_raw   = row.get("Gender") or ""
                gender        = str(_gender_raw).strip() if str(_gender_raw).strip() in ("M", "F") else ""
                _email_raw    = row.get("Email") or ""
                email         = clean_input(str(_email_raw).strip(), "email") or None
                admission_no  = clean_input(str(row.get("Admission No", "") or ""), "name")
                fees_paid     = str(row.get("Paid Fees", "") or "")
                if not new_name:
                    errors.append(f"❌ Row {idx + 1}: Name is required")
                    continue
                if gender and gender not in ["M", "F"]:
                    errors.append(f"❌ Row {idx + 1}: Gender must be M or F")
                    continue
                try:
                    update_student(
                        old_name,
                        new_name=new_name if new_name != old_name else None,
                        gender=gender or None,
                        email=email,
                        admission_number=admission_no or None,
                        school_fees_paid=fees_paid or None,
                    )
                    success_count += 1
                except Exception as e:
                    logger.error(f"Failed to update student '{old_name}': {e}")
                    errors.append(f"❌ Row {idx + 1}: Failed to update '{old_name}'")
            for err in errors:
                st.error(err)
            if success_count:
                st.success(f"✅ Updated {success_count} student(s)!")
                st.rerun()

    # ── Tab 2: Add Student ────────────────────────────────────────────────────
    with tabs[1]:
        if st.session_state.register_students_tab_tracker != 1:
            ActivityTracker.watch_tab("register_students_tabs", 1)
            st.session_state.register_students_tab_tracker = 1

        st.subheader("Add New Student")
        if "student_form_counter" not in st.session_state:
            st.session_state.student_form_counter = 0

        with st.form(f"add_student_form_{st.session_state.student_form_counter}"):
            new_name         = st.text_input("Name", placeholder="Enter student name")
            new_gender       = st.selectbox("Gender", ["M", "F"])
            new_email        = st.text_input("Email (optional)", placeholder="student@example.com")
            new_admission_no = st.text_input("Admission Number (optional)")
            fees_paid        = st.selectbox("Paid Fees", ["NO", "YES"])
            submit_button    = st.form_submit_button("➕ Add Student")
            ActivityTracker.watch_form(submit_button)

            if submit_button:
                errors = []
                new_name = clean_input(new_name, "name")
                if not new_name:
                    errors.append("❌ Name is required")
                existing_names = {s["student_name"].lower() for s in students}
                if new_name.lower() in existing_names:
                    errors.append("❌ A student with this name is already enrolled in this class")
                if errors:
                    for err in errors:
                        st.error(err)
                else:
                    # create in master registry if not already there, then enroll
                    create_student(new_name, new_gender,
                                   email=new_email.strip() or None,
                                   admission_number=new_admission_no or None,
                                   school_fees_paid=fees_paid)
                    ok, reason = enroll_student(new_name, class_name, session, term)
                    if ok:
                        st.success("✅ Student added and enrolled successfully!")
                        st.session_state.student_form_counter += 1
                        st.rerun()
                    else:
                        st.error(f"❌ Enrollment failed: {reason}")

    # ── Tab 3: Batch Add ──────────────────────────────────────────────────────
    with tabs[2]:
        if st.session_state.register_students_tab_tracker != 2:
            ActivityTracker.watch_tab("register_students_tabs", 2)
            st.session_state.register_students_tab_tracker = 2

        st.subheader("Batch Add Students")
        st.markdown("Enter multiple students below. Each row = one student.")
        if "batch_form_counter" not in st.session_state:
            st.session_state.batch_form_counter = 0

        batch_df = pd.DataFrame({"Name": [""]*3, "Gender": [""]*3,
                                  "Email": [""]*3, "Admission No": [""]*3, "Paid Fees": [""]*3})
        edited_batch_df = st.data_editor(
            batch_df,
            column_config={
                "Name": st.column_config.TextColumn("Name", required=True, width="medium"),
                "Gender": st.column_config.SelectboxColumn("Gender", options=["M", "F"], width="small"),
                "Email": st.column_config.TextColumn("Email", width="medium"),
                "Admission No": st.column_config.TextColumn("Admission No", width="medium"),
                "Paid Fees": st.column_config.SelectboxColumn("Paid Fees", options=["NO", "YES"], width="small"),
            },
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            key=f"batch_student_editor_{st.session_state.batch_form_counter}",
        )

        if st.button("➕ Add Students in Batch", key=f"batch_add_{st.session_state.batch_form_counter}"):
            ActivityTracker.update()
            errors, success_count = [], 0
            existing_names = {s["student_name"].lower() for s in students}
            processed_names = set()

            batch_names = edited_batch_df["Name"].str.lower().str.strip()
            dup_mask = batch_names.duplicated(keep=False) & (batch_names != "")
            if dup_mask.any():
                dup_rows = edited_batch_df[dup_mask].index + 1
                errors.append(f"❌ Duplicate names in batch at rows: {', '.join(map(str, dup_rows))}")

            for idx, row in edited_batch_df.iterrows():
                name         = clean_input(str(row.get("Name", "") or ""), "name")
                _gender_raw  = row.get("Gender") or ""
                gender       = str(_gender_raw).strip() if str(_gender_raw).strip() in ("M", "F") else ""
                _email_raw   = row.get("Email") or ""
                email        = clean_input(str(_email_raw).strip(), "email") or None
                admission_no = clean_input(str(row.get("Admission No", "") or ""), "name")
                _fees_raw    = row.get("Paid Fees") or "NO"
                fees_paid    = str(_fees_raw) if str(_fees_raw) in ("YES", "NO") else "NO"
                if not name:
                    continue
                if name.lower() in processed_names:
                    errors.append(f"❌ Row {idx+1}: Duplicate name '{name}'")
                    continue
                if name.lower() in existing_names:
                    errors.append(f"❌ Row {idx+1}: '{name}' already enrolled in this class")
                    continue
                if gender and gender not in ["M", "F"]:
                    errors.append(f"❌ Row {idx+1}: Gender must be M or F")
                    continue
                create_student(name, gender or None,
                               email=email,
                               admission_number=admission_no or None,
                               school_fees_paid=fees_paid or "NO")
                ok, reason = enroll_student(name, class_name, session, term)
                if ok:
                    success_count += 1
                    processed_names.add(name.lower())
                    existing_names.add(name.lower())
                else:
                    errors.append(f"❌ Row {idx+1}: Enrollment failed for '{name}': {reason}")

            for err in errors:
                st.error(err)
            if success_count:
                st.success(f"✅ Added and enrolled {success_count} student(s)!")
                st.session_state.batch_form_counter += 1
                st.rerun()

    # ── Tab 4: Remove Student ─────────────────────────────────────────────────
    with tabs[3]:
        if st.session_state.register_students_tab_tracker != 3:
            ActivityTracker.watch_tab("register_students_tabs", 3)
            st.session_state.register_students_tab_tracker = 3

        st.subheader("Remove Student from Class")
        st.info("**Unenroll** removes the student from this class-session only (scores and other data are lost for this session). "
                "The student remains in the master registry.")

        if not students:
            st.info("No students enrolled in this class.")
        else:
            # ── Unenroll single student ────────────────────────────────────────
            with st.expander("**Unenroll Single Student**", expanded=True):
                student_options = [s["student_name"] for s in students]
                student_to_remove = st.selectbox("Select student to unenroll",
                                                 student_options, key="unenroll_student_select")
                ActivityTracker.watch_value("unenroll_student_dropdown", student_to_remove)

                if st.button("❌ Unenroll Student", key="unenroll_student_btn"):
                    ActivityTracker.update()

                    @st.dialog("Confirm Unenrollment", width="small")
                    def confirm_unenroll():
                        st.warning(f"⚠️ Remove **{student_to_remove}** from **{class_name}** / **{session}**?")
                        st.error("This will permanently delete all their scores, comments, and subject selections for this session.")
                        c1, c2 = st.columns(2)
                        if c1.button("✅ Unenroll", key="confirm_unenroll_ok"):
                            ActivityTracker.update()
                            if unenroll_student(student_to_remove, class_name, session, term):
                                st.success("✅ Student unenrolled.")
                            else:
                                st.error("❌ Failed to unenroll student.")
                            st.rerun()
                        if c2.button("🚫 Cancel", key="confirm_unenroll_cancel"):
                            st.rerun()

                    confirm_unenroll()

            st.markdown("---")

            # ── Unenroll all ──────────────────────────────────────────────────
            with st.expander("**Unenroll ALL Students from this Class-Session**", expanded=False):
                st.warning("⚠️ This permanently removes every student's enrollment, scores, comments, and subject selections for this class-session.")
                confirm_all = st.checkbox("I understand and confirm I want to unenroll ALL students")
                ActivityTracker.watch_value("confirm_unenroll_all_checkbox", confirm_all)
                if st.button("🗑️ Unenroll All", key="unenroll_all_btn", disabled=not confirm_all):
                    ActivityTracker.update()

                    @st.dialog("Confirm Unenroll All", width="small")
                    def confirm_unenroll_all():
                        st.warning(f"Remove ALL {len(students)} students from **{class_name}** / **{session}**?")
                        c1, c2 = st.columns(2)
                        if c1.button("✅ Unenroll All", key="confirm_unenroll_all_ok"):
                            ActivityTracker.update()
                            removed = 0
                            for s in students:
                                if unenroll_student(s["student_name"], class_name, session, term):
                                    removed += 1
                            st.success(f"✅ Unenrolled {removed} student(s).")
                            st.rerun()
                        if c2.button("🚫 Cancel", key="confirm_unenroll_all_cancel"):
                            st.rerun()

                    confirm_unenroll_all()