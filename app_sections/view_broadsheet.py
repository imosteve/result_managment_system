# app_sections/view_broadsheet.py

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
    
    selected_class_display = st.selectbox("Select Class", class_options)

    if not class_options:
        return
    
    # Find the selected class data
    selected_index = class_options.index(selected_class_display)
    selected_class_data = classes[selected_index]
    class_name = selected_class_data['class_name']
    term = selected_class_data['term']
    session = selected_class_data['session']

    students = get_students_by_class(class_name, term, session, user_id, "admin")
    if not students:
        st.warning(f"⚠️ No students found for {class_name} - {term} - {session}.")
        return

    subjects = get_subjects_by_class(class_name, term, session, user_id, "admin")
    if not subjects:
        st.warning(f"⚠️ No subjects found for {class_name} - {term} - {session}.")
        return

    broadsheet_data = []
    grand_totals = get_student_grand_totals(class_name, term, session, user_id, "admin")

    for idx, student in enumerate(students, 1):
        student_name = student[1]
        scores = get_student_scores(student_name, class_name, term, session, user_id, "admin")
        
        # Create dictionaries for test, exam, and total scores
        test_scores = {}
        exam_scores = {}
        total_scores = {}
        
        for score in scores:
            subject_name = score[2]
            test_scores[subject_name] = str(int(score[3])) if score[3] is not None else "-"
            exam_scores[subject_name] = str(int(score[4])) if score[4] is not None else "-"
            total_scores[subject_name] = str(int(score[5])) if score[5] is not None else "-"
        
        row = {"S/N": str(idx), "Student": student_name}
        
        # Add Test, Exam, and Total columns for each subject
        for subject in subjects:
            subject_name = subject[1]
            row[f"{subject_name} (Test)"] = test_scores.get(subject_name, "-")
            row[f"{subject_name} (Exam)"] = exam_scores.get(subject_name, "-")
            row[f"{subject_name} (Total)"] = total_scores.get(subject_name, "-")
        
        # Calculate grand total (sum of all subject totals)
        numeric_totals = [int(v) for v in total_scores.values() if v != "-"]
        grand_total = str(sum(numeric_totals)) if numeric_totals else "-"
        row["Grand Total"] = grand_total
        
        # Calculate average
        if grand_total != "-" and numeric_totals:
            avg = round(int(grand_total) / len(numeric_totals), 2)
            row["Average"] = str(avg)
        else:
            row["Average"] = "-"
        
        # Get position
        position_data = next((gt for gt in grand_totals if gt['student_name'] == student_name), None)
        row["Position"] = format_ordinal(position_data['position']) if position_data else "-"
        
        broadsheet_data.append(row)

    # Calculate class average
    numeric_averages = []
    for row in broadsheet_data:
        avg = row["Average"]
        if avg != "-":
            numeric_averages.append(float(avg))
    
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
    create_metric_5col_broadsheet(subjects, students, class_average, broadsheet_data, class_name, term, session, user_id, "admin")

    # Create DataFrame
    df = pd.DataFrame(broadsheet_data)
    
    # Display DataFrame
    st.dataframe(
        df,
        column_config={
            "S/N": st.column_config.TextColumn("S/N", width="small"),
            "Student": st.column_config.TextColumn("Student", width="large"),
            "Grand Total": st.column_config.TextColumn("Grand Total", width="medium"),
            "Average": st.column_config.TextColumn("Average", width="medium"),
            "Position": st.column_config.TextColumn("Position", width="medium")
        },
        hide_index=True,
        width="stretch"
    )
    
    # Download button for CSV
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        csv_filename = f"{class_name}_{term}_{session}_Broadsheet.csv"
        csv_data = df.to_csv(index=False)
        st.download_button(
            label="📥 Download Broadsheet as CSV",
            data=csv_data,
            file_name=csv_filename,
            mime="text/csv",
            width="stretch"
        )

