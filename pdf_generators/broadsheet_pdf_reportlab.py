"""Broadsheet PDF generation module - ReportLab version matching WeasyPrint design"""

import io
import os
import re
from pathlib import Path
from reportlab.lib.pagesizes import A2, landscape
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from PyPDF2 import PdfMerger
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

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
LOGO_PATH = BASE_DIR / 'static' / 'logos' / 'SU_logo.png'

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

class WatermarkCanvas(canvas.Canvas):
    """Custom canvas class to add watermark on every page"""
    
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self.pages = []
        
    def showPage(self):
        self.pages.append(dict(self.__dict__))
        self._startPage()
        
    def save(self):
        for page in self.pages:
            self.__dict__.update(page)
            self.draw_watermark()
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)
        
    def draw_watermark(self):
        """Draw watermark logo in center of page"""
        if LOGO_PATH.exists():
            self.saveState()
            page_width, page_height = self._pagesize
            watermark_size = 400
            x = (page_width - watermark_size) / 2
            y = (page_height - watermark_size) / 2
            self.setFillAlpha(0.05)
            self.drawImage(
                str(LOGO_PATH), 
                x, y, 
                width=watermark_size, 
                height=watermark_size,
                mask='auto',
                preserveAspectRatio=True
            )
            self.restoreState()


def get_page_size(num_subjects, num_students):
    """Determine appropriate page size based on data volume"""
    return landscape(A2)


def get_dynamic_sizing(num_subjects, num_students):
    """Get dynamic sizing parameters based on data volume to ensure table fits on A2 landscape"""
    # A2 landscape provides plenty of space, but we need to scale for many subjects
    
    return {
        'body_font': 7,
        'school_name_font': 18,
        'logo_size': 45,
        'header_font': 5,
        'subheader_font': 5,
        'student_name_font': 5,
        'score_font': 6
    }


def calculate_column_widths(num_subjects, page_width):
    """Calculate optimal column widths to fit table within page"""
    # A2 landscape width minus margins (20mm on each side)
    available_width = page_width - 20*mm
    
    # Fixed width columns
    sn_width = 20  # S/N column
    student_width = 100  # Student name column
    grand_total_width = 35  # Grand Total
    average_width = 35  # Average
    position_width = 50  # Position/Grade
    
    # Calculate remaining width for subject columns
    fixed_widths = sn_width + student_width + grand_total_width + average_width + position_width
    remaining_width = available_width - fixed_widths
    
    # Each subject has 3 sub-columns (Test, Exam, Total)
    subject_total_width = remaining_width / num_subjects
    test_width = subject_total_width / 3
    exam_width = subject_total_width / 3
    total_width = subject_total_width / 3
    
    return {
        'sn': sn_width,
        'student': student_width,
        'test': test_width,
        'exam': exam_width,
        'total': total_width,
        'grand_total': grand_total_width,
        'average': average_width,
        'position': position_width
    }


def create_header(class_name, term, session, sizing):
    """Create header with logo and school information"""
    elements = []
    styles = getSampleStyleSheet()
    
    # Create custom styles
    school_name_style = ParagraphStyle(
        'SchoolName',
        parent=styles['Normal'],
        fontSize=sizing['school_name_font'],
        fontName=FONT_NAME_BOLD,
        textColor=colors.black,
        alignment=TA_CENTER,
        spaceAfter=8
    )
    
    address_style = ParagraphStyle(
        'Address',
        parent=styles['Normal'],
        fontSize=12,
        fontName=FONT_NAME,
        textColor=colors.black,
        alignment=TA_CENTER,
        spaceAfter=6
    )
    
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Normal'],
        fontSize=13,
        fontName=FONT_NAME_BOLD,
        textColor=colors.HexColor('#2c5f2d'),
        alignment=TA_CENTER,
        spaceAfter=8
    )
    
    # Create header table with logo and text
    header_data = []
    
    if LOGO_PATH.exists():
        logo = Image(str(LOGO_PATH), width=sizing['logo_size'], height=sizing['logo_size'])
        text_content = [
            Paragraph(SCHOOL_NAME, school_name_style),
            Paragraph(SCHOOL_ADDRESS, address_style),
            Paragraph(f"BROADSHEET FOR {class_name} - {term}, {session} SESSION", title_style)
        ]
        header_data = [[logo, text_content]]
    else:
        text_content = [
            Paragraph(SCHOOL_NAME, school_name_style),
            Paragraph(SCHOOL_ADDRESS, address_style),
            Paragraph(f"BROADSHEET FOR {class_name} - {term}, {session} SESSION", title_style)
        ]
        header_data = [[text_content]]
    
    header_table = Table(header_data, colWidths=[60 if LOGO_PATH.exists() else None, None])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('LINEBELOW', (0, 0), (-1, -1), 2, colors.black),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
    ]))
    
    elements.append(header_table)
    elements.append(Spacer(1, 10))
    
    return elements


# def create_summary_section(class_name, term, session, num_students, num_subjects, class_average=None):
#     """Create summary information section"""
#     elements = []
    
#     summary_style = ParagraphStyle(
#         'Summary',
#         fontSize=9,
#         fontName=FONT_NAME,
#         textColor=colors.black,
#         leading=11
#     )
    
#     summary_label_style = ParagraphStyle(
#         'SummaryLabel',
#         fontSize=9,
#         fontName=FONT_NAME_BOLD,
#         textColor=colors.HexColor('#2c5f2d'),
#         leading=11
#     )
    
#     # Create summary data
#     summary_items = [
#         [Paragraph("<b>Class:</b>", summary_label_style), Paragraph(class_name, summary_style)],
#         [Paragraph("<b>Term:</b>", summary_label_style), Paragraph(term, summary_style)],
#         [Paragraph("<b>Session:</b>", summary_label_style), Paragraph(session, summary_style)],
#         [Paragraph("<b>Number of Students:</b>", summary_label_style), Paragraph(str(num_students), summary_style)],
#         [Paragraph("<b>Number of Subjects:</b>", summary_label_style), Paragraph(str(num_subjects), summary_style)]
#     ]
    
#     if class_average:
#         summary_items.append([
#             Paragraph("<b>Class Average:</b>", summary_label_style), 
#             Paragraph(str(class_average), summary_style)
#         ])
    
#     # Create single-row table for horizontal layout
#     summary_data = [[item for sublist in summary_items for item in sublist]]
    
#     summary_table = Table(summary_data)
#     summary_table.setStyle(TableStyle([
#         ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f0f0f0')),
#         ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#d0cfcf')),
#         ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
#         ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
#         ('LEFTPADDING', (0, 0), (-1, -1), 8),
#         ('RIGHTPADDING', (0, 0), (-1, -1), 8),
#         ('TOPPADDING', (0, 0), (-1, -1), 6),
#         ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
#     ]))
    
#     elements.append(summary_table)
#     elements.append(Spacer(1, 10))
    
#     return elements


def create_summary_section(class_name, term, session, num_students, num_subjects, class_average=None):
    elements = []

    summary_style = ParagraphStyle(
        'Summary',
        fontSize=9,
        fontName=FONT_NAME,
        textColor=colors.black,
        leading=11
    )

    label_color = colors.HexColor('#2c5f2d')
    TAB = '&nbsp;&nbsp;'

    # 🔥 EACH ITEM IS A SINGLE CELL (LABEL + VALUE)
    summary_cells = [
        Paragraph(f'<font name="{FONT_NAME_BOLD}" color="{label_color}">Class:</font> {TAB}{class_name}', summary_style),
        Paragraph(f'<font name="{FONT_NAME_BOLD}" color="{label_color}">Term:</font> {TAB}{term}', summary_style),
        Paragraph(f'<font name="{FONT_NAME_BOLD}" color="{label_color}">Session:</font> {TAB}{session}', summary_style),
        Paragraph(f'<font name="{FONT_NAME_BOLD}" color="{label_color}">Number of Students:</font> {TAB}{num_students}', summary_style),
        Paragraph(f'<font name="{FONT_NAME_BOLD}" color="{label_color}">Number of Subjects:</font> {TAB}{num_subjects}', summary_style),
    ]

    if class_average is not None:
        summary_cells.append(
            Paragraph(
                f'<font name="{FONT_NAME_BOLD}" color="{label_color}">Class Average:</font> {TAB}{class_average}',
                summary_style
            )
        )

    # 🔥 ONE ROW, MANY CELLS — EACH CELL = LABEL: VALUE
    summary_table = Table([summary_cells])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f0f0f0')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#d0cfcf')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))

    elements.append(summary_table)
    elements.append(Spacer(1, 10))
    return elements


def create_broadsheet_table(students_data, subject_names, is_sss2_or_sss3, sizing, col_widths):
    """Create the main broadsheet table with dynamic sizing"""
    
    # Create styles for wrapped text
    header_style = ParagraphStyle(
        'HeaderStyle',
        fontSize=sizing['header_font'],
        fontName=FONT_NAME_BOLD,
        textColor=colors.white,
        alignment=TA_CENTER,
        leading=sizing['header_font'] + 1
    )
    
    subheader_style = ParagraphStyle(
        'SubHeaderStyle',
        fontSize=sizing['subheader_font'],
        fontName=FONT_NAME_BOLD,
        textColor=colors.white,
        alignment=TA_CENTER,
        leading=sizing['subheader_font'] + 0.5
    )
    
    student_name_style = ParagraphStyle(
        'StudentNameStyle',
        fontSize=sizing['student_name_font'],
        fontName=FONT_NAME,
        alignment=TA_LEFT,
        leading=sizing['student_name_font'] + 1
    )
    
    score_style = ParagraphStyle(
        'ScoreStyle',
        fontSize=sizing['score_font'],
        fontName=FONT_NAME,
        alignment=TA_CENTER,
        leading=sizing['score_font'] + 1
    )
    
    # Header row 1 - subject names (wrapped in Paragraphs)
    header_row1 = [
        Paragraph('S/N', header_style),
        Paragraph('STUDENT NAME', header_style)
    ]
    for subject_name in subject_names:
        header_row1.extend([Paragraph(subject_name, header_style), '', ''])
    header_row1.extend([
        Paragraph('GRAND TOTAL', header_style),
        Paragraph('AVERAGE', header_style),
        Paragraph('GRADES' if is_sss2_or_sss3 else 'POSITION', header_style)
    ])
    
    # Header row 2 - test/exam/total with tighter spacing
    header_row2 = ['', '']
    for _ in subject_names:
        header_row2.extend([
            Paragraph('Test<br/>(30%)', subheader_style),
            Paragraph('Exam<br/>(70%)', subheader_style),
            Paragraph('Total<br/>(100%)', subheader_style)
        ])
    header_row2.extend(['', '', ''])
    
    table_data = [header_row1, header_row2]
    
    # Student data rows - wrap all text in Paragraphs
    for idx, student in enumerate(students_data, 1):
        row = [
            Paragraph(str(idx), score_style),
            Paragraph(student['name'], student_name_style)
        ]
        
        for subject_name in subject_names:
            scores = student['scores'].get(subject_name, {'test': '', 'exam': '', 'total': ''})
            row.extend([
                Paragraph(str(scores['test']) if scores['test'] else '', score_style),
                Paragraph(str(scores['exam']) if scores['exam'] else '', score_style),
                Paragraph(str(scores['total']) if scores['total'] else '', score_style)
            ])
        
        row.append(Paragraph(str(student['grand_total']) if student['grand_total'] else '', score_style))
        row.append(Paragraph(str(student['average']) if student['average'] else '', score_style))
        
        position_text = student['grade'] if is_sss2_or_sss3 else student['position'] if student['position'] else ''
        row.append(Paragraph(str(position_text), student_name_style))
        
        table_data.append(row)
    
    # Build column widths list
    table_col_widths = [col_widths['sn'], col_widths['student']]
    for _ in subject_names:
        table_col_widths.extend([col_widths['test'], col_widths['exam'], col_widths['total']])
    table_col_widths.extend([col_widths['grand_total'], col_widths['average'], col_widths['position']])
    
    # Create table
    table = Table(table_data, colWidths=table_col_widths, repeatRows=2)
    
    # Calculate style commands
    num_cols = len(header_row1)
    num_rows = len(table_data)
    
    style_commands = [
        # Outer border
        ('BOX', (0, 0), (-1, -1), 2, colors.black),
        ('INNERGRID', (0, 0), (-1, -1), 1, colors.black),
        
        # Header row 1 - main subject headers
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b7a3c')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), FONT_NAME_BOLD),
        ('FONTSIZE', (0, 0), (-1, 0), sizing['header_font']),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        
        # Header row 2 - test/exam/total
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#3b7a3c')),
        ('TEXTCOLOR', (0, 1), (-1, 1), colors.white),
        ('FONTNAME', (0, 1), (-1, 1), FONT_NAME_BOLD),
        ('FONTSIZE', (0, 1), (-1, 1), sizing['subheader_font']),
        ('ALIGN', (0, 1), (-1, 1), 'CENTER'),
        ('VALIGN', (0, 1), (-1, 1), 'MIDDLE'),
        
        # All body cells
        ('FONTNAME', (0, 2), (-1, -1), FONT_NAME),
        ('FONTSIZE', (0, 2), (-1, -1), sizing['score_font']),
        ('ALIGN', (0, 2), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 2), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        
        # S/N column
        ('FONTSIZE', (0, 0), (0, -1), sizing['score_font']),
        
        # Student name column - left aligned
        ('ALIGN', (1, 2), (1, -1), 'LEFT'),
        ('LEFTPADDING', (1, 2), (1, -1), 4),
        ('FONTSIZE', (1, 2), (1, -1), sizing['student_name_font']),
        
        # Span S/N and Student Name in header
        ('SPAN', (0, 0), (0, 1)),
        ('SPAN', (1, 0), (1, 1)),
    ]
    
    # Span subject headers (3 columns each)
    col_idx = 2
    for _ in subject_names:
        style_commands.append(('SPAN', (col_idx, 0), (col_idx + 2, 0)))
        style_commands.append(('BACKGROUND', (col_idx, 0), (col_idx + 2, 0), colors.HexColor('#3b7a3c')))
        
        # Highlight total column
        for row_idx in range(2, num_rows):
            style_commands.append(('BACKGROUND', (col_idx + 2, row_idx), (col_idx + 2, row_idx), colors.HexColor('#faf5e4')))
            style_commands.append(('FONTNAME', (col_idx + 2, row_idx), (col_idx + 2, row_idx), FONT_NAME_BOLD))
        
        col_idx += 3
    
    # Span final columns (Grand Total, Average, Position/Grade)
    for i in range(3):
        style_commands.append(('SPAN', (col_idx + i, 0), (col_idx + i, 1)))
    
    # Grand Total column styling
    style_commands.append(('BACKGROUND', (col_idx, 2), (col_idx, -1), colors.HexColor('#fff3cd')))
    style_commands.append(('FONTNAME', (col_idx, 2), (col_idx, -1), FONT_NAME_BOLD))
    style_commands.append(('FONTSIZE', (col_idx, 2), (col_idx, -1), sizing['score_font']))
    
    # Average column styling
    style_commands.append(('BACKGROUND', (col_idx + 1, 2), (col_idx + 1, -1), colors.HexColor('#d4edda')))
    style_commands.append(('FONTNAME', (col_idx + 1, 2), (col_idx + 1, -1), FONT_NAME_BOLD))
    
    # Position/Grade column styling
    style_commands.append(('BACKGROUND', (col_idx + 2, 2), (col_idx + 2, -1), colors.HexColor('#cce5ff')))
    style_commands.append(('ALIGN', (col_idx + 2, 2), (col_idx + 2, -1), 'LEFT'))
    
    # Alternating row colors
    for row_idx in range(2, num_rows):
        if row_idx % 2 == 0:  # Even rows (0-indexed, so this is odd in 1-indexed)
            style_commands.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor('#fafafa')))
        else:
            style_commands.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor('#ecf0f2')))
    
    table.setStyle(TableStyle(style_commands))
    
    return table


def create_footer():
    """Create footer section"""
    elements = []
    
    footer_style = ParagraphStyle(
        'Footer',
        fontSize=9,
        fontName=FONT_NAME,
        textColor=colors.black,
        leading=14
    )
    
    footer_data = [[
        Paragraph("<b>Prepared by:</b> ___________________________", footer_style),
        Paragraph("<b>Date:</b> ___________________________", footer_style),
        Paragraph("<b>Signature:</b> ___________________________", footer_style)
    ]]
    
    footer_table = Table(footer_data)
    footer_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEABOVE', (0, 0), (-1, 0), 1, colors.HexColor('#cccccc')),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
    ]))
    
    elements.append(Spacer(1, 20))
    elements.append(footer_table)
    
    return elements


def prepare_student_data_empty(students, is_sss2_or_sss3):
    """Prepare empty student data for blank template"""
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
    """Prepare student data with scores from broadsheet data"""
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
    """Generate blank broadsheet template PDF using ReportLab"""
    students_data = prepare_student_data_empty(students, is_sss2_or_sss3)
    subject_names = [subject[1] for subject in subjects]
    
    pdf_buffer = io.BytesIO()
    page_size = get_page_size(len(subjects), len(students))
    sizing = get_dynamic_sizing(len(subjects), len(students))
    col_widths = calculate_column_widths(len(subjects), page_size[0])
    
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=page_size,
        topMargin=10*mm,
        bottomMargin=10*mm,
        leftMargin=10*mm,
        rightMargin=10*mm
    )
    
    elements = []
    
    # Add header
    elements.extend(create_header(class_name, term, session, sizing))
    
    # Add summary section
    elements.extend(create_summary_section(class_name, term, session, len(students), len(subjects)))
    
    # Add broadsheet table
    table = create_broadsheet_table(students_data, subject_names, is_sss2_or_sss3, sizing, col_widths)
    elements.append(table)
    
    # Add footer
    elements.extend(create_footer())
    
    # Build PDF with watermark
    doc.build(elements, canvasmaker=WatermarkCanvas)
    pdf_buffer.seek(0)
    
    return pdf_buffer


def generate_broadsheet_with_scores_pdf(class_name, term, session, broadsheet_data, 
                                        subjects, class_average, is_sss2_or_sss3):
    """Generate broadsheet with scores PDF using ReportLab"""
    subject_names = [subject[1] for subject in subjects]
    students_data = prepare_student_data_with_scores(broadsheet_data, subject_names, is_sss2_or_sss3)
    
    pdf_buffer = io.BytesIO()
    page_size = get_page_size(len(subjects), len(students_data))
    sizing = get_dynamic_sizing(len(subjects), len(students_data))
    col_widths = calculate_column_widths(len(subjects), page_size[0])
    
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=page_size,
        topMargin=10*mm,
        bottomMargin=10*mm,
        leftMargin=10*mm,
        rightMargin=10*mm
    )
    
    elements = []
    
    # Add header
    elements.extend(create_header(class_name, term, session, sizing))
    
    # Add summary section
    elements.extend(create_summary_section(
        class_name, term, session, 
        len(students_data), len(subject_names), 
        class_average
    ))
    
    # Add broadsheet table
    table = create_broadsheet_table(students_data, subject_names, is_sss2_or_sss3, sizing, col_widths)
    elements.append(table)
    
    # Add footer
    elements.extend(create_footer())
    
    # Build PDF with watermark
    doc.build(elements, canvasmaker=WatermarkCanvas)
    pdf_buffer.seek(0)
    
    # Save to folder
    file_path = None
    try:
        os.makedirs("data/broadsheet", exist_ok=True)
        safe_class = class_name.replace(' ', '_')
        safe_term = term.replace(' ', '_')
        safe_session = session.replace('/', '_')
        file_path = os.path.join("data/broadsheet", f"{safe_class}_{safe_term}_{safe_session}_Broadsheet.pdf")
        
        with open(file_path, 'wb') as f:
            f.write(pdf_buffer.getvalue())
        
        pdf_buffer.seek(0)
    except Exception as e:
        print(f"Error saving broadsheet to folder: {e}")
        file_path = None
    
    return pdf_buffer, file_path


def build_class_broadsheet_data(class_name, term, session, user_id, role, sort_by="Position"):
    """Build broadsheet data for a single class"""
    is_sss2_or_sss3 = bool(re.match(r"SSS [23].*$", class_name))
    
    students = get_students_by_class(class_name, term, session, user_id, role)
    subjects = get_subjects_by_class(class_name, term, session, user_id, role)
    
    if not students or not subjects:
        return None
    
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
        
        numeric_totals = [int(v) for v in total_scores.values() if v != "-"]
        grand_total = str(sum(numeric_totals)) if numeric_totals else "-"
        row["Grand Total"] = grand_total
        
        if grand_total != "-" and numeric_totals:
            avg = round(int(grand_total) / len(numeric_totals), 1)
            row["Average"] = str(avg)
        else:
            row["Average"] = "-"
        
        position_data = next((gt for gt in grand_totals if gt['student_name'] == student_name), None)
        
        if is_sss2_or_sss3:
            grade_distribution = get_grade_distribution(student_name, class_name, term, session, user_id, role)
            row["Grade"] = grade_distribution if grade_distribution else "-"
            row["_position"] = position_data['position'] if position_data else 999
        else:
            row["Position"] = format_ordinal(position_data['position']) if position_data else "-"
            row["_position"] = position_data['position'] if position_data else 999
        
        broadsheet_data.append(row)
    
    if sort_by == "Name (A-Z)":
        broadsheet_data.sort(key=lambda x: x["Student"].lower())
    elif sort_by == "Name (Z-A)":
        broadsheet_data.sort(key=lambda x: x["Student"].lower(), reverse=True)
    else:
        broadsheet_data.sort(key=lambda x: x.get("_position", 999))
    
    for row in broadsheet_data:
        row.pop("_position", None)
    
    numeric_averages = [float(row["Average"]) for row in broadsheet_data if row["Average"] != "-"]
    class_average = round(sum(numeric_averages) / len(numeric_averages), 2) if numeric_averages else 0
    
    return broadsheet_data, subjects, class_average, is_sss2_or_sss3


def generate_all_classes_broadsheet_pdf(classes, user_id, role, sort_by="Position"):
    """Generate broadsheet PDF for all classes in a single document"""
    merger = PdfMerger()
    
    for class_data in classes:
        class_name = class_data['class_name']
        term = class_data['term']
        session = class_data['session']
        
        result = build_class_broadsheet_data(class_name, term, session, user_id, role, sort_by)
        
        if result is None:
            continue
        
        broadsheet_data, subjects, class_average, is_sss2_or_sss3 = result
        
        class_pdf, _ = generate_broadsheet_with_scores_pdf(
            class_name, term, session, broadsheet_data, subjects, 
            class_average, is_sss2_or_sss3
        )
        
        merger.append(class_pdf)
    
    output_buffer = io.BytesIO()
    merger.write(output_buffer)
    merger.close()
    output_buffer.seek(0)
    
    return output_buffer