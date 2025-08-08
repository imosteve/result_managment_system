import streamlit as st
import pandas as pd
from utils import assign_grade, inject_login_css
from database import (
    get_all_classes, get_students_by_class, get_subjects_by_class,
    get_scores_by_class_subject, save_scores, clear_all_scores
)

def enter_scores():
    # Check authentication
    if not st.session_state.get("authenticated", False):
        st.error("⚠️ Please log in first.")
        st.switch_page("main.py")
        return

    st.set_page_config(page_title="Enter Scores", layout="wide")

    # Custom CSS for better table styling
    inject_login_css("templates/tabs_styles.css")

    st.markdown(
            """
            <div style='width: auto; margin: auto; text-align: center; background-color: #c6b7b1;'>
                <h3 style='color:#000; font-size:30px; margin-top:30px; margin-bottom:10px;'>
                    Manage Subject Scores
                </h3>
            </div>
            """,
            unsafe_allow_html=True
        )
    classes = get_all_classes()
    if not classes:
        st.warning("⚠️ No classes found.")
        return

    # Class selection
    class_options = [f"{cls['class_name']} - {cls['term']} - {cls['session']}" for cls in classes]
    selected_class_display = st.selectbox("Select Class", class_options)
    
    # Get selected class details
    selected_index = class_options.index(selected_class_display)
    selected_class_data = classes[selected_index]
    class_name = selected_class_data['class_name']
    term = selected_class_data['term']
    session = selected_class_data['session']

    subjects = get_subjects_by_class(class_name, term, session)
    if not subjects:
        st.warning(f"⚠️ No subjects found for {class_name} - {term} - {session}.")
        return

    subject_names = [s[1] for s in subjects]
    subject = st.selectbox("Select Subject", subject_names)
    
    students = get_students_by_class(class_name, term, session)
    if not students:
        st.warning(f"⚠️ No students found in {class_name} - {term} - {session}.")
        return

    # Get existing scores for this class and subject
    existing_scores = get_scores_by_class_subject(class_name, subject, term, session)
    score_map = {score[1]: score for score in existing_scores}  # student_name: score_data

    # Tabs for different operations
    tab1, tab2, tab3 = st.tabs(["Enter Scores", "Preview Scores", "Clear All Scores"])

    with tab1:
        st.subheader("Enter Scores")
        # Build editable data
        editable_rows = []
        for student in students:
            student_name = student[1]
            existing = score_map.get(student_name)
            test = existing[3] if existing else 0  # test score
            exam = existing[4] if existing else 0  # exam score

            editable_rows.append({
                "Student": student_name,
                "Test (30%)": test,
                "Exam (70%)": exam,
            })

        # Create editable DataFrame
        editable_df = st.data_editor(
            pd.DataFrame(editable_rows),
            column_config={
                "Student": st.column_config.TextColumn("Student", disabled=True, width="large"),
                "Test (30%)": st.column_config.NumberColumn("Test (30%)", min_value=0, max_value=30, width="medium"),
                "Exam (70%)": st.column_config.NumberColumn("Exam (70%)", min_value=0, max_value=70, width="medium"),
            },
            hide_index=True,
            use_container_width=True,
            key="score_editor"
        )

        if st.button("💾 Save All Scores", key="save_scores"):
            scores_to_save = []
            for _, row in editable_df.iterrows():
                student = row["Student"]
                test = float(row.get("Test (30%)", 0))
                exam = float(row.get("Exam (70%)", 0))
                total = test + exam
                grade = assign_grade(total)

                scores_to_save.append({
                    "student": student,
                    "class": class_name,
                    "subject": subject,
                    "term": term,
                    "session": session,
                    "test": test,
                    "exam": exam,
                    "total": total,
                    "grade": grade
                })

            # Save scores with position calculation
            save_scores(scores_to_save, class_name, subject, term, session)
            st.markdown(f'<div class="success-container">✅ All scores saved successfully for {subject} in {class_name} - {term} - {session}!</div>', unsafe_allow_html=True)
            st.rerun()

    with tab2:
        st.subheader("Preview Scores")
        # Build preview data
        preview_data = []
        for idx, student in enumerate(students, 1):
            student_name = student[1]
            existing = score_map.get(student_name)
            test = existing[3] if existing else 0
            exam = existing[4] if existing else 0
            total = test + exam
            grade = assign_grade(total)
            # Get position from database, format as ordinal (e.g., "1st", "2nd")
            position = format_ordinal(existing[7]) if existing and existing[7] else "-"

            preview_data.append({
                "S/N": str(idx),
                "Student": student_name,
                "Test": test,
                "Exam": exam,
                "Total": total,
                "Grade": grade,
                "Position": position
            })

        st.dataframe(
            pd.DataFrame(preview_data),
            column_config={
                "S/N": st.column_config.TextColumn("S/N", width="small"),
                "Student": st.column_config.TextColumn("Student", width="large"),
                "Test": st.column_config.NumberColumn("Test", width="medium"),
                "Exam": st.column_config.NumberColumn("Exam", width="medium"),
                "Total": st.column_config.NumberColumn("Total", width="medium"),
                "Grade": st.column_config.TextColumn("Grade", width="medium"),
                "Position": st.column_config.TextColumn("Position", width="medium")
            },
            hide_index=True,
            use_container_width=True
        )

    with tab3:
        st.subheader("Clear All Scores")
        st.warning("⚠️ This action will permanently delete all scores for the selected subject in this class. This cannot be undone.")
        
        if existing_scores:
            confirm_clear = st.checkbox("I confirm I want to clear all scores for this subject")
            clear_all_button = st.button("🗑️ Clear All Scores", key="clear_all_scores", disabled=not confirm_clear)
            
            if clear_all_button and confirm_clear:
                success = clear_all_scores(class_name, subject, term, session)
                if success:
                    st.markdown(f'<div class="success-container">✅ All scores cleared successfully for {subject} in {class_name} - {term} - {session}!</div>', unsafe_allow_html=True)
                    st.rerun()
                else:
                    st.markdown('<div class="error-container">❌ Failed to clear scores. Please try again.</div>', unsafe_allow_html=True)
        else:
            st.info("No scores available to clear.")

def format_ordinal(n):
    """Convert number to ordinal string (e.g., 1 -> '1st', 2 -> '2nd')"""
    if not isinstance(n, int):
        return str(n)
    if 10 <= n % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f"{n}{suffix}"