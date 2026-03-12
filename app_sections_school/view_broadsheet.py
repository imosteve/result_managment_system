# app_sections/view_broadsheet.py

import streamlit as st
import pandas as pd
import re
import os
from database_school import (
    get_active_session, get_active_term_name, get_classes_for_session, 
    get_enrolled_students, get_subjects_by_class, get_scores_for_subject, 
    get_student_grand_totals, get_grade_distribution, get_all_sessions,
    get_user_assignments, get_student_selected_subjects
)
from main_utils import (
    assign_grade, create_metric_5col_broadsheet,
    format_ordinal, render_page_header, inject_login_css,
    render_class_term_session_selector
)
from pdf_generators.broadsheet_pdf_reportlab import (
    generate_blank_broadsheet_pdf,
    generate_broadsheet_with_scores_pdf,
    generate_all_classes_broadsheet_pdf,
    build_class_broadsheet_data
)
from PyPDF2 import PdfMerger
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

    # ── Session / term context ────────────────────────────────────────────────
    _ctx = render_class_term_session_selector("view_broadsheet", allow_term_session_override=True)
    if _ctx is None:
        return
    class_name = _ctx["class_name"]
    term       = _ctx["term"]
    session    = _ctx["session"]
    
    # Check if this is SSS2 or SSS3
    is_sss2_or_sss3 = bool(re.match(r"SSS [23].*$", class_name))
    
    students = get_enrolled_students(class_name, session, term)
    if not students:
        st.warning(f"⚠️ No students found for {class_name}.")
        return

    subjects = get_subjects_by_class(class_name)
    if not subjects:
        st.warning(f"⚠️ No subjects found for {class_name}.")
        return

    broadsheet_data = []
    grand_totals = get_student_grand_totals(class_name, session, term)

    # Preload all scores per subject for efficient lookup
    scores_by_subject = {}
    for subject in subjects:
        subj_name = subject["subject_name"] if isinstance(subject, dict) else subject[1]
        subj_score_list = get_scores_for_subject(class_name, session, term, subj_name)
        scores_by_subject[subj_name] = {
            (s["student_name"] if isinstance(s, dict) else s[1]): s
            for s in subj_score_list
        }

    for student in students:
        student_name = student["student_name"]

        # For SSS2/SSS3, get this student's selected subjects for this term
        if is_sss2_or_sss3:
            selected_subjects = set(
                get_student_selected_subjects(student_name, class_name, term, session)
            )
        else:
            selected_subjects = None  # None = all subjects count

        test_scores = {}
        exam_scores = {}
        total_scores = {}
        for subject in subjects:
            subj_name = subject["subject_name"] if isinstance(subject, dict) else subject[1]

            # For SSS2/SSS3: if subject not selected by this student, show "-"
            if selected_subjects is not None and subj_name not in selected_subjects:
                test_scores[subj_name] = "-"
                exam_scores[subj_name] = "-"
                total_scores[subj_name] = "-"
                continue

            subj_scores = scores_by_subject.get(subj_name, {})
            student_score = subj_scores.get(student_name)
            if student_score:
                ca    = student_score.get("ca_score")    if isinstance(student_score, dict) else student_score[3]
                exam  = student_score.get("exam_score")  if isinstance(student_score, dict) else student_score[4]
                total = student_score.get("total_score") if isinstance(student_score, dict) else student_score[5]
                test_scores[subj_name]  = str(int(ca))    if ca    is not None else "-"
                exam_scores[subj_name]  = str(int(exam))  if exam  is not None else "-"
                total_scores[subj_name] = str(int(total)) if total is not None else "-"
            else:
                test_scores[subj_name]  = "-"
                exam_scores[subj_name]  = "-"
                total_scores[subj_name] = "-"
        
        row = {"Student": student_name}
        
        # Add Test, Exam, and Total columns for each subject
        for subject in subjects:
            subject_name = subject["subject_name"] if isinstance(subject, dict) else subject[1]
            row[f"{subject_name} (Test)"] = test_scores.get(subject_name, "-")
            row[f"{subject_name} (Exam)"] = exam_scores.get(subject_name, "-")
            row[f"{subject_name} (Total)"] = total_scores.get(subject_name, "-")
        
        # Calculate grand total and average
        # For SSS2/SSS3: use the pre-computed grand_total (selected subjects only)
        # For others: sum all non-"-" subject totals
        position_data = next((gt for gt in grand_totals if gt['student_name'] == student_name), None)

        if is_sss2_or_sss3:
            if position_data and position_data['grand_total'] is not None:
                grand_total = str(int(position_data['grand_total']))
                # Average over selected subjects only
                selected_totals = [int(v) for k, v in total_scores.items() if v != "-"]
                avg = round(int(grand_total) / len(selected_totals), 1) if selected_totals else 0
                row["Grand Total"] = grand_total
                row["Average"] = str(avg)
            else:
                row["Grand Total"] = "-"
                row["Average"] = "-"
        else:
            numeric_totals = [int(v) for v in total_scores.values() if v != "-"]
            grand_total = str(sum(numeric_totals)) if numeric_totals else "-"
            row["Grand Total"] = grand_total
            if grand_total != "-" and numeric_totals:
                avg = round(sum(numeric_totals) / len(numeric_totals), 1)
                row["Average"] = str(avg)
            else:
                row["Average"] = "-"
        
        if is_sss2_or_sss3:
            # For SSS2 and SSS3, get grade distribution
            grade_distribution = get_grade_distribution(student_name, class_name, session, term)
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
    create_metric_5col_broadsheet(subjects, students, class_average, broadsheet_data, class_name, term, session, user_id, role)

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
                pdf_buffer = generate_broadsheet_with_scores_pdf(
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
        classes = get_classes_for_session(session)
        if role in ["superadmin", "admin"]:
            if st.button("Export All Classes", use_container_width=True):
                try:
                    total_classes = len(classes)
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    merger = PdfMerger()
                    skipped = []

                    for i, class_data in enumerate(classes):
                        class_name_iter = class_data['class_name']
                        status_text.text(f"Processing {class_name_iter} ({i + 1}/{total_classes})...")

                        result = build_class_broadsheet_data(class_name_iter, term, session, user_id, role, sort_by)
                        if result is None:
                            skipped.append(class_name_iter)
                        else:
                            bd_data, bd_subjects, bd_avg, bd_is_sss = result
                            class_pdf = generate_broadsheet_with_scores_pdf(
                                class_name_iter, term, session, bd_data, bd_subjects, bd_avg, bd_is_sss
                            )
                            merger.append(class_pdf)

                        progress_bar.progress((i + 1) / total_classes)

                    status_text.text("Merging all class broadsheets...")
                    output_buffer = io.BytesIO()
                    merger.write(output_buffer)
                    merger.close()
                    output_buffer.seek(0)

                    progress_bar.progress(1.0)
                    status_text.text(f"✅ Done! {total_classes - len(skipped)} class(es) exported.")

                    if skipped:
                        st.warning(f"⚠️ Skipped (no data): {', '.join(skipped)}")

                    safe_term = term.replace(' ', '_')
                    safe_session = session.replace('/', '_')
                    file_name = f"All_Classes_{safe_term}_{safe_session}_Broadsheet.pdf"

                    st.download_button(
                        label="⬇️ Download All Classes PDF",
                        data=output_buffer,
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