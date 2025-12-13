# pdf_generators/report_card_pdf.py

import streamlit as st
import re
from datetime import datetime
import os
import zipfile
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS
from PyPDF2 import PdfMerger
from main_utils import (
    assign_grade, format_ordinal
)
from database import (
    get_all_classes, get_students_by_class, get_student_scores, 
    get_class_average, get_student_grand_totals, get_comment, get_subjects_by_class,
    get_psychomotor_rating, get_grade_distribution, get_next_term_begin_date, get_next_term_info
)
from config import APP_CONFIG

# Email Configuration
SMTP_SERVER = os.getenv('SMTP_SERVER', "smtp.gmail.com")
SMTP_PORT = int(os.getenv('SMTP_PORT', 465))
EMAIL_SENDER = os.getenv('EMAIL_SENDER', "SUIS Terminal Result <ideas.elites@gmail.com>")
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', "lkydcrsaritupygu")

def calculate_next_term(current_term, current_session):
    """Intelligently calculate the next term and session"""
    term_map = {"1st Term": "2nd Term", "2nd Term": "3rd Term", "3rd Term": "1st Term"}
    next_term = term_map.get(current_term, "1st Term")
    
    # If moving from 3rd term to 1st term, increment session
    if current_term == "3rd Term":
        year_parts = current_session.split('/')
        if len(year_parts) == 2:
            start_year = int(year_parts[0])
            end_year = int(year_parts[1])
            next_session = f"{start_year + 1}/{end_year + 1}"
        else:
            next_session = current_session
    else:
        next_session = current_session
    
    return next_term, next_session

def generate_report_card(student_name, class_name, term, session, is_secondary_class, is_primary_class):
    """Generate PDF report card for a student"""
    from database import get_head_teacher_comment_by_average, get_student_average
    
    user_id = st.session_state.user_id
    role = st.session_state.role

    # Fetch student data with role-based restrictions
    students = get_students_by_class(class_name, term, session, user_id, role)
    student_data = next((s for s in students if s[1] == student_name), None)
    if not student_data:
        return None
    gender = student_data[2]
    class_size = len(students)

    # Fetch student scores with role-based restrictions
    student_scores = get_student_scores(student_name, class_name, term, session, user_id, role)
    
    # Get all subjects for the class
    all_subjects = get_subjects_by_class(class_name, term, session, user_id, role)
    if not all_subjects:
        return None

    # Calculate student average and totals (only from actual scores, filtering None values)
    if student_scores:
        # Filter out None values
        valid_totals = [score[5] for score in student_scores if score[5] is not None]
        valid_tests = [int(score[3]) for score in student_scores if score[3] is not None]
        valid_exams = [int(score[4]) for score in student_scores if score[4] is not None]
        
        total_score = sum(valid_totals) if valid_totals else 0
        total_test = sum(valid_tests) if valid_tests else 0
        total_exam = sum(valid_exams) if valid_exams else 0
        grand_total = int(total_test + total_exam)
        avg = total_score / len(valid_totals) if valid_totals else 0
        grade = assign_grade(avg)
    else:
        total_score = total_test = total_exam = grand_total = 0
        avg = 0
        grade = "-"

    # Calculate class average
    class_average = get_class_average(class_name, term, session, user_id, role)

    # Get position based on grand total comparison
    grand_totals = get_student_grand_totals(class_name, term, session, user_id, role)
    position_data = next((gt for gt in grand_totals if gt['student_name'] == student_name), None)
    # Get position or grade distribution based on class
    is_sss2_or_sss3 = bool(re.match(r"SSS [23].*$", class_name))
    if is_sss2_or_sss3:
        # For SSS2 and SSS3, get grade distribution instead of position
        grade_distribution = get_grade_distribution(student_name, class_name, term, session, user_id, role)
        position = ""  # Not used for SSS2/SSS3
    else:
        grade_distribution = ""
        position = format_ordinal(position_data['position']) if position_data else "-"   

    current_date = datetime.now().strftime("%d %b %Y")
    
    # Fetch dynamic comments - UPDATED TO HANDLE AUTO COMMENTS
    comment = get_comment(student_name, class_name, term, session)
    class_teacher_comment = ""
    head_teacher_comment = ""
    
    if comment:
        class_teacher_comment = comment['class_teacher_comment'] if comment['class_teacher_comment'] else ""
        
        # Check if head teacher comment is custom or should be auto-generated
        is_ht_custom = comment.get('head_teacher_comment_custom', 0) == 1
        
        if is_ht_custom:
            # Use the stored custom comment
            head_teacher_comment = comment['head_teacher_comment'] if comment['head_teacher_comment'] else ""
        else:
            # Auto-generate based on student average
            if avg > 0:
                auto_comment = get_head_teacher_comment_by_average(avg)
                head_teacher_comment = auto_comment if auto_comment else ""
            else:
                head_teacher_comment = ""

    # Fetch psychomotor ratings
    psychomotor = get_psychomotor_rating(student_name, class_name, term, session)
    psychomotor_ratings = {
        'punctuality': psychomotor['punctuality'] if psychomotor else 0,
        'neatness': psychomotor['neatness'] if psychomotor else 0,
        'honesty': psychomotor['honesty'] if psychomotor else 0,
        'cooperation': psychomotor['cooperation'] if psychomotor else 0,
        'leadership': psychomotor['leadership'] if psychomotor else 0,
        'perseverance': psychomotor['perseverance'] if psychomotor else 0,
        'politeness': psychomotor['politeness'] if psychomotor else 0,
        'obedience': psychomotor['obedience'] if psychomotor else 0,
        'attentiveness': psychomotor['attentiveness'] if psychomotor else 0,
        'attitude_to_work': psychomotor['attitude_to_work'] if psychomotor else 0
    }

    # Create score dictionary for quick lookup
    score_dict = {score[2]: score for score in student_scores}

    # Prepare data for template with all subjects
    subjects_data = []
    for subject in all_subjects:
        subject_name = subject[1]
        if subject_name in score_dict:
            score = score_dict[subject_name]
            subjects_data.append({
                'subject': subject_name,
                'test': int(score[3]) if score[3] is not None else "-",
                'exam': int(score[4]) if score[4] is not None else "-",
                'total': int(score[5]) if score[5] is not None else "-",
                'grade': score[6] if score[6] else "-",
                'position': format_ordinal(position_data['position']) if position_data else "-"
            })
        else:
            subjects_data.append({
                'subject': subject_name,
                'test': "-",
                'exam': "-",
                'total': "-",
                'grade': "-",
                'position': "-"
            })

    next_term, next_session = calculate_next_term(term, session)
    next_term_date = get_next_term_begin_date(next_term, next_session)
    next_term_info = get_next_term_info(next_term, next_session)

    if next_term_info:
        if next_term_info['fees'] is not None:
            next_term_fee = next_term_info['fees'].get(class_name, "#")
            if next_term_fee == "0":
                next_term_fee = "-"
        else:
            next_term_fee = "-"
    else:
        next_term_fee = "-"
    # Load and render template
    try:
        env = Environment(loader=FileSystemLoader("templates"))
        template = env.get_template("report_template.html")
        html_out = template.render(
            school_name=APP_CONFIG["school_name"],
            school_address=APP_CONFIG["school_address"],
            name=student_name,
            class_name=class_name,
            term=term,
            session=session,
            is_secondary_class=is_secondary_class,
            is_primary_class=is_primary_class,
            gender=gender,
            class_size=class_size,
            class_average=class_average,
            average=round(avg, 2),
            grade=grade,
            position=position,
            is_sss2_or_sss3=is_sss2_or_sss3,
            grade_distribution=grade_distribution,
            subjects=subjects_data,
            total_test=total_test,
            total_exam=total_exam,
            grand_total=grand_total,
            class_teacher_comment=class_teacher_comment,
            head_teacher_comment=head_teacher_comment,
            psychomotor=psychomotor_ratings,
            next_term_date=next_term_date,
            next_term_fee=f"₦{next_term_fee}",
            current_date=current_date
        )

        # Generate PDF - FORCE ONE PAGE
        os.makedirs("data/reports", exist_ok=True)
        safe_name = "".join(c if c.isalnum() or c in (' ', '_') else "_" for c in student_name)
        output_path = os.path.join("data/reports", f"{safe_name.replace(' ', '_')}_{term.replace(' ', '_')}_{session.replace('/', '_')}_report.pdf")
        
        # Create CSS with page break prevention
        one_page_css = CSS(string='''
            @page {
                size: A4;
                margin-top: 10mm;
                margin-bottom: -8mm;
                margin-left: 15mm;
                margin-right: 15mm;
            }
            body {
                margin: 0;
                padding: 0;
            }
            * {
                page-break-inside: avoid !important;
                break-inside: avoid !important;
            }
            table {
                page-break-inside: avoid !important;
            }
            .report-card {
                page-break-inside: avoid !important;
            }
        ''')
        
        HTML(string=html_out, base_url=os.getcwd()).write_pdf(
            output_path,
            stylesheets=[
                CSS('templates/report_card_styles.css'),
                one_page_css
            ]
        )
        return output_path
        
    except Exception as e:
        st.error(f"Error generating PDF: {e}")
        return None

def merge_pdfs_into_single_file(pdf_paths, class_name, term, session):
    """Merge all PDFs into a single PDF file"""
    try:
        os.makedirs("data/reports", exist_ok=True)
        merged_filename = f"{class_name.replace(' ', '_')}_{term.replace(' ', '_')}_{session.replace('/', '_')}_All_Reports.pdf"
        merged_path = os.path.join("data/reports", merged_filename)
        
        merger = PdfMerger()
        
        for pdf_path in pdf_paths:
            if os.path.exists(pdf_path):
                merger.append(pdf_path)
        
        merger.write(merged_path)
        merger.close()
        
        return merged_path
    except Exception as e:
        st.error(f"Error merging PDFs: {e}")
        return None

def create_zip_file(pdf_paths, class_name, term, session):
    """Create a zip file containing all generated PDFs - kept for email functionality"""
    try:
        os.makedirs("data/reports", exist_ok=True)
        zip_filename = f"{class_name.replace(' ', '_')}_{term.replace(' ', '_')}_{session.replace('/', '_')}_Reports.zip"
        zip_path = os.path.join("data/reports", zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for pdf_path in pdf_paths:
                if os.path.exists(pdf_path):
                    # Add file to zip with just the filename (not full path)
                    zipf.write(pdf_path, os.path.basename(pdf_path))
        
        return zip_path
    except Exception as e:
        st.error(f"Error creating zip file: {e}")
        return None
