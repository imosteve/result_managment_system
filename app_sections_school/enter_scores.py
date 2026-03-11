# app_sections/enter_scores.py

import streamlit as st
import pandas as pd
import logging
import re
from typing import Optional, List, Dict, Any
from main_utils import (
    assign_grade, inject_login_css, format_ordinal, render_page_header,
    inject_metric_css, render_class_term_session_selector
)
from database_school import (
    get_active_session, get_active_term_name, get_classes_for_session,
    get_subjects_by_class, get_enrolled_students,
    get_scores_for_subject, save_score, delete_scores_for_term,
    get_student_selected_subjects, get_user_assignments,
    get_all_sessions,
    get_all_classes)
from auth.activity_tracker import ActivityTracker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def enter_scores():
    """Main function to handle score entry with role-based access control"""
    try:
        if not _check_authentication():
            return
        if not _check_authorization():
            return

        ActivityTracker.init()
        _initialize_session_state()

        st.set_page_config(page_title="Enter Scores", layout="wide")
        inject_login_css("templates/tabs_styles.css")
        render_page_header("Manage Subject Scores")

        _render_score_management_interface()

    except Exception as e:
        logger.error(f"Error in enter_scores: {str(e)}")
        st.error("❌ An unexpected error occurred. Please try again or contact support.")


def _check_authentication() -> bool:
    if not st.session_state.get("authenticated", False):
        st.error("⚠️ Please log in first.")
        st.switch_page("main.py")
        return False
    return True


def _check_authorization() -> bool:
    allowed_roles = ["superadmin", "admin", "class_teacher", "subject_teacher"]
    if st.session_state.get("role") not in allowed_roles:
        st.error("⚠️ Access denied.")
        return False
    return True


def _initialize_session_state():
    for key in ['user_id', 'role', 'assignment']:
        if key not in st.session_state:
            st.session_state[key] = None


def _render_score_management_interface():
    user_id = st.session_state.user_id
    role = st.session_state.role

    # ── Session / term context ────────────────────────────────────────────────
    _ctx = render_class_term_session_selector("enter_scores", allow_term_session_override=True)
    if _ctx is None:
        return
    class_name = _ctx["class_name"]
    term       = _ctx["term"]
    session    = _ctx["session"]
    ActivityTracker.watch_value("enter_scores_class", f"{class_name}_{session}_{term}")

    subjects = _get_accessible_subjects(class_name, user_id, role)
    if not subjects:
        st.warning(f"⚠️ No subjects found or assigned to you for {class_name}.")
        return

    selected_subject = _render_subject_selection(subjects)
    if not selected_subject:
        return

    is_senior_class = bool(re.match(r"SSS [23].*$", class_name))

    students = _get_accessible_students(class_name, session, term, user_id, role, selected_subject, is_senior_class)
    if not students:
        if is_senior_class:
            st.warning(f"⚠️ No students have selected {selected_subject} in {class_name}.")
            st.info("💡 Students need to make subject selections in 'Manage Subject Combination' first.")
        else:
            st.warning(f"⚠️ No students found in {class_name}.")
        return

    existing_scores = _get_existing_scores(class_name, selected_subject, session, term)

    if is_senior_class:
        st.info(f"Showing {len(students)} student(s) who selected {selected_subject}")

    _render_score_tabs(students, existing_scores, class_name, selected_subject, session, term)


def _render_class_selection(classes, role) -> Optional[str]:
    class_names = [c['class_name'] for c in classes]
    selected = st.selectbox("Select Class", class_names, key="enter_scores_class")
    return selected


def _get_accessible_subjects(class_name: str, user_id: int, role: str) -> list:
    try:
        # New schema: get_subjects_by_class(class_name) — no term/session
        all_subjects = get_subjects_by_class(class_name)

        if role in ["superadmin", "admin", "class_teacher"]:
            return all_subjects

        # subject_teacher — filter to assigned subjects only
        if role == "subject_teacher":
            assignments = get_user_assignments(user_id)
            assigned_subjects = {
                a['subject_name'] for a in assignments
                if a.get('assignment_type') == 'subject_teacher'
                and a.get('class_name') == class_name
                and a.get('subject_name')
            }
            return [s for s in all_subjects if
                    (s['subject_name'] if isinstance(s, dict) else s[1]) in assigned_subjects]

        return []
    except Exception as e:
        logger.error(f"Error fetching subjects: {str(e)}")
        st.error("❌ Failed to load subjects.")
        return []


def _render_subject_selection(subjects: list) -> Optional[str]:
    subject_names = [
        s['subject_name'] if isinstance(s, dict) else s[1]
        for s in subjects
    ]
    selected = st.selectbox("Select Subject", subject_names)
    ActivityTracker.watch_value("enter_scores_subject", selected)
    return selected


def _get_accessible_students(class_name: str, session: str, term: str,
                              user_id: int, role: str,
                              subject_name: str, is_senior_class: bool) -> list:
    try:
        # New schema: get_enrolled_students(class_name, session) → [{student_name,...}]
        all_students = get_enrolled_students(class_name, session)

        if is_senior_class and subject_name:
            filtered = []
            seen = set()
            for student in all_students:
                sn = student['student_name'] if isinstance(student, dict) else student[1]
                if sn in seen:
                    continue
                # New schema: get_student_selected_subjects(name, class_name, session, term)
                sels = get_student_selected_subjects(sn, class_name, session, term)
                if subject_name in sels:
                    filtered.append(student)
                    seen.add(sn)
            return filtered

        return all_students
    except Exception as e:
        logger.error(f"Error fetching students: {str(e)}")
        st.error("❌ Failed to load students.")
        return []


def _get_existing_scores(class_name: str, subject: str, session: str, term: str) -> Dict:
    try:
        # New schema: get_scores_for_subject(class_name, session, term, subject_name)
        scores = get_scores_for_subject(class_name, session, term, subject)
        # returns list of dicts with student_name, ca_score, exam_score, total_score
        return {
            (s['student_name'] if isinstance(s, dict) else s[1]): s
            for s in scores
        }
    except Exception as e:
        logger.error(f"Error fetching scores: {str(e)}")
        return {}


def _render_score_tabs(students, score_map, class_name, subject, session, term):
    tab1, tab2, tab3 = st.tabs(["Enter Scores", "Preview Scores", "Clear All Scores"])

    active_tab = st.session_state.get("enter_scores_active_tab", 0)
    ActivityTracker.watch_tab("enter_scores", active_tab)

    with tab1:
        st.session_state.enter_scores_active_tab = 0
        _render_score_entry_tab(students, score_map, class_name, subject, session, term)

    with tab2:
        st.session_state.enter_scores_active_tab = 1
        _render_score_preview_tab(students, score_map)

    with tab3:
        st.session_state.enter_scores_active_tab = 2
        _render_clear_scores_tab(score_map, class_name, subject, session, term)


def _validate_scores(df: pd.DataFrame) -> Dict:
    errors = []
    try:
        for idx, row in df.iterrows():
            student_name = row['Student']
            ca = float(row.get("CA (30%)", 0))
            exam = float(row.get("Exam (70%)", 0))
            if ca < 0:
                errors.append(f"❌ {idx+1} - {student_name}: CA score cannot be negative ({ca:.1f})")
            elif ca > 30:
                errors.append(f"❌ {idx+1} - {student_name}: CA score exceeds max of 30 ({ca:.1f})")
            if exam < 0:
                errors.append(f"❌ {idx+1} - {student_name}: Exam score cannot be negative ({exam:.1f})")
            elif exam > 70:
                errors.append(f"❌ {idx+1} - {student_name}: Exam score exceeds max of 70 ({exam:.1f})")
        return {"valid": len(errors) == 0, "errors": errors}
    except Exception as e:
        return {"valid": False, "errors": [f"❌ Validation error: {str(e)}"]}


def _save_scores_to_database(df: pd.DataFrame, class_name: str, subject: str, session: str, term: str):
    try:
        user_id = st.session_state.get('user_id')
        for _, row in df.iterrows():
            student = row["Student"]
            ca = float(row.get("CA (30%)", 0))
            exam = float(row.get("Exam (70%)", 0))
            total = ca + exam
            grade = assign_grade(total)
            # New schema: save_score(student_name, class_name, session, term, subject_name, ca_score, exam_score, grade, updated_by)
            save_score(student, class_name, session, term, subject, ca, exam, grade, user_id)

        st.success(f"✅ Scores saved for {subject} in {class_name} - {term} - {session}!")
        logger.info(f"Scores saved for {subject} in {class_name} - {term} - {session}")
        st.rerun()
    except Exception as e:
        logger.error(f"Error saving scores: {str(e)}")
        st.error("❌ Failed to save scores. Please try again.")


def _render_score_preview_tab(students, score_map):
    st.subheader("Preview Scores")
    if not students:
        st.info("No students available.")
        return

    preview_data = {}
    for idx, student in enumerate(students, 1):
        sn = student['student_name'] if isinstance(student, dict) else student[1]
        if sn in preview_data:
            continue

        existing = score_map.get(sn)
        if existing:
            ca = int(existing['ca_score'] if isinstance(existing, dict) else existing[3] or 0)
            exam = int(existing['exam_score'] if isinstance(existing, dict) else existing[4] or 0)
            total = int(existing['total_score'] if isinstance(existing, dict) else existing[5] or ca + exam)
            grade = assign_grade(total)
        else:
            ca = exam = total = 0
            grade = assign_grade(0)

        preview_data[sn] = {
            "S/N": str(idx), "Student": sn,
            "CA": str(ca), "Exam": str(exam), "Total": str(total), "Grade": grade
        }

    st.dataframe(
        pd.DataFrame(list(preview_data.values())),
        column_config={
            "S/N": st.column_config.TextColumn("S/N", width="small"),
            "Student": st.column_config.TextColumn("Student", width="medium"),
            "CA": st.column_config.TextColumn("CA", width="small"),
            "Exam": st.column_config.TextColumn("Exam", width="small"),
            "Total": st.column_config.TextColumn("Total", width="small"),
            "Grade": st.column_config.TextColumn("Grade", width="small"),
        },
        hide_index=True, width="stretch",
        height=35 * len(preview_data) + 38
    )


def _render_clear_scores_tab(score_map, class_name, subject, session, term):
    st.subheader("🗑️ Clear All Scores")
    st.warning("⚠️ **DANGER ZONE**: Permanently deletes all scores for this subject/term. Cannot be undone.")

    if score_map:
        st.info(f"📊 Found {len(score_map)} student scores to be cleared.")
        confirm_clear = st.checkbox("I understand this action cannot be undone")
        ActivityTracker.watch_value("confirm_clear_scores", confirm_clear)

        confirm_text = st.text_input("Type 'DELETE' to confirm:", placeholder="Type DELETE to confirm")
        if confirm_text:
            ActivityTracker.watch_value("confirm_delete_text", confirm_text)

        is_confirmed = confirm_clear and confirm_text.strip().upper() == "DELETE"

        if st.button("🗑️ Clear All Scores", key="clear_all_scores", disabled=not is_confirmed, type="secondary"):
            ActivityTracker.update()
            try:
                # New schema: delete_scores_for_term(class_name, session, term)
                # This clears scores for the entire term; subject-specific clear not available in new schema
                delete_scores_for_term(class_name, session, term)
                st.success(f"✅ Scores cleared for {class_name} - {term} - {session}!")
                st.rerun()
            except Exception as e:
                logger.error(f"Error clearing scores: {str(e)}")
                st.error("❌ Failed to clear scores. Please try again.")
    else:
        st.info("No scores available to clear.")


def resolve_device_mode(choice: str) -> bool:
    if choice == "Mobile":
        return True
    return False


def _render_score_entry_tab(students, score_map, class_name, subject, session, term):
    """Smart rendering based on device type"""
    with st.sidebar.expander("📱 View Mode"):
        device_mode = st.radio(
            "📱 View Mode",
            ["Desktop", "Mobile"],
            index=0,
            horizontal=True,
            label_visibility="collapsed",
            width="stretch"
        )
        ActivityTracker.watch_value("score_entry_view_mode", device_mode)

    is_mobile = resolve_device_mode(device_mode)

    if is_mobile:
        _render_mobile_score_entry(students, score_map, class_name, subject, session, term)
    else:
        _render_desktop_score_entry(students, score_map, class_name, subject, session, term)


def _render_mobile_score_entry(students, score_map, class_name, subject, session, term):
    """Mobile-optimized individual student entry"""
    if 'current_student_idx' not in st.session_state:
        st.session_state.current_student_idx = 0

    total_students = len(students)
    current_idx = st.session_state.current_student_idx
    if current_idx >= total_students:
        st.session_state.current_student_idx = 0
        current_idx = 0

    student = students[current_idx]
    student_name = student['student_name'] if isinstance(student, dict) else student[1]

    st.markdown(f"#### {student_name}")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("⬅️ Prev", disabled=current_idx == 0, width="stretch"):
            st.session_state.current_student_idx -= 1
            st.rerun()
    with col2:
        st.markdown(f"<h4 style='text-align:center;'>{current_idx + 1} of {total_students} students</h4>", unsafe_allow_html=True)
    with col3:
        if st.button("Next ➡️", disabled=current_idx >= total_students - 1, width="stretch"):
            st.session_state.current_student_idx += 1
            st.rerun()

    st.markdown(" ")

    with st.container(key=f"mobile_score_{current_idx}", border=True):
        st.markdown("##### Enter Scores")

        existing = score_map.get(student_name)
        current_ca = float(existing['ca_score'] if isinstance(existing, dict) else (existing[3] or 0)) if existing else 0.0
        current_exam = float(existing['exam_score'] if isinstance(existing, dict) else (existing[4] or 0)) if existing else 0.0

        col1, col2, col3 = st.columns(3, vertical_alignment="bottom")
        with col1:
            ca_score = st.number_input(
                "CA Score", min_value=0.0, max_value=30.0,
                value=current_ca, step=0.5,
                key=f"mobile_ca_{current_idx}_{student_name}",
                help="CA (0-30)"
            )
        with col2:
            exam_score = st.number_input(
                "Exam Score", min_value=0.0, max_value=70.0,
                value=current_exam, step=0.5,
                key=f"mobile_exam_{current_idx}_{student_name}",
                help="Exam (0-70)"
            )

        total = ca_score + exam_score
        grade = assign_grade(total)

        with col3:
            if st.button("💾 Save", type="primary", width="stretch"):
                _save_single_student_score(student_name, class_name, subject, session, term, ca_score, exam_score, grade)
                st.success(f"✅ Saved {student_name}'s scores!")
                st.rerun()

        st.markdown(" ")
        inject_metric_css()
        st.markdown("##### Quick Score Preview")
        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric("CA", f"{ca_score:.1f}/30")
        with col2: st.metric("Exam", f"{exam_score:.1f}/70")
        with col3: st.metric("Total", f"{total:.1f}/100")
        with col4: st.metric("Grade", grade)

        st.markdown(" ")
        st.markdown("##### Quick Jump to Student")
        col1_1, col2_2 = st.columns([3, 1], vertical_alignment="bottom")
        with col1_1:
            jump_options = []
            for i, stud in enumerate(students):
                sn = stud['student_name'] if isinstance(stud, dict) else stud[1]
                has_scores = sn in score_map and (
                    score_map[sn]['ca_score'] if isinstance(score_map[sn], dict) else score_map[sn][3]
                ) is not None
                status = "✅" if has_scores else "⭕"
                jump_options.append(f"{status} {i+1}. {sn}")

            selected_jump = st.selectbox(
                "Select student:",
                range(total_students),
                format_func=lambda i: jump_options[i],
                key="mobile_jump_selector"
            )
        with col2_2:
            if st.button("Jump", width="stretch"):
                st.session_state.current_student_idx = selected_jump
                st.rerun()

    completed = sum(
        1 for s in students
        if (s['student_name'] if isinstance(s, dict) else s[1]) in score_map
        and (score_map[(s['student_name'] if isinstance(s, dict) else s[1])].get('ca_score')
             if isinstance(score_map.get(s['student_name'] if isinstance(s, dict) else s[1]), dict)
             else None) is not None
    )
    st.caption(f"📊 Completed: {completed}/{total_students} students")


def _render_desktop_score_entry(students, score_map, class_name, subject, session, term):
    st.subheader("Enter Scores")
    if not students:
        st.warning("⚠️ No students available.")
        return

    st.info("📊 **Score Limits:** CA (0-30) | Exam (0-70) | Total (0-100)")

    student_scores = {}
    for idx, student in enumerate(students, 1):
        sn = student['student_name'] if isinstance(student, dict) else student[1]
        if sn in student_scores:
            continue
        existing = score_map.get(sn)
        ca = float(existing['ca_score'] if isinstance(existing, dict) else (existing[3] or 0)) if existing else 0.0
        exam = float(existing['exam_score'] if isinstance(existing, dict) else (existing[4] or 0)) if existing else 0.0
        student_scores[sn] = {"S/N": str(idx), "Student": sn, "CA (30%)": ca, "Exam (70%)": exam}

    editable_rows = list(student_scores.values())

    try:
        editable_df = st.data_editor(
            pd.DataFrame(editable_rows),
            column_config={
                "S/N": st.column_config.TextColumn("S/N", disabled=True, width=20),
                "Student": st.column_config.TextColumn("Student", disabled=True, width=200),
                "CA (30%)": st.column_config.NumberColumn("CA (30%)", width="small", format="%d"),
                "Exam (70%)": st.column_config.NumberColumn("Exam (70%)", width="small", format="%d"),
            },
            hide_index=True, width="stretch",
            key=f"score_editor_{class_name}_{subject}_{session}_{term}",
            height=35 * len(editable_rows) + 38,
            on_change=ActivityTracker.update
        )

        validation = _validate_scores(editable_df)
        if validation["valid"]:
            if st.button("💾 Save All Scores", key="save_scores", type="primary"):
                ActivityTracker.update()
                _save_scores_to_database(editable_df, class_name, subject, session, term)
        else:
            for error in validation["errors"]:
                st.error(error)
            st.warning("⚠️ Please correct errors before saving.")

    except Exception as e:
        logger.error(f"Error in score entry: {str(e)}")
        st.error("❌ Error creating score entry interface.")


def _save_single_student_score(student_name, class_name, subject, session, term, ca, exam, grade):
    try:
        user_id = st.session_state.get('user_id')
        # New schema: save_score(student_name, class_name, session, term, subject_name, ca_score, exam_score, grade, updated_by)
        save_score(student_name, class_name, session, term, subject, ca, exam, grade, user_id)
        return True
    except Exception as e:
        logger.error(f"Error saving single score: {str(e)}")
        st.error(f"❌ Failed to save: {str(e)}")
        return False


if __name__ == "__main__":
    enter_scores()