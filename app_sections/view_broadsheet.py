# app_sections/view_broadsheet.py

import streamlit as st
import pandas as pd
import re
import os
from database import get_all_classes, get_students_by_class, get_subjects_by_class, get_student_scores, get_student_grand_totals, get_grade_distribution
from main_utils import (
    assign_grade, create_metric_5col_broadsheet, 
    format_ordinal, render_page_header, inject_login_css, 
    render_persistent_class_selector
)
from pdf_generators.broadsheet_pdf import (
    generate_blank_broadsheet_pdf,
    generate_broadsheet_with_scores_pdf,
    generate_all_classes_broadsheet_pdf
)
from utils.broadsheet_import import show_import_interface
import io

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
    selected_class_data = render_persistent_class_selector(
        classes, 
        widget_key="view_broadsheet_class"
    )

    if not selected_class_data:
        st.warning("⚠️ No class selected.")
        return

    class_name = selected_class_data['class_name']
    term = selected_class_data['term']
    session = selected_class_data['session']
    
    # Check if this is SSS2 or SSS3
    is_sss2_or_sss3 = bool(re.match(r"SSS [23].*$", class_name))
    
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

    for student in students:
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
        
        row = {"Student": student_name}
        
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
            avg = round(int(grand_total) / len(numeric_totals), 1)
            row["Average"] = str(avg)
        else:
            row["Average"] = "-"
        
        # Get position or grade based on class type
        position_data = next((gt for gt in grand_totals if gt['student_name'] == student_name), None)
        
        if is_sss2_or_sss3:
            # For SSS2 and SSS3, get grade distribution
            grade_distribution = get_grade_distribution(student_name, class_name, term, session, user_id, "admin")
            row["Grade"] = grade_distribution if grade_distribution else "-"
            row["_position"] = position_data['position'] if position_data else 999  # Hidden field for sorting
        else:
            # For other classes, show position
            row["Position"] = format_ordinal(position_data['position']) if position_data else "-"
            row["_position"] = position_data['position'] if position_data else 999  # Hidden field for sorting
        
        broadsheet_data.append(row)

    # Default sort by position
    broadsheet_data.sort(key=lambda x: x.get("_position", 999))
    
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

    # Add sorting filter
    st.markdown("---")
    col_space, col_filter_label, col_filter = st.columns([4, 0.5, 1], vertical_alignment="center")
    
    with col_filter_label:
        st.markdown("**Sort by:**")
    with col_filter:
        if is_sss2_or_sss3:
            sort_options = ["Position/Grade", "Name (A-Z)", "Name (Z-A)"]
        else:
            sort_options = ["Position", "Name (A-Z)", "Name (Z-A)"]
        
        sort_by = st.selectbox("Sort by:", sort_options, key="sort_broadsheet", label_visibility="collapsed")
    
    # Apply sorting based on selection
    sorted_data = broadsheet_data.copy()
    
    if sort_by == "Name (A-Z)":
        sorted_data.sort(key=lambda x: x["Student"].lower())
    elif sort_by == "Name (Z-A)":
        sorted_data.sort(key=lambda x: x["Student"].lower(), reverse=True)
    else:  # Position or Position/Grade
        sorted_data.sort(key=lambda x: x.get("_position", 999))
    
    # Add S/N after sorting and remove hidden _position field
    for idx, row in enumerate(sorted_data, 1):
        row["S/N"] = str(idx)
        row.pop("_position", None)

    # Create DataFrame with proper column order
    if is_sss2_or_sss3:
        # For SSS2/SSS3: S/N, Student, subjects..., Grand Total, Average, Grade
        column_order = ["S/N", "Student"] + [col for col in sorted_data[0].keys() if col not in ["S/N", "Student", "Grand Total", "Average", "Grade"]] + ["Grand Total", "Average", "Grade"]
    else:
        # For other classes: S/N, Student, subjects..., Grand Total, Average, Position
        column_order = ["S/N", "Student"] + [col for col in sorted_data[0].keys() if col not in ["S/N", "Student", "Grand Total", "Average", "Position"]] + ["Grand Total", "Average", "Position"]
    
    df = pd.DataFrame(sorted_data)
    df = df[column_order]
    
    # Display DataFrame
    column_config = {
        "S/N": st.column_config.TextColumn("S/N", width="small"),
        "Student": st.column_config.TextColumn("Student", width="medium"),
        "Grand Total": st.column_config.TextColumn("Grand Total", width="small"),
        "Average": st.column_config.TextColumn("Average", width="small")
    }
    
    if is_sss2_or_sss3:
        column_config["Grade"] = st.column_config.TextColumn("Grade", width=150)
    else:
        column_config["Position"] = st.column_config.TextColumn("Position", width="small")
    
    st.dataframe(
        df,
        column_config=column_config,
        hide_index=True,
        width='stretch',
        height=35 * len(sorted_data) + 38
    )
    
    # Export buttons section
    st.markdown("---")
    st.markdown("### 📥 Export Options")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # Export blank broadsheet template
        if st.button("Export Blank Template", use_container_width=True):
            try:
                pdf_buffer = generate_blank_broadsheet_pdf(
                    class_name, term, session, students, subjects, is_sss2_or_sss3
                )
                st.download_button(
                    label="⬇️ Download Blank Template",
                    data=pdf_buffer,
                    file_name=f"{class_name}_{term}_{session}_Blank_Broadsheet.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Error generating blank template: {str(e)}")
    
    with col2:
        # Export broadsheet with scores (automatically saves to folder)
        if st.button("Export with Scores", use_container_width=True):
            try:
                pdf_buffer, file_path = generate_broadsheet_with_scores_pdf(
                    class_name, term, session, sorted_data, subjects, 
                    class_average, is_sss2_or_sss3
                )
                st.download_button(
                    label="⬇️ Download Broadsheet PDF",
                    data=pdf_buffer,
                    file_name=f"{class_name}_{term}_{session}_Broadsheet.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Error generating broadsheet PDF: {str(e)}")
    
    with col3:
        # Export all classes broadsheet
        if role in ["superadmin", "admin"]:
            if st.button("Export All Classes", use_container_width=True):
                try:
                    pdf_buffer = generate_all_classes_broadsheet_pdf(
                        classes, user_id, role
                    )

                    os.makedirs("data/broadsheet", exist_ok=True)
                    safe_term = term.replace(' ', '_')
                    safe_session = session.replace('/', '_')
                    file_name=f"All_Classes_{safe_term}_{safe_session}_Broadsheet.pdf"
                    file_path = os.path.join("data/broadsheet", file_name)
                    
                    with open(file_path, 'wb') as f:
                        f.write(pdf_buffer.getvalue())
                        
                    st.download_button(
                        label="⬇️ Download All Classes PDF",
                        data=pdf_buffer,
                        file_name=file_name,
                        mime="application/pdf",
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"Error generating all classes PDF: {str(e)}")
    
    with col4:
        # Import broadsheet
        if role in ["superadmin"]:
            if st.button("📤 Import Broadsheet", use_container_width=True):
                st.session_state.show_import_dialog = True
    
    # Show import interface if button clicked
    if st.session_state.get('show_import_dialog', False):
        st.markdown("---")
        show_import_interface(class_name, term, session, user_id, role)
        
        if st.button("← Back to Broadsheet", use_container_width=False):
            st.session_state.show_import_dialog = False
            st.rerun()
    
    # Download CSV button
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
            use_container_width=True
        )