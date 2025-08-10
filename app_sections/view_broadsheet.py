import streamlit as st
import pandas as pd
from database import get_all_classes, get_students_by_class, get_subjects_by_class, get_student_scores, get_student_grand_totals
from utils import assign_grade, create_metric_5col_broadsheet, format_ordinal, render_page_header

def generate_broadsheet():
    if not st.session_state.get("authenticated", False):
        st.error("⚠️ Please log in first.")
        st.switch_page("main.py")
        return

    if st.session_state.role not in ["superadmin", "admin", "class_teacher", "subject_teacher"]:
        st.error("⚠️ Access denied.")
        return

    user_id = st.session_state.user_id
    role = st.session_state.role

    st.set_page_config(page_title="View Broadsheet", layout="wide")

    st.markdown("""
        <style>
        .stDataFrame {
            border-radius: 8px;
            overflow: hidden;
        }
        .error-container {
            background-color: #ffebee;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 10px;
        }
        </style>
    """, unsafe_allow_html=True)

    # Subheader
    render_page_header("View Broadsheet Data")

    classes = get_all_classes(user_id, role)
    if not classes:
        st.warning("⚠️ Please create at least one class first.")
        if role in ["class_teacher", "subject_teacher"]:
            st.info("You may need to select a class assignment in the 'Change Assignment' section.")
        return

    # Select class
    class_options = [f"{cls['class_name']} - {cls['term']} - {cls['session']}" for cls in classes]
    if role in ["class_teacher", "subject_teacher"]:
        assignment = st.session_state.get("assignment")
        if not assignment:
            st.warning("⚠️ No class assignment selected. Please select a class in the 'Change Assignment' section.")
            class_options = []  # Prevent class selection until assignment is set
            selected_class_display = None
        else:
            allowed_class = f"{assignment['class_name']} - {assignment['term']} - {assignment['session']}"
            if allowed_class not in class_options:
                st.error("⚠️ Assigned class not found in available classes. Please select a new assignment.")
                return
            class_options = [allowed_class]
            selected_class_display = st.selectbox("Select Class", class_options, disabled=True)
    else:
        selected_class_display = st.selectbox("Select Class", class_options)

    if not class_options:
        return
    
    # Find the selected class data
    selected_index = class_options.index(selected_class_display)
    selected_class_data = classes[selected_index]
    class_name = selected_class_data['class_name']
    term = selected_class_data['term']
    session = selected_class_data['session']

    students = get_students_by_class(class_name, term, session, user_id, role)
    if not students:
        st.warning(f"⚠️ No students found for {class_name} - {term} - {session}.")
        return

    subjects = get_subjects_by_class(class_name, term, session, user_id, role)
    if not subjects:
        st.warning(f"⚠️ No subjects found for {class_name} - {term} - {session}.")
        return

    broadsheet_data = []
    grand_totals = get_student_grand_totals(class_name, term, session, user_id, role)

    for student in students:
        student_name = student[1]
        scores = get_student_scores(student_name, class_name, term, session, user_id, role)
        score_dict = {score[2]: score[5] for score in scores}
        row = {"Student": student_name}
        for subject in subjects:
            subject_name = subject[1]
            row[subject_name] = score_dict.get(subject_name, "-")  # Changed from 0 to "-"
        # Only sum numeric values for total
        numeric_scores = [v for v in score_dict.values() if isinstance(v, (int, float))]
        total_score = sum(numeric_scores)
        row["Total"] = total_score if numeric_scores else "-"
        row["Average"] = round(total_score / len(numeric_scores), 2) if numeric_scores else "-"
        row["Grade"] = assign_grade(row["Average"]) if isinstance(row["Average"], (int, float)) else "-"
        position_data = next((gt for gt in grand_totals if gt['student_name'] == student_name), None)
        row["Position"] = format_ordinal(position_data['position']) if position_data else "-"
        broadsheet_data.append(row)

    # Calculate class average
    df = pd.DataFrame(broadsheet_data)
    # Only calculate class average from numeric values
    numeric_averages = [row["Average"] for row in broadsheet_data if isinstance(row["Average"], (int, float))]
    class_average = round(sum(numeric_averages) / len(numeric_averages), 2) if numeric_averages else 0
    
    # Display class summary
    st.markdown(
        """
        <div style='width: auto; margin: auto; text-align: center; background-color: #c6b7b1;'>
            <h3 style='color:#000; font-size:20px; margin-top:10px; margin-bottom:20px;'>
                📊 Class Summary
            </h3>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Create columns with expanded metrics
    create_metric_5col_broadsheet(subjects, students, class_average, broadsheet_data, class_name, term, session, user_id, role)

    df = pd.DataFrame(broadsheet_data)
    st.dataframe(
        df,
        column_config={
            "Student": st.column_config.TextColumn("Student", width="large"),
            "Total": st.column_config.TextColumn("Total", width="medium"),
            "Average": st.column_config.TextColumn("Average", width="medium"),
            "Grade": st.column_config.TextColumn("Grade", width="medium"),
            "Position": st.column_config.TextColumn("Position", width="medium")
        },
        hide_index=True,
        use_container_width=True
    )