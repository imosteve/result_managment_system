"""Report Card PDF generation module - ReportLab version (Exact WeasyPrint replica)"""

import streamlit as st
import re
import os
import zipfile
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm, inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas
from PyPDF2 import PdfMerger
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from main_utils import assign_grade, format_ordinal
from database import (
    get_students_by_class, get_student_scores, 
    get_class_average, get_student_grand_totals, get_comment, get_subjects_by_class,
    get_psychomotor_rating, get_grade_distribution, get_next_term_begin_date, get_next_term_info
)
from config import APP_CONFIG

# Register Arial fonts if available (fallback to Helvetica if not)
try:
    # Try different possible Arial font paths
    try:
        pdfmetrics.registerFont(TTFont('Arial', 'arial.ttf'))
        pdfmetrics.registerFont(TTFont('Arial-Bold', 'arialbd.ttf'))
    except:
        # Try Windows font directory
        pdfmetrics.registerFont(TTFont('Arial', 'C:/Windows/Fonts/arial.ttf'))
        pdfmetrics.registerFont(TTFont('Arial-Bold', 'C:/Windows/Fonts/arialbd.ttf'))
    FONT_NAME = 'Arial'
    FONT_NAME_BOLD = 'Arial-Bold'
except:
    # Fallback to Helvetica if Arial is not available
    FONT_NAME = 'Helvetica'
    FONT_NAME_BOLD = 'Helvetica-Bold'

# Email Configuration
SMTP_SERVER = os.getenv('SMTP_SERVER', "smtp.gmail.com")
SMTP_PORT = int(os.getenv('SMTP_PORT', 465))
EMAIL_SENDER = os.getenv('EMAIL_SENDER', "SUIS Terminal Result <ideas.elites@gmail.com>")
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', "lkydcrsaritupygu")


def calculate_next_term(current_term, current_session):
    """Intelligently calculate the next term and session"""
    term_map = {"1st Term": "2nd Term", "2nd Term": "3rd Term", "3rd Term": "1st Term"}
    next_term = term_map.get(current_term, "1st Term")
    
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


class ReportCardCanvas(canvas.Canvas):
    """Custom canvas for adding watermark, stamps, and borders"""
    def __init__(self, *args, **kwargs):
        self.is_secondary = kwargs.pop('is_secondary_class', False)
        self.is_primary = kwargs.pop('is_primary_class', False)
        self.current_date_str = kwargs.pop('current_date_str', '')
        super().__init__(*args, **kwargs)

    def showPage(self):
        # 🔥 DRAW STAMPS LAST (TOP LAYER)
        self.draw_page_elements()
        super().showPage()

    def draw_page_elements(self):
        """Draw watermark, stamps, border, and Christmas stamp"""
        page_width, page_height = A4
        
        # # Draw border (2px solid black)
        # self.setStrokeColor(colors.black)
        # self.setLineWidth(2)
        # self.rect(10*mm, 10*mm, page_width - 20*mm, page_height - 20*mm)
        
        # Draw watermark (centered, faded logo)
        watermark_path = "static/logos/SU_logo.png"
        if os.path.exists(watermark_path):
            self.saveState()
            self.setFillAlpha(0.1)
            # Center the watermark
            watermark_size = 300
            x = (page_width - watermark_size) / 2
            y = (page_height - watermark_size) / 2
            self.drawImage(watermark_path, x, y, 
                          width=watermark_size, height=watermark_size, 
                          mask='auto', preserveAspectRatio=True)
            self.restoreState()
        
        # Draw stamps and signature (positioned exactly as in CSS)
        if self.is_secondary:
            # SSS stamp
            stamp_path = "static/stamps/su_stamp_sss.png"
            if os.path.exists(stamp_path):
                self.saveState()
                self.setFillAlpha(1.0)
                # Position: top: 76.5%, left: 81% with rotation and scale
                stamp_x = page_width * 0.81
                stamp_y = page_height * 0.195  # 100% - 76.5% = 23.5%
                self.translate(stamp_x, stamp_y)
                self.rotate(15)  # 345 degrees = -15
                self.scale(1, 1)
                self.drawImage(stamp_path, -50, -50, width=100, height=100, 
                              mask='auto', preserveAspectRatio=True)
                self.restoreState()
            
            # Principal signature
            sig_path = "static/stamps/signature_principal.png"
            if os.path.exists(sig_path):
                self.saveState()
                self.setFillAlpha(1.0)
                sig_x = page_width * 0.82
                sig_y = page_height * 0.215  # 100% - 74% = 26%
                self.translate(sig_x, sig_y)
                self.rotate(15)
                self.scale(1.0, 1.0)
                self.drawImage(sig_path, -50, -50, width=100, height=100,
                              mask='auto', preserveAspectRatio=True)
                self.restoreState()
        
        elif self.is_primary:
            # Primary stamp
            stamp_path = "static/stamps/su_stamp_primary.png"
            if os.path.exists(stamp_path):
                self.saveState()
                self.setFillAlpha(1.0)
                stamp_x = page_width * 0.82
                stamp_y = page_height * 0.20
                self.translate(stamp_x, stamp_y)
                self.rotate(15)
                self.scale(1, 1)
                self.drawImage(stamp_path, -50, -50, width=100, height=100,
                              mask='auto', preserveAspectRatio=True)
                self.restoreState()
            
            # Head teacher signature
            sig_path = "static/stamps/signature_ht.png"
            if os.path.exists(sig_path):
                self.saveState()
                self.setFillAlpha(1.0)
                sig_x = page_width * 0.82
                sig_y = page_height * 0.22
                self.translate(sig_x, sig_y)
                self.rotate(15)
                self.scale(0.7, 0.7)
                self.drawImage(sig_path, -50, -50, width=100, height=100,
                              mask='auto', preserveAspectRatio=True)
                self.restoreState()
        
        # Draw stamp date
        if self.current_date_str:
            self.saveState()
            self.setFillColor(colors.HexColor('#00064a'))
            self.setFont(FONT_NAME_BOLD, 6)
            date_x = page_width * 0.84
            date_y = page_height * 0.193  # 100% - 76.9%
            self.translate(date_x, date_y)
            self.rotate(15)
            self.drawCentredString(0, 0, self.current_date_str)
            self.restoreState()
        
        # # Draw Christmas stamp (bottom center)
        # self.saveState()
        # self.setFillAlpha(0.8)
        # christmas_x = page_width / 2
        # christmas_y = page_height * 0.10  # 100% - 90%
        # self.translate(christmas_x, christmas_y)
        # self.scale(0.4, 0.4)
        
        # Christmas stamp border with gradient effect
        # self.setFillColor(colors.HexColor('#c41e3a'))
        # self.roundRect(-90, -40, 180, 80, 10, fill=1, stroke=0)
        
        # # Gold double border
        # self.setStrokeColor(colors.HexColor('#FFD700'))
        # self.setLineWidth(3)
        # self.roundRect(-90, -40, 180, 80, 10, fill=0, stroke=1)
        # self.setLineWidth(1.5)
        # self.roundRect(-87, -37, 174, 74, 10, fill=0, stroke=1)
        
        # # Christmas text
        # self.setFillColor(colors.white)
        # self.setFont(FONT_NAME_BOLD, 16)
        # self.drawCentredString(0, 15, '❇ ★ ❇')
        # self.setFont(FONT_NAME_BOLD, 20)
        # self.drawCentredString(0, -5, 'MERRY CHRISTMAS')
        # self.setFont(FONT_NAME_BOLD, 14)
        # self.drawCentredString(0, -22, '& HAPPY NEW YEAR!')
        # self.setFont(FONT_NAME_BOLD, 12)
        # self.drawCentredString(0, -35, '2025')
        
        # self.restoreState()


def generate_report_card(student_name, class_name, term, session, is_secondary_class, is_primary_class):
    """Generate PDF report card for a student using ReportLab - exact WeasyPrint replica"""
    from database import get_head_teacher_comment_by_average
    
    user_id = st.session_state.user_id
    role = st.session_state.role

    # Fetch student data
    students = get_students_by_class(class_name, term, session, user_id, role)
    student_data = next((s for s in students if s[1] == student_name), None)
    if not student_data:
        return None
    
    gender = student_data[2]
    class_size = len(students)

    # Fetch student scores
    student_scores = get_student_scores(student_name, class_name, term, session, user_id, role)
    all_subjects = get_subjects_by_class(class_name, term, session, user_id, role)
    
    if not all_subjects:
        return None

    # Calculate totals and averages
    if student_scores:
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

    # Class average and position
    class_average = get_class_average(class_name, term, session, user_id, role)
    grand_totals = get_student_grand_totals(class_name, term, session, user_id, role)
    position_data = next((gt for gt in grand_totals if gt['student_name'] == student_name), None)
    
    is_sss2_or_sss3 = bool(re.match(r"SSS [23].*$", class_name))
    if is_sss2_or_sss3:
        grade_distribution = get_grade_distribution(student_name, class_name, term, session, user_id, role)
        position = ""
    else:
        grade_distribution = ""
        position = format_ordinal(position_data['position']) if position_data else "-"

    current_date = datetime.now().strftime("%d %b %Y")
    
    # Fetch comments
    comment = get_comment(student_name, class_name, term, session)
    class_teacher_comment = ""
    head_teacher_comment = ""
    
    if comment:
        class_teacher_comment = comment['class_teacher_comment'] if comment['class_teacher_comment'] else ""
        is_ht_custom = comment.get('head_teacher_comment_custom', 0) == 1
        
        if is_ht_custom:
            head_teacher_comment = comment['head_teacher_comment'] if comment['head_teacher_comment'] else ""
        else:
            if avg > 0:
                auto_comment = get_head_teacher_comment_by_average(avg)
                head_teacher_comment = auto_comment if auto_comment else ""
            else:
                head_teacher_comment = ""

    # Psychomotor ratings
    psychomotor = get_psychomotor_rating(student_name, class_name, term, session)
    psychomotor_ratings = {
        'Punctuality': psychomotor['punctuality'] if psychomotor else 0,
        'Neatness': psychomotor['neatness'] if psychomotor else 0,
        'Honesty': psychomotor['honesty'] if psychomotor else 0,
        'Cooperation': psychomotor['cooperation'] if psychomotor else 0,
        'Leadership': psychomotor['leadership'] if psychomotor else 0,
        'Perseverance': psychomotor['perseverance'] if psychomotor else 0,
        'Politeness': psychomotor['politeness'] if psychomotor else 0,
        'Obedience': psychomotor['obedience'] if psychomotor else 0,
        'Attentiveness': psychomotor['attentiveness'] if psychomotor else 0,
        'Attitude to work': psychomotor['attitude_to_work'] if psychomotor else 0
    }

    # Prepare subjects data
    score_dict = {score[2]: score for score in student_scores}
    subjects_data = []
    
    for subject in all_subjects:
        subject_name = subject[1]
        if subject_name in score_dict:
            score = score_dict[subject_name]
            subj_grade = score[6] if score[6] else "-"
            # Get remark based on grade
            remarks = {
                'A': 'Excellent', 'B': 'Very Good', 'C': 'Good',
                'D': 'Pass', 'E': 'Weak Pass', 'F': 'Fail'
            }
            remark = remarks.get(subj_grade, ' ')
            
            subjects_data.append({
                'subject': subject_name,
                'test': int(score[3]) if score[3] is not None else "-",
                'exam': int(score[4]) if score[4] is not None else "-",
                'total': int(score[5]) if score[5] is not None else "-",
                'grade': subj_grade,
                'remark': remark
            })
        else:
            subjects_data.append({
                'subject': subject_name,
                'test': "-", 'exam': "-", 'total': "-",
                'grade': "-", 'remark': ' '
            })

    # Next term info
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

    # Generate PDF
    try:
        os.makedirs("data/reports", exist_ok=True)
        safe_name = "".join(c if c.isalnum() or c in (' ', '_') else "_" for c in student_name)
        output_path = os.path.join("data/reports", 
            f"{safe_name.replace(' ', '_')}_{term.replace(' ', '_')}_{session.replace('/', '_')}_report.pdf")
        
        # Create document with custom canvas
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            topMargin=10*mm,
            bottomMargin=10*mm,
            leftMargin=15*mm,
            rightMargin=15*mm
        )
        
        elements = []
        styles = getSampleStyleSheet()
        
        # Custom styles matching CSS exactly
        title_style = ParagraphStyle(
            'Title',
            # parent=styles['Heading1'],
            parent=styles['Normal'],
            fontSize=17,
            textColor=colors.black,
            spaceAfter=8,
            alignment=TA_CENTER,
            fontName=FONT_NAME_BOLD,
            leading=13
        )
        
        subtitle_style = ParagraphStyle(
            'Subtitle',
            parent=styles['Normal'],
            fontSize=12,
            textColor=colors.black,
            spaceAfter=4,
            alignment=TA_CENTER,
            fontName=FONT_NAME,
            leading=13
        )
        
        report_title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Normal'],
            fontSize=13,
            textColor=colors.black,
            spaceAfter=8,
            alignment=TA_CENTER,
            fontName=FONT_NAME_BOLD,
            leading=13
        )
        
        # Header with logo
        logo_path = "static/logos/SU_logo.png"
        if os.path.exists(logo_path):
            logo = Image(logo_path, width=60, height=60)
        else:
            logo = Paragraph("<b>LOGO</b>", title_style)
        
        header_data = [[
            logo,
            [
                Paragraph(f"<b>{APP_CONFIG['school_name']}</b>", title_style),
                Paragraph(APP_CONFIG['school_address'], subtitle_style),
                Paragraph(f"<b>TERMLY REPORT FOR {term.upper()}, {session} SESSION</b>", report_title_style)
            ]
        ]]
        
        header_table = Table(header_data, colWidths=[80, 430])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 10))
        
        # Student info table (3 rows, styled exactly like CSS)
        gender_display = 'MALE' if gender == 'M' else 'FEMALE' if gender == 'F' else ''
        
        # Row 1: Name only
        info_row1 = [
            [Paragraph("<b>Name:</b>", ParagraphStyle('InfoLabel', fontSize=8, fontName=FONT_NAME_BOLD, alignment=TA_LEFT)),
            Paragraph(f"<b>{student_name.upper()}</b>", ParagraphStyle('InfoValue', fontSize=12, fontName=FONT_NAME_BOLD, alignment=TA_CENTER))]
        ]
        
        # Row 2: Gender, Class, No. in Class
        info_row2 = [
            Paragraph("<b>Gender:</b>", ParagraphStyle('InfoLabel', fontSize=8, fontName=FONT_NAME_BOLD)),
            Paragraph(gender_display, ParagraphStyle('InfoValue', fontSize=10, alignment=TA_CENTER)),
            Paragraph("<b>Class:</b>", ParagraphStyle('InfoLabel', fontSize=8, fontName=FONT_NAME_BOLD)),
            Paragraph(class_name.upper(), ParagraphStyle('InfoValue', fontSize=10, alignment=TA_CENTER)),
            Paragraph("<b>No. in Class:</b>", ParagraphStyle('InfoLabel', fontSize=8, fontName=FONT_NAME_BOLD)),
            Paragraph(str(class_size), ParagraphStyle('InfoValue', fontSize=10, alignment=TA_CENTER))
        ]
        
        # Row 3: Student's Average, Class Average, Position/Grade
        student_avg_label = "Student's Average:" if is_secondary_class else "Pupil's Average:"
        position_label = "Grades:" if is_sss2_or_sss3 else "Position:"
        position_value = grade_distribution if is_sss2_or_sss3 else position
        
        info_row3 = [
            Paragraph(f"<b>{student_avg_label}</b>", ParagraphStyle('InfoLabel', fontSize=8, fontName=FONT_NAME_BOLD)),
            Paragraph(f"{avg:.2f}", ParagraphStyle('InfoValue', fontSize=10, alignment=TA_CENTER)),
            Paragraph("<b>Class Average:</b>", ParagraphStyle('InfoLabel', fontSize=8, fontName=FONT_NAME_BOLD)),
            Paragraph(f"{class_average:.1f}", ParagraphStyle('InfoValue', fontSize=10, alignment=TA_CENTER)),
            Paragraph(f"<b>{position_label}</b>", ParagraphStyle('InfoLabel', fontSize=8, fontName=FONT_NAME_BOLD)),
            Paragraph(str(position_value), ParagraphStyle('InfoValue', fontSize=10, alignment=TA_CENTER))
        ]
        
        # Create three separate tables for the three rows
        info_table1 = Table(info_row1, colWidths=[90, 430])
        info_table1.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.black),   # outer border only
            # ('LINEBEFORE', (0, 0), (0, 0), 0, colors.white),  # no vertical divider
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        
        info_table2 = Table([info_row2], colWidths=[90, 83, 60, 130, 80, 77])
        info_table2.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.black),  # outer border
            ('LINEAFTER', (1, 0), (1, 0), 1, colors.black),
            ('LINEAFTER', (3, 0), (3, 0), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))

        
        info_table3 = Table([info_row3], colWidths=[90, 83, 80, 110, 50, 107])
        info_table3.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.black),  # outer border
            ('LINEAFTER', (1, 0), (1, 0), 1, colors.black),
            ('LINEAFTER', (3, 0), (3, 0), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        
        elements.append(info_table1)
        elements.append(info_table2)
        elements.append(info_table3)
        elements.append(Spacer(1, 10))
        
        # Performance section title
        perf_title_style = ParagraphStyle('PerfTitle', fontSize=9, fontName=FONT_NAME_BOLD, alignment=TA_CENTER, spaceAfter=2)
        elements.append(Paragraph("PERFORMANCE IN SUBJECTS", perf_title_style))
        
        # Subjects table
        subjects_header = [
            Paragraph('<b>SUBJECTS</b>', ParagraphStyle('Header', fontSize=10, fontName=FONT_NAME_BOLD, alignment=TA_CENTER)),
            Paragraph('<b>Test<br/>(30%)</b>', ParagraphStyle('Header', fontSize=10, fontName=FONT_NAME_BOLD, alignment=TA_CENTER)),
            Paragraph('<b>Exam<br/>(70%)</b>', ParagraphStyle('Header', fontSize=10, fontName=FONT_NAME_BOLD, alignment=TA_CENTER)),
            Paragraph('<b>Total<br/>(100%)</b>', ParagraphStyle('Header', fontSize=10, fontName=FONT_NAME_BOLD, alignment=TA_CENTER)),
            Paragraph('<b>Grade</b>', ParagraphStyle('Header', fontSize=10, fontName=FONT_NAME_BOLD, alignment=TA_CENTER)),
            Paragraph('<b>Remarks</b>', ParagraphStyle('Header', fontSize=10, fontName=FONT_NAME_BOLD, alignment=TA_CENTER))
        ]
        
        subjects_table_data = [subjects_header]
        cell_style = ParagraphStyle('Cell', fontSize=10, alignment=TA_CENTER)
        subject_style = ParagraphStyle('Subject', fontSize=10, alignment=TA_LEFT)
        
        for subj in subjects_data:
            subjects_table_data.append([
                Paragraph(subj['subject'], subject_style),
                Paragraph(str(subj['test']), cell_style),
                Paragraph(str(subj['exam']), cell_style),
                Paragraph(str(subj['total']), cell_style),
                Paragraph(subj['grade'], cell_style),
                Paragraph(subj['remark'], cell_style)
            ])
        
        # Totals row
        total_style = ParagraphStyle('Total', fontSize=10, fontName=FONT_NAME_BOLD, alignment=TA_CENTER)
        subjects_table_data.append([
            Paragraph('<b>Total</b>', ParagraphStyle('TotalLeft', fontSize=10, fontName=FONT_NAME_BOLD, alignment=TA_LEFT)),
            Paragraph(f'<b>{total_test}</b>', total_style),
            Paragraph(f'<b>{total_exam}</b>', total_style),
            Paragraph(f'<b>{grand_total}</b>', total_style),
            Paragraph('', total_style),
            Paragraph('', total_style)
        ])
        
        subjects_table = Table(subjects_table_data, colWidths=[215, 52, 52, 52, 52, 97])
        subjects_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.white),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.white),
            ('TOPPADDING', (0, 0), (-1, -1), 1.8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1.8),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(subjects_table)
        elements.append(Spacer(1, 10))
        
        # Conduct and Grading side by side
        conduct_title_style = ParagraphStyle('CondTitle', fontSize=8, fontName=FONT_NAME_BOLD, 
                                            textColor=colors.red, alignment=TA_CENTER, spaceAfter=1)
        conduct_subtitle_style = ParagraphStyle('CondSubtitle', fontSize=8, fontName=FONT_NAME,
                                               textColor=colors.red, alignment=TA_CENTER, spaceAfter=2)
        
        # Psychomotor table - CENTERED with conduct title
        psych_header = [
            Paragraph('<b>RATING</b>', ParagraphStyle('PsychHeader', fontSize=8, fontName=FONT_NAME_BOLD, alignment=TA_CENTER)),
            Paragraph('', ParagraphStyle('Empty', fontSize=8)),
            Paragraph('<b>RATING</b>', ParagraphStyle('PsychHeader', fontSize=8, fontName=FONT_NAME_BOLD, alignment=TA_CENTER)),
            Paragraph('', ParagraphStyle('Empty', fontSize=8))
        ]
        
        psych_data = [psych_header]
        psych_items = list(psychomotor_ratings.items())
        psych_cell_style = ParagraphStyle('PsychCell', fontSize=8, fontName=FONT_NAME, alignment=TA_LEFT)
        psych_rating_style = ParagraphStyle('PsychRating', fontSize=8, fontName=FONT_NAME_BOLD, alignment=TA_CENTER)
        
        for i in range(0, len(psych_items), 2):
            row = [
                Paragraph(psych_items[i][0], psych_cell_style),
                Paragraph(str(psych_items[i][1]), psych_rating_style)
            ]
            if i + 1 < len(psych_items):
                row.extend([
                    Paragraph(psych_items[i + 1][0], psych_cell_style),
                    Paragraph(str(psych_items[i + 1][1]), psych_rating_style)
                ])
            else:
                row.extend([Paragraph('', psych_cell_style), Paragraph('', psych_rating_style)])
            psych_data.append(row)
        
        psych_table = Table(psych_data, colWidths=[80, 35, 80, 35])
        psych_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8f5e8')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ]))
        
        # Grading system box
        grading_title_style = ParagraphStyle('GradeTitle', fontSize=9, fontName=FONT_NAME_BOLD,
                                            textColor=colors.red, alignment=TA_CENTER, spaceAfter=5)
        grading_item_style = ParagraphStyle('GradeItem', fontSize=9, fontName=FONT_NAME, alignment=TA_LEFT)
        
        grading_data = [
            [Paragraph('<b>Grading System</b>', grading_title_style)]
        ]
        grading_items = [
            'A - Excellent   -    80% & Above',
            'B - Very Good    -    70% - 79%',
            'C - Good    -    60% - 69%',
            'D - Pass    -    50% - 59%',
            'E - Weak Pass    -    45% - 49%',
            'F - Fail    -    1% - 44%'
        ]
        
        for item in grading_items:
            grading_data.append([Paragraph(item, grading_item_style)])
        
        grading_table = Table(grading_data, colWidths=[160])
        grading_table.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))
        
        # Create centered conduct section with psychomotor table
        conduct_section = [
            Paragraph("OBSERVATION OF CONDUCT", conduct_title_style),
            Paragraph("(5 - Exceptional) (4 - Excellent) (3 - Good) (2 - Average) (1 - Below Average)", 
                     conduct_subtitle_style),
            psych_table
        ]
        
        # Combine conduct (centered) and grading side by side
        conduct_grading_data = [[conduct_section, "", grading_table]]
        
        conduct_grading_table = Table(conduct_grading_data, colWidths=[300, 60, 160])
        conduct_grading_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),  # Center the conduct section
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(conduct_grading_table)
        elements.append(Spacer(1, 10))
        
        # Comments section
        comments_title_style = ParagraphStyle('CommTitle', fontSize=8, fontName=FONT_NAME_BOLD, 
                                             alignment=TA_CENTER, spaceAfter=2)
        elements.append(Paragraph("COMMENTS & REMARKS", comments_title_style))
        
        comment_label_style = ParagraphStyle('CommLabel', fontSize=8, fontName=FONT_NAME_BOLD, alignment=TA_LEFT)
        comment_text_style = ParagraphStyle('CommText', fontSize=9, alignment=TA_LEFT)
        
        # Class teacher comment
        ct_comment_data = [[
            Paragraph("Class Teacher's Comment:", comment_label_style),
            Paragraph(class_teacher_comment if class_teacher_comment else '', comment_text_style)
        ]]
        ct_comment_table = Table(ct_comment_data, colWidths=[130, 390])
        ct_comment_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        elements.append(ct_comment_table)
        
        # Head teacher/Principal comment
        ht_label = "Principal's Comment:" if is_secondary_class else "Head Teacher's Comment:"
        ht_comment_data = [[
            Paragraph(ht_label, comment_label_style),
            Paragraph(head_teacher_comment if head_teacher_comment else '', comment_text_style)
        ]]
        ht_comment_table = Table(ht_comment_data, colWidths=[130, 390])
        ht_comment_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        elements.append(ht_comment_table)
        elements.append(Spacer(1, 10))
        
        # Footer section (dark green background)
        footer_style = ParagraphStyle('Footer', fontSize=8, fontName=FONT_NAME_BOLD, 
                                     textColor=colors.white, alignment=TA_LEFT)
        footer_center_style = ParagraphStyle('FooterCenter', fontSize=8, fontName=FONT_NAME_BOLD, 
                                            textColor=colors.white, alignment=TA_CENTER)
        footer_right_style = ParagraphStyle('FooterRight', fontSize=8, fontName=FONT_NAME_BOLD, 
                                           textColor=colors.white, alignment=TA_RIGHT)
        
        # Format class name for fees display
        display_class = class_name.replace("KINDERGARTEN", "KG") if class_name.upper().startswith("KINDERGARTEN") else class_name
        
        footer_fees = [
            Paragraph("Next Terms School Fees:", footer_style),
            Paragraph(f"For {display_class} - #{next_term_fee}" if next_term_fee != "-" else f"For {display_class} - -", footer_style)
        ]
        
        footer_account = [
            Paragraph("Account Information:", footer_center_style),
            Paragraph("ECOBANK 0272005494 Scripture Union Int'l Schools", footer_center_style),
            Paragraph("STERLING BANK 0072344744 Scripture Union Int'l Schools", footer_center_style)
        ]
        
        footer_next_term = [
            Paragraph(f"<b>Next Term Begins On:</b> {next_term_date if next_term_date else '-'}", footer_right_style)
        ]
        
        footer_data = [[footer_fees, footer_account, footer_next_term]]
        
        footer_table = Table(footer_data, colWidths=[130, 260, 130])
        footer_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#3b5625')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        elements.append(footer_table)
        
        # Create custom canvas maker function that accepts all ReportLab arguments
        def make_canvas(filename, **kwargs):
            # Pass through all kwargs to ReportCardCanvas
            return ReportCardCanvas(
                filename,
                is_secondary_class=is_secondary_class,
                is_primary_class=is_primary_class,
                current_date_str=current_date,
                **kwargs
            )
        
        # Build PDF with custom
        doc.build(elements, canvasmaker=make_canvas)
        
        return output_path
        
    except Exception as e:
        st.error(f"Error generating PDF: {e}")
        import traceback
        st.error(traceback.format_exc())
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
    """Create a zip file containing all generated PDFs"""
    try:
        os.makedirs("data/reports", exist_ok=True)
        zip_filename = f"{class_name.replace(' ', '_')}_{term.replace(' ', '_')}_{session.replace('/', '_')}_Reports.zip"
        zip_path = os.path.join("data/reports", zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for pdf_path in pdf_paths:
                if os.path.exists(pdf_path):
                    zipf.write(pdf_path, os.path.basename(pdf_path))
        
        return zip_path
    except Exception as e:
        st.error(f"Error creating zip file: {e}")
        return None