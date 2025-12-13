# utils/broadsheet_import.py

"""Broadsheet import functionality for bulk score entry"""

import pandas as pd
import streamlit as st
from database import (
    get_students_by_class, get_subjects_by_class,
    save_scores
)
from main_utils import assign_grade

def parse_broadsheet_file(uploaded_file, class_name, term, session):
    """
    Parse uploaded broadsheet file (CSV or Excel)
    
    Args:
        uploaded_file: Streamlit uploaded file object
        class_name: Class name
        term: Term
        session: Session
    
    Returns:
        tuple: (success, message, parsed_data)
    """
    try:
        # Read file based on extension
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        elif uploaded_file.name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(uploaded_file)
        else:
            return False, "Unsupported file format. Please upload CSV or Excel file.", None
        
        # Validate required columns
        if 'Student' not in df.columns:
            return False, "Missing required 'Student' column in file.", None
        
        # Extract subject columns (those with Test, Exam, Total suffixes)
        subject_cols = {}
        for col in df.columns:
            if col.endswith(' (Test)'):
                subject_name = col.replace(' (Test)', '')
                if subject_name not in subject_cols:
                    subject_cols[subject_name] = {}
                subject_cols[subject_name]['test'] = col
            elif col.endswith(' (Exam)'):
                subject_name = col.replace(' (Exam)', '')
                if subject_name not in subject_cols:
                    subject_cols[subject_name] = {}
                subject_cols[subject_name]['exam'] = col
        
        if not subject_cols:
            return False, "No subject score columns found in file.", None
        
        # Validate subjects have both test and exam columns
        incomplete_subjects = []
        for subject, cols in subject_cols.items():
            if 'test' not in cols or 'exam' not in cols:
                incomplete_subjects.append(subject)
        
        if incomplete_subjects:
            return False, f"Incomplete score columns for subjects: {', '.join(incomplete_subjects)}", None
        
        # Parse student scores
        parsed_data = []
        for _, row in df.iterrows():
            student_name = str(row['Student']).strip()
            if not student_name or student_name == 'nan':
                continue
            
            for subject_name, cols in subject_cols.items():
                try:
                    test_score = row[cols['test']]
                    exam_score = row[cols['exam']]
                    
                    # Skip if both scores are empty
                    if pd.isna(test_score) and pd.isna(exam_score):
                        continue
                    
                    # Convert to integers, default to 0 if empty
                    test_score = int(float(test_score)) if not pd.isna(test_score) else 0
                    exam_score = int(float(exam_score)) if not pd.isna(exam_score) else 0
                    
                    # Validate score ranges
                    if not (0 <= test_score <= 30):
                        return False, f"Invalid test score for {student_name} in {subject_name}: {test_score} (must be 0-30)", None
                    
                    if not (0 <= exam_score <= 70):
                        return False, f"Invalid exam score for {student_name} in {subject_name}: {exam_score} (must be 0-70)", None
                    
                    total_score = test_score + exam_score
                    grade = assign_grade(total_score)
                    
                    parsed_data.append({
                        'student': student_name,
                        'subject': subject_name,
                        'class': class_name,
                        'term': term,
                        'session': session,
                        'test': test_score,
                        'exam': exam_score,
                        'total': total_score,
                        'grade': grade,
                        'position': 0  # Will be calculated when saving
                    })
                    
                except Exception as e:
                    return False, f"Error parsing scores for {student_name} in {subject_name}: {str(e)}", None
        
        if not parsed_data:
            return False, "No valid score data found in file.", None
        
        return True, f"Successfully parsed {len(parsed_data)} score entries", parsed_data
    
    except Exception as e:
        return False, f"Error reading file: {str(e)}", None


def import_broadsheet_scores(parsed_data, class_name, term, session, user_id, role):
    """
    Import parsed broadsheet scores into database
    
    Args:
        parsed_data: List of score dictionaries
        class_name: Class name
        term: Term
        session: Session
        user_id: User ID
        role: User role
    
    Returns:
        tuple: (success, message)
    """
    try:
        # Validate students and subjects exist
        existing_students = get_students_by_class(class_name, term, session, user_id, role)
        existing_subjects = get_subjects_by_class(class_name, term, session, user_id, role)
        
        student_names = {s[1] for s in existing_students}
        subject_names = {s[1] for s in existing_subjects}
        
        # Check for missing students or subjects
        missing_students = set()
        missing_subjects = set()
        
        for entry in parsed_data:
            if entry['student'] not in student_names:
                missing_students.add(entry['student'])
            if entry['subject'] not in subject_names:
                missing_subjects.add(entry['subject'])
        
        if missing_students:
            return False, f"Students not found in database: {', '.join(list(missing_students)[:5])}"
        
        if missing_subjects:
            return False, f"Subjects not found in database: {', '.join(list(missing_subjects)[:5])}"
        
        # Group scores by subject for batch processing
        scores_by_subject = {}
        for entry in parsed_data:
            subject = entry['subject']
            if subject not in scores_by_subject:
                scores_by_subject[subject] = []
            scores_by_subject[subject].append(entry)
        
        # Save scores for each subject
        for subject, scores in scores_by_subject.items():
            save_scores(scores, class_name, subject, term, session)
        
        return True, f"Successfully imported scores for {len(scores_by_subject)} subjects"
    
    except Exception as e:
        return False, f"Error importing scores: {str(e)}"


def show_import_interface(class_name, term, session, user_id, role):
    """
    Display the import interface in Streamlit
    
    Args:
        class_name: Class name
        term: Term
        session: Session
        user_id: User ID
        role: User role
    """
    st.markdown("### 📤 Import Broadsheet Scores")
    st.info("""
    **Import Instructions:**
    1. Download the blank broadsheet template or a previous broadsheet
    2. Fill in the scores in the appropriate columns (Test and Exam)
    3. Save the file as CSV or Excel format
    4. Upload the file below
    5. Review the preview and confirm import
    
    **Important Notes:**
    - Student names must exactly match those in the database
    - Test scores should be between 0-30
    - Exam scores should be between 0-70
    - Leave cells empty for students who didn't take the exam
    """)
    
    uploaded_file = st.file_uploader(
        "Upload Broadsheet File",
        type=['csv', 'xlsx', 'xls'],
        help="Upload a CSV or Excel file with student scores"
    )
    
    if uploaded_file is not None:
        st.success(f"File uploaded: {uploaded_file.name}")
        
        # Parse the file
        with st.spinner("Parsing broadsheet file..."):
            success, message, parsed_data = parse_broadsheet_file(
                uploaded_file, class_name, term, session
            )
        
        if not success:
            st.error(f"❌ {message}")
            return
        
        st.success(f"✅ {message}")
        
        # Show preview of parsed data
        st.markdown("#### Preview of Parsed Data")
        preview_df = pd.DataFrame(parsed_data[:20])  # Show first 20 entries
        st.dataframe(preview_df, use_container_width=True)
        
        if len(parsed_data) > 20:
            st.info(f"Showing first 20 of {len(parsed_data)} total entries")
        
        # Confirmation buttons
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if st.button("✅ Confirm Import", type="primary", use_container_width=True):
                with st.spinner("Importing scores..."):
                    success, message = import_broadsheet_scores(
                        parsed_data, class_name, term, session, user_id, role
                    )
                
                if success:
                    st.success(f"✅ {message}")
                    st.balloons()
                    st.info("Scores have been successfully imported. You can now view the updated broadsheet.")
                else:
                    st.error(f"❌ {message}")
        
        with col2:
            if st.button("❌ Cancel Import", use_container_width=True):
                st.warning("Import cancelled. No changes were made.")
                st.rerun()