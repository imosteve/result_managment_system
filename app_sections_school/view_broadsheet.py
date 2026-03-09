# app_sections/view_broadsheet.py

import streamlit as st
import pandas as pd
import re
import os
from database_school import (
    get_active_session, get_active_term_name, get_classes_for_session, 
    get_enrolled_students, get_subjects_by_class, get_scores_for_subject, 
    get_student_grand_totals, get_grade_distribution, get_all_sessions,
    get_user_assignments
)
from main_utils import (
    assign_grade, create_metric_5col_broadsheet, 
    format_ordinal, render_page_header, inject_login_css
)
from pdf_generators.broadsheet_pdf_reportlab import (
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

    # ── Session / term context ────────────────────────────────────────────────
    _active_session = get_active_session()
    _active_term    = get_active_term_name()

    if role in ("superadmin", "admin"):
        _all_sessions  = get_all_sessions()
        _session_names = [s["session"] for s in _all_sessions] if _all_sessions else ([_active_session] if _active_session else [])
        _term_options  = ["First", "Second", "Third"]
        _term_display  = ["1st Term", "2nd Term", "3rd Term"]
        _term_map      = dict(zip(_term_display, _term_options))
        _term_rmap     = dict(zip(_term_options, _term_display))

        classes = get_classes_for_session(session)
        class_names = [c["class_name"] for c in classes]
        if not class_names:
            st.warning("⚠️ No classes found.")
            return

        _col_class, _col_term, _col_session = st.columns(3)
        with _col_class:
            class_name = st.selectbox("Select Class", class_names, key="view_broadsheet_class")
        with _col_term:
            _term_default = _term_rmap.get(_active_term, "1st Term")
            _term_sel     = st.selectbox("Select Term", _term_display,
                                         index=_term_display.index(_term_default),
                                         key="view_broadsheet_term")
            term = _term_map[_term_sel]
        with _col_session:
            _sess_default = _session_names.index(_active_session) if _active_session in _session_names else 0
            session       = st.selectbox("Select Session", _session_names,
                                         index=_sess_default,
                                         key="view_broadsheet_session")
    else:
        if not _active_session:
            st.warning("⚠️ No active session configured. Ask an admin to set one in Academic Settings.")
            return
        if not _active_term:
            st.warning("⚠️ No active term configured. Ask an admin to set one in Academic Settings.")
            return
        session = _active_session
        term    = _active_term
        user_assignments = get_user_assignments(user_id)
        assigned_classes = list(dict.fromkeys(
            a["class_name"] for a in user_assignments if a.get("class_name")
        ))
        if not assigned_classes:
            st.warning("⚠️ No class assignments found. Contact your administrator.")
            return
        class_name = st.selectbox("Select Class", assigned_classes, key="view_broadsheet_class")
        st.info(f"**Active:** {session} — {term} Term")
    if not class_name:
        return
    
    # Check if this is SSS2 or SSS3
    is_sss2_or_sss3 = bool(re.match(r"SSS [23].*$", class_name))
    
    students = get_enrolled_students(class_name, session)
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
        # scores_by_subject is preloaded below; look up per subject
        test_scores = {}
        exam_scores = {}
        total_scores = {}
        for subject in subjects:
            subj_name = subject["subject_name"] if isinstance(subject, dict) else subject[1]
            subj_scores = scores_by_subject.get(subj_name, {})
            student_score = subj_scores.get(student_name)
            if student_score:
                ca = student_score.get("ca_score") if isinstance(student_score, dict) else student_score[3]
                exam = student_score.get("exam_score") if isinstance(student_score, dict) else student_score[4]
                total = student_score.get("total_score") if isinstance(student_score, dict) else student_score[5]
                test_scores[subj_name] = str(int(ca)) if ca is not None else "-"
                exam_scores[subj_name] = str(int(exam)) if exam is not None else "-"
                total_scores[subj_name] = str(int(total)) if total is not None else "-"
            else:
                test_scores[subj_name] = "-"
                exam_scores[subj_name] = "-"
                total_scores[subj_name] = "-"
        
        row = {"Student": student_name}
        
        # Add Test, Exam, and Total columns for each subject
        for subject in subjects:
            subject_name = subject["subject_name"] if isinstance(subject, dict) else subject[1]
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
                        classes, user_id, role, sort_by
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