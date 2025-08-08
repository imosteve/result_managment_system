import streamlit as st
import pandas as pd
from database import (
    get_all_classes, get_students_by_class, get_subjects_by_class,
    get_all_scores_by_class
)
from utils import create_metric_5col

def generate_broadsheet():
    # Check authentication
    if not st.session_state.get("authenticated", False):
        st.error("⚠️ Please log in first.")
        st.switch_page("main.py")
        st.stop()

    st.set_page_config(page_title="Class Broadsheet")
    
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
    selected_class_display = st.selectbox("Choose Class", class_options)
    
    # Find the selected class data
    selected_index = class_options.index(selected_class_display)
    selected_class_data = classes[selected_index]
    
    class_name = selected_class_data['class_name']
    term = selected_class_data['term']
    session = selected_class_data['session']
    
    students = get_students_by_class(class_name, term, session)
    subjects = get_subjects_by_class(class_name, term, session)
    
    if not students:
        st.warning(f"⚠️ No students found for {class_name} - {term} - {session}.")
        return
        
    if not subjects:
        st.warning(f"⚠️ No subjects found for {class_name} - {term} - {session}.")
        return

    # Get all scores for the class
    all_scores = get_all_scores_by_class(class_name, term, session)
    
    # Organize scores by student and subject
    score_dict = {}
    for score in all_scores:
        student_name = score[1]
        subject_name = score[2]
        if student_name not in score_dict:
            score_dict[student_name] = {}
        score_dict[student_name][subject_name] = {
            'test': score[3],
            'exam': score[4],
            'total': score[5]
        }

    # Build broadsheet data
    broadsheet_rows = []
    subject_names = [s[1] for s in subjects]
    
    for idx, student in enumerate(students, 1):
        student_name = student[1]
        student_gender = student[2]
        
        row = {"S/N": str(idx), "NAME": student_name, "Gender": student_gender}
        total_test = total_exam = total_score = 0
        subject_count = 0

        for subject_name in subject_names:
            student_scores = score_dict.get(student_name, {})
            subject_score = student_scores.get(subject_name, {'test': 0, 'exam': 0, 'total': 0})
            
            test = subject_score['test']
            exam = subject_score['exam']
            total = subject_score['total']

            row[f"{subject_name} - Test"] = test
            row[f"{subject_name} - Exam"] = exam
            row[f"{subject_name} - Total"] = total

            total_test += test
            total_exam += exam
            total_score += total
            subject_count += 1

        average = total_score / subject_count if subject_count else 0
        row["Test Total"] = total_test
        row["Exam Total"] = total_exam
        row["Grand Total"] = total_score
        row["Average"] = round(average, 2)
        broadsheet_rows.append(row)

    if not broadsheet_rows:
        st.warning("⚠️ No data available for broadsheet.")
        return

    broadsheet_df = pd.DataFrame(broadsheet_rows)
    
    # Rank students by grand total
    broadsheet_df["Position"] = broadsheet_df["Grand Total"].rank(ascending=False, method="min").astype(int)

    # Calculate class average
    class_average = round(broadsheet_df["Average"].mean(), 2)

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

    # Order columns
    ordered_cols = ["S/N", "NAME", "Gender"]
    for subject_name in subject_names:
        ordered_cols.extend([f"{subject_name} - Test", f"{subject_name} - Exam", f"{subject_name} - Total"])
    ordered_cols.extend(["Test Total", "Exam Total", "Grand Total", "Average", "Position"])

    # Reorder DataFrame columns
    available_cols = [col for col in ordered_cols if col in broadsheet_df.columns]
    broadsheet_df = broadsheet_df[available_cols]
    
    st.dataframe(broadsheet_df, hide_index=True, use_container_width=True)