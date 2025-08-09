import streamlit as st
import pandas as pd
from database import get_all_classes, get_students_by_class, get_subjects_by_class, get_student_scores, get_class_average, get_student_grand_totals
from utils import assign_grade, create_metric_5col, format_ordinal

def generate_broadsheet():
    if not st.session_state.get("authenticated", False):
        st.error("⚠️ Please log in first.")
        st.switch_page("main.py")
        return

    if st.session_state.role not in ["admin", "class_teacher"]:
        st.error("⚠️ Access denied. Admins and Class Teachers only.")
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

    st.markdown(
        """
        <div style='width: auto; margin: auto; text-align: center; background-color: #c6b7b1;'>
            <h3 style='color:#000; font-size:25px; margin-top:30px;'>
                View Broadsheet Data
            </h3>
        </div>
        """,
        unsafe_allow_html=True
    )

    classes = get_all_classes()
    if not classes:
        st.warning("⚠️ No classes found.")
        return

    # Create class display options with all three components
    class_options = [f"{cls['class_name']} - {cls['term']} - {cls['session']}" for cls in classes]
    if role == "class_teacher":
        assignment = st.session_state.get("assignment")
        if not assignment:
            st.error("⚠️ Please select a class assignment first.")
            return
        allowed_class = f"{assignment['class_name']} - {assignment['term']} - {assignment['session']}"
        if allowed_class not in class_options:
            st.error("⚠️ Assigned class not found.")
            return
        class_options = [allowed_class]
        selected_class_display = st.selectbox("Select Class", class_options, disabled=True)
    else:
        selected_class_display = st.selectbox("Select Class", class_options)

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
            row[subject_name] = score_dict.get(subject_name, 0)
        total_score = sum(score_dict.values())
        row["Total"] = total_score
        row["Average"] = round(total_score / len(subjects), 2) if subjects else 0
        row["Grade"] = assign_grade(row["Average"])
        position_data = next((gt for gt in grand_totals if gt['student_name'] == student_name), None)
        row["Position"] = format_ordinal(position_data['position']) if position_data else "-"
        broadsheet_data.append(row)

    # Calculate class average
    class_average = round(broadsheet_data["Average"].mean(), 2)

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

    # Create columns
    create_metric_5col(class_name, term, session, students, class_average)

    df = pd.DataFrame(broadsheet_data)
    st.dataframe(
        df,
        column_config={
            "Student": st.column_config.TextColumn("Student", width="large"),
            "Total": st.column_config.NumberColumn("Total", width="medium"),
            "Average": st.column_config.NumberColumn("Average", width="medium"),
            "Grade": st.column_config.TextColumn("Grade", width="medium"),
            "Position": st.column_config.TextColumn("Position", width="medium")
        },
        hide_index=True,
        use_container_width=True
    )

