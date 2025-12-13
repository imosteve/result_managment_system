# pdf_generators/broadsheet_pdf.py
"""Broadsheet PDF generation module - Clean and modular"""

import io
import os
import re
from pathlib import Path
from weasyprint import HTML, CSS
from jinja2 import Environment, FileSystemLoader
from PyPDF2 import PdfMerger

from database import (
    get_students_by_class, 
    get_subjects_by_class, 
    get_student_scores, 
    get_student_grand_totals, 
    get_grade_distribution
)
from main_utils import format_ordinal
from config import APP_CONFIG

# School information constants
SCHOOL_NAME = APP_CONFIG["school_name"]
SCHOOL_ADDRESS = APP_CONFIG["school_address"]

# Get paths
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / 'templates'


def get_jinja_env():
    """Initialize and return Jinja2 environment"""
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True
    )


def get_dynamic_css(num_subjects, num_students):
    """
    Generate dynamic CSS based on data size
    
    Args:
        num_subjects: Number of subjects
        num_students: Number of students
    
    Returns:
        str: Dynamic CSS content (page size, font sizes, logo size)
    """
    # Determine sizing based on data
    if num_subjects > 15 or num_students > 50:
        paper_size = "A2 landscape"
        body_font = "9px"
        school_name_font = "24px"
        logo_size = "45px"
    else:
        paper_size = "A2 landscape"
        body_font = "10px"
        school_name_font = "24px"
        logo_size = "55px"
    
    # Return dynamic CSS that will be prepended to static CSS
    return f"""
        @page {{
            size: {paper_size};
            margin: 1cm;
        }}
        
        body {{
            font-size: {body_font};
        }}
        
        .school-name {{
            font-size: {school_name_font};
        }}
        
        .logo {{
            width: {logo_size};
            height: {logo_size};
        }}
    """


def prepare_student_data_empty(students, is_sss2_or_sss3):
    """
    Prepare empty student data for blank template
    
    Args:
        students: List of student records
        is_sss2_or_sss3: Boolean for SSS2/SSS3 classes
    
    Returns:
        list: List of student dictionaries with empty scores
    """
    students_data = []
    for student in students:
        student_dict = {
            'name': student[1],
            'scores': {},
            'grand_total': '',
            'average': '',
        }
        
        if is_sss2_or_sss3:
            student_dict['grade'] = ''
            student_dict['position'] = None
        else:
            student_dict['position'] = ''
            student_dict['grade'] = None
        
        students_data.append(student_dict)
    
    return students_data


def prepare_student_data_with_scores(broadsheet_data, subject_names, is_sss2_or_sss3):
    """
    Prepare student data with scores from broadsheet data
    
    Args:
        broadsheet_data: List of student data dictionaries
        subject_names: List of subject names
        is_sss2_or_sss3: Boolean for SSS2/SSS3 classes
    
    Returns:
        list: List of formatted student dictionaries
    """
    students_data = []
    
    for row in broadsheet_data:
        student_dict = {
            'name': row['Student'],
            'scores': {},
            'grand_total': row.get('Grand Total', '-'),
            'average': row.get('Average', '-')
        }
        
        # Extract scores for each subject
        for subject_name in subject_names:
            test_key = f"{subject_name} (Test)"
            exam_key = f"{subject_name} (Exam)"
            total_key = f"{subject_name} (Total)"
            
            student_dict['scores'][subject_name] = {
                'test': row.get(test_key, '-'),
                'exam': row.get(exam_key, '-'),
                'total': row.get(total_key, '-')
            }
        
        # Add position or grade
        if is_sss2_or_sss3:
            student_dict['grade'] = row.get('Grade', '-')
            student_dict['position'] = None
        else:
            student_dict['position'] = row.get('Position', '-')
            student_dict['grade'] = None
        
        students_data.append(student_dict)
    
    return students_data


def generate_blank_broadsheet_pdf(class_name, term, session, students, subjects, is_sss2_or_sss3):
    """
    Generate blank broadsheet template PDF
    
    Args:
        class_name: Class name
        term: Term
        session: Session
        students: List of student records
        subjects: List of subject records
        is_sss2_or_sss3: Boolean indicating if class is SSS2 or SSS3
    
    Returns:
        BytesIO: PDF buffer
    """
    # Prepare data
    students_data = prepare_student_data_empty(students, is_sss2_or_sss3)
    subject_names = [subject[1] for subject in subjects]
    
    # Setup Jinja environment
    env = get_jinja_env()
    template = env.get_template('broadsheet.html')
    
    # Render HTML
    html_content = template.render(
        school_name=SCHOOL_NAME,
        school_address=SCHOOL_ADDRESS,
        class_name=class_name,
        term=term,
        session=session,
        num_students=len(students),
        num_subjects=len(subjects),
        subjects=subject_names,
        students_data=students_data,
        is_sss2_or_sss3=is_sss2_or_sss3,
        class_average=None
    )
    
    # Load static CSS from file
    css_path = TEMPLATES_DIR / 'broadsheet_styles.css'
    static_css = css_path.read_text()
    
    # Generate dynamic CSS based on data size
    dynamic_css = get_dynamic_css(len(subjects), len(students))
    
    # Combine: dynamic CSS first (so it can override defaults), then static CSS
    full_css = dynamic_css + "\n" + static_css
    
    # Generate PDF
    pdf_buffer = io.BytesIO()
    HTML(string=html_content, base_url=str(BASE_DIR)).write_pdf(
        pdf_buffer,
        stylesheets=[CSS(string=full_css)]
    )
    pdf_buffer.seek(0)
    
    return pdf_buffer


def generate_broadsheet_with_scores_pdf(class_name, term, session, broadsheet_data, 
                                        subjects, class_average, is_sss2_or_sss3):
    """
    Generate broadsheet with scores PDF for a single class and save to folder
    
    Args:
        class_name: Class name
        term: Term
        session: Session
        broadsheet_data: List of student data dictionaries
        subjects: List of subject records
        class_average: Class average score
        is_sss2_or_sss3: Boolean indicating if class is SSS2 or SSS3
    
    Returns:
        tuple: (BytesIO PDF buffer, str file_path) - file_path is None if save failed
    """
    # Prepare data
    subject_names = [subject[1] for subject in subjects]
    students_data = prepare_student_data_with_scores(broadsheet_data, subject_names, is_sss2_or_sss3)
    
    # Setup Jinja environment
    env = get_jinja_env()
    template = env.get_template('broadsheet.html')
    
    # Render HTML
    html_content = template.render(
        school_name=SCHOOL_NAME,
        school_address=SCHOOL_ADDRESS,
        class_name=class_name,
        term=term,
        session=session,
        num_students=len(students_data),
        num_subjects=len(subject_names),
        subjects=subject_names,
        students_data=students_data,
        is_sss2_or_sss3=is_sss2_or_sss3,
        class_average=class_average
    )
    
    # Load static CSS from file
    css_path = TEMPLATES_DIR / 'broadsheet_styles.css'
    static_css = css_path.read_text()
    
    # Generate dynamic CSS based on data size
    dynamic_css = get_dynamic_css(len(subject_names), len(students_data))
    
    # Combine: dynamic CSS first, then static CSS
    full_css = dynamic_css + "\n" + static_css
    
    # Generate PDF
    pdf_buffer = io.BytesIO()
    HTML(string=html_content, base_url=str(BASE_DIR)).write_pdf(
        pdf_buffer,
        stylesheets=[CSS(string=full_css)]
    )
    pdf_buffer.seek(0)
    
    # Save to folder automatically (like report cards)
    file_path = None
    try:
        os.makedirs("data/broadsheet", exist_ok=True)
        safe_class = class_name.replace(' ', '_')
        safe_term = term.replace(' ', '_')
        safe_session = session.replace('/', '_')
        file_path = os.path.join("data/broadsheet", f"{safe_class}_{safe_term}_{safe_session}_Broadsheet.pdf")
        
        with open(file_path, 'wb') as f:
            f.write(pdf_buffer.getvalue())
        
        # Reset buffer position for download
        pdf_buffer.seek(0)
    except Exception as e:
        print(f"Error saving broadsheet to folder: {e}")
        file_path = None
    
    return pdf_buffer, file_path


def build_class_broadsheet_data(class_name, term, session, user_id, role):
    """
    Build broadsheet data for a single class
    
    Args:
        class_name: Class name
        term: Term
        session: Session
        user_id: User ID
        role: User role
    
    Returns:
        tuple: (broadsheet_data, subjects, class_average, is_sss2_or_sss3) or None if no data
    """
    # Check if SSS2 or SSS3
    is_sss2_or_sss3 = bool(re.match(r"SSS [23].*$", class_name))
    
    # Get students and subjects
    students = get_students_by_class(class_name, term, session, user_id, role)
    subjects = get_subjects_by_class(class_name, term, session, user_id, role)
    
    if not students or not subjects:
        return None
    
    # Build broadsheet data
    broadsheet_data = []
    grand_totals = get_student_grand_totals(class_name, term, session, user_id, role)
    
    for student in students:
        student_name = student[1]
        scores = get_student_scores(student_name, class_name, term, session, user_id, role)
        
        test_scores = {}
        exam_scores = {}
        total_scores = {}
        
        for score in scores:
            subject_name = score[2]
            test_scores[subject_name] = str(int(score[3])) if score[3] is not None else "-"
            exam_scores[subject_name] = str(int(score[4])) if score[4] is not None else "-"
            total_scores[subject_name] = str(int(score[5])) if score[5] is not None else "-"
        
        row = {"Student": student_name}
        
        for subject in subjects:
            subject_name = subject[1]
            row[f"{subject_name} (Test)"] = test_scores.get(subject_name, "-")
            row[f"{subject_name} (Exam)"] = exam_scores.get(subject_name, "-")
            row[f"{subject_name} (Total)"] = total_scores.get(subject_name, "-")
        
        # Calculate grand total
        numeric_totals = [int(v) for v in total_scores.values() if v != "-"]
        grand_total = str(sum(numeric_totals)) if numeric_totals else "-"
        row["Grand Total"] = grand_total
        
        # Calculate average
        if grand_total != "-" and numeric_totals:
            avg = round(int(grand_total) / len(numeric_totals), 1)
            row["Average"] = str(avg)
        else:
            row["Average"] = "-"
        
        # Get position or grade
        position_data = next((gt for gt in grand_totals if gt['student_name'] == student_name), None)
        
        if is_sss2_or_sss3:
            grade_distribution = get_grade_distribution(student_name, class_name, term, session, user_id, role)
            row["Grade"] = grade_distribution if grade_distribution else "-"
        else:
            row["Position"] = format_ordinal(position_data['position']) if position_data else "-"
        
        broadsheet_data.append(row)
    
    # Calculate class average
    numeric_averages = [float(row["Average"]) for row in broadsheet_data if row["Average"] != "-"]
    class_average = round(sum(numeric_averages) / len(numeric_averages), 2) if numeric_averages else 0
    
    return broadsheet_data, subjects, class_average, is_sss2_or_sss3


def generate_all_classes_broadsheet_pdf(classes, user_id, role):
    """
    Generate broadsheet PDF for all classes in a single document
    
    Args:
        classes: List of class dictionaries
        user_id: User ID
        role: User role
    
    Returns:
        BytesIO: PDF buffer with all broadsheets
    """
    merger = PdfMerger()
    
    for class_data in classes:
        class_name = class_data['class_name']
        term = class_data['term']
        session = class_data['session']
        
        # Build data for this class
        result = build_class_broadsheet_data(class_name, term, session, user_id, role)
        
        if result is None:
            continue
        
        broadsheet_data, subjects, class_average, is_sss2_or_sss3 = result
        
        # Generate PDF for this class (returns buffer and file_path)
        class_pdf, _ = generate_broadsheet_with_scores_pdf(
            class_name, term, session, broadsheet_data, subjects, 
            class_average, is_sss2_or_sss3
        )
        
        merger.append(class_pdf)
    
    # Merge all PDFs
    output_buffer = io.BytesIO()
    merger.write(output_buffer)
    merger.close()
    output_buffer.seek(0)
    
    return output_buffer