# app_sections/generate_reports.py

import streamlit as st
import re
from datetime import datetime
import os
import zipfile
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS
from PyPDF2 import PdfMerger
from utils import (
    assign_grade, create_metric_5col_report, format_ordinal, 
    render_page_header, inject_login_css, render_persistent_class_selector
)
from database import (
    get_all_classes, get_students_by_class, get_student_scores, 
    get_class_average, get_student_grand_totals, get_comment, get_subjects_by_class,
    get_psychomotor_rating, get_grade_distribution, get_next_term_begin_date, get_next_term_info
)
from auth.activity_tracker import ActivityTracker
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

def send_email(to_email, student_name, pdf_path, term, session):
    """Send email with PDF attachment using HTML template"""
    import re
    import socket
    from datetime import datetime
    from jinja2 import Environment, FileSystemLoader

    msg = MIMEMultipart('alternative')

    # If EMAIL_SENDER contains a display name like "Name <email>", extract raw email for authentication
    match = re.search(r'<([^>]+)>', EMAIL_SENDER)
    sender_email = match.group(1) if match else EMAIL_SENDER

    msg["From"] = EMAIL_SENDER
    msg["To"] = to_email
    msg["Subject"] = f"Report Card - {student_name} - {term} {session}"

    # Load HTML template
    try:
        env = Environment(loader=FileSystemLoader("templates"))
        template = env.get_template("email_template.html")
        html_body = template.render(
            school_name=APP_CONFIG["school_name"],
            student_name=student_name,
            term=term,
            session=session,
            year=datetime.now().year
        )
        
        school_name=APP_CONFIG["school_name"]
        # Plain text fallback
        text_body = f"""Dear Parent/Guardian,

We are pleased to share the academic report card for {student_name} for the recently concluded term.

Report Details:
- Student: {student_name}
- Term: {term}
- Academic Session: {session}

Please find the detailed report card attached to this email in PDF format.

We encourage you to review the report carefully and discuss your child's progress with them. Should you have any questions or concerns regarding the report, please do not hesitate to contact us.

Best regards,
School Administration
{school_name.title()}
---
This is an automated message. Please do not reply to this email."""

        # Attach both plain text and HTML versions
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))
        
    except Exception as e:
        # Fallback to simple plain text if template loading fails
        st.warning(f"Could not load email template, using plain text: {e}")
        body = f"""Dear Parent/Guardian,

Please find attached the report card for {student_name} for {term}, {session}.

Best regards,
School Administration"""
        msg.attach(MIMEText(body, "plain"))

    # Ensure attachment exists before attempting to open/send
    if not pdf_path or not os.path.exists(pdf_path):
        st.error(f"Attachment not found: {pdf_path}")
        return False

    try:
        with open(pdf_path, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition", f"attachment; filename={os.path.basename(pdf_path)}"
            )
            msg.attach(part)

        # Connect and send using SSL for port 465, otherwise use STARTTLS
        server = None
        try:
            if SMTP_PORT == 465:
                server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=30)
                server.login(sender_email, EMAIL_PASSWORD)
            else:
                server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30)
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(sender_email, EMAIL_PASSWORD)

            # sendmail expects sender and list of recipients
            server.sendmail(sender_email, [to_email], msg.as_string())
            server.quit()
            return True

        except (smtplib.SMTPException, socket.error) as smtp_err:
            # Attempt to close connection if open
            try:
                if server:
                    server.quit()
            except Exception:
                pass
            st.error(f"SMTP error sending email to {to_email}: {smtp_err}")
            return False

    except Exception as e:
        st.error(f"Error attaching/sending email to {to_email}: {e}")
        return False
        
def generate_tab():
    """Tab 1: Generate Report Cards"""
    user_id = st.session_state.user_id
    role = st.session_state.role

    classes = get_all_classes(user_id, role)
    if not classes:
        st.warning("⚠️ No classes found.")
        return

    selected_class_data = render_persistent_class_selector(
        classes, 
        widget_key="generate_reports_class"
    )

    if not selected_class_data:
        st.warning("⚠️ No class selected.")
        return
    
    # Track class selection
    class_identifier = f"{selected_class_data['class_name']}_{selected_class_data['term']}_{selected_class_data['session']}"
    ActivityTracker.watch_value("generate_reports_class", class_identifier)

    class_name = selected_class_data['class_name']
    term = selected_class_data['term']
    session = selected_class_data['session']

    import re
    is_senior_class = bool(re.match(r"SSS [123].*$", class_name))
    is_junior_class = bool(re.match(r"JSS [123].*$", class_name))
    is_secondary_class = is_senior_class or is_junior_class
    
    is_kg_class = bool(re.match(r"KINDERGARTEN [12345].*$", class_name))
    is_nursery_class = bool(re.match(r"NURSERY [12345].*$", class_name))
    is_pri_class = bool(re.match(r"PRIMARY [123456].*$", class_name))
    is_primary_class = is_kg_class or is_nursery_class or is_pri_class

    students = get_students_by_class(class_name, term, session, user_id, role)
    if not students:
        st.warning(f"⚠️ No students found for {class_name} - {term} - {session}.")
        return

    st.markdown(
        """
        <div style='width: auto; margin: auto; text-align: center; background-color: #c6b7b1;'>
            <h3 style='color:#000; font-size:20px; margin-bottom: 15px;'>
                Report Card Summary
            </h3>
        </div>
        """,
        unsafe_allow_html=True
    )

    student_names = [s[1] for s in students]
    selected_student = st.selectbox("Select Student", student_names)
    
    # Track student selection
    ActivityTracker.watch_value("generate_reports_student", selected_student)

    # Calculate summary metrics for selected student
    student_data = next((s for s in students if s[1] == selected_student), None)
    gender = student_data[2] if student_data else "-"
    no_in_class = len(students)
    student_scores = get_student_scores(selected_student, class_name, term, session, user_id, role)
    
    # Filter out None values when calculating totals
    valid_scores = [score[5] for score in student_scores if score[5] is not None] if student_scores else []
    total_score = sum(valid_scores) if valid_scores else 0
    student_average = round(total_score / len(valid_scores), 2) if valid_scores else 0
    
    class_average = get_class_average(class_name, term, session, user_id, role)
    grand_totals = get_student_grand_totals(class_name, term, session, user_id, role)
    position_data = next((gt for gt in grand_totals if gt['student_name'] == selected_student), None)
    
    is_sss2_or_sss3 = bool(re.match(r"SSS [23].*$", class_name))
    if is_sss2_or_sss3:
        # For SSS2 and SSS3, get grade distribution instead of position
        grade_distribution = get_grade_distribution(selected_student, class_name, term, session, user_id, role)
        position = ""  # Not used for SSS2/SSS3
    else:
        grade_distribution = ""
        position = format_ordinal(position_data['position']) if position_data else "-"

    # Create summary metric
    create_metric_5col_report(gender, 
                              no_in_class, 
                              class_average, 
                              student_average, 
                              position,
                              grade_distribution,
                              is_secondary_class, 
                              is_primary_class,
                              is_sss2_or_sss3
                              )

    # Individual Report Card
    if st.button("Generate Report Card"):
        # Track generate button
        ActivityTracker.update()
        
        pdf_path = generate_report_card(selected_student, class_name, term, session, is_secondary_class, is_primary_class)
        with st.spinner(f"Generating and sending report for {selected_student}..."):
            if pdf_path and os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        label=f"📥 Download {selected_student}'s Report Card",
                        data=f,
                        file_name=os.path.basename(pdf_path),
                        mime="application/pdf",
                        on_click=ActivityTracker.update  # Track download
                    )
                st.success(f"✅ Report card generated for {selected_student}")
            else:
                st.error("❌ Failed to generate report card. Make sure subjects has been added to class.")

    st.markdown("---")

    # Batch Report Cards
    if st.button("Generate All Report Cards"):
        # Track batch generate button
        ActivityTracker.update()
        
        st.info(f"Generating report cards for {class_name} - {term} - {session}...")
        
        success_count = 0
        failed_students = []
        pdf_paths = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, student in enumerate(students):
            student_name = student[1]
            status_text.text(f"Generating report for {student_name}...")
            
            pdf_path = generate_report_card(student_name, class_name, term, session, is_secondary_class, is_primary_class)
            if pdf_path and os.path.exists(pdf_path):
                success_count += 1
                pdf_paths.append(pdf_path)
            else:
                failed_students.append(student_name)
                
            progress_bar.progress((i + 1) / len(students))

        status_text.text("Merging all reports into a single PDF...")
        
        if pdf_paths:
            merged_pdf_path = merge_pdfs_into_single_file(pdf_paths, class_name, term, session)
            
            if merged_pdf_path and os.path.exists(merged_pdf_path):
                status_text.text("Complete!")
                st.success(f"✅ Generated {success_count}/{len(students)} report cards successfully and merged into single PDF.")
                
                with open(merged_pdf_path, "rb") as f:
                    st.download_button(
                        label=f"📥 Download All Report Cards (Single PDF)",
                        data=f,
                        file_name=os.path.basename(merged_pdf_path),
                        mime="application/pdf",
                        on_click=ActivityTracker.update  # Track download
                    )
            else:
                status_text.text("Complete!")
                st.error("❌ Failed to merge PDFs into single file.")
        else:
            status_text.text("Complete!")
            st.error("❌ No report cards were generated successfully.")
        
        if failed_students:
            st.warning(f"⚠️ Failed to generate reports for: {', '.join(failed_students)}")
            st.info("Make sure these students have scores entered for at least one subject.")

def email_tab():
    """Tab 2: Email All Report Cards"""
    user_id = st.session_state.user_id
    role = st.session_state.role

    classes = get_all_classes(user_id, role)
    if not classes:
        st.warning("⚠️ No classes found.")
        return

    selected_class_data = render_persistent_class_selector(
        classes, 
        widget_key="email_reports_class")

    if not selected_class_data:
        st.warning("⚠️ No class selected.")
        return
    
    # Track class selection
    class_identifier = f"{selected_class_data['class_name']}_{selected_class_data['term']}_{selected_class_data['session']}"
    ActivityTracker.watch_value("email_reports_class", class_identifier)

    class_name = selected_class_data['class_name']
    term = selected_class_data['term']
    session = selected_class_data['session']

    import re
    is_senior_class = bool(re.match(r"SSS [123].*$", class_name))
    is_junior_class = bool(re.match(r"JSS [123].*$", class_name))
    is_secondary_class = is_senior_class or is_junior_class
    
    is_kg_class = bool(re.match(r"KINDERGARTEN [12345].*$", class_name))
    is_nursery_class = bool(re.match(r"NURSERY [12345].*$", class_name))
    is_pri_class = bool(re.match(r"PRIMARY [123456].*$", class_name))
    is_primary_class = is_kg_class or is_nursery_class or is_pri_class

    students = get_students_by_class(class_name, term, session, user_id, role)
    if not students:
        st.warning("⚠️ No students found for this class.")
        return

    st.markdown(
        """
        <div style='width: auto; margin: auto; text-align: center; background-color: #c6b7b1;'>
            <h3 style='color:#000; font-size:20px; margin-bottom: 15px;'>
                Email Report Cards
            </h3>
        </div>
        """,
        unsafe_allow_html=True
    )

    students_eligible = [s for s in students if s[3] and s[4] == 'YES']
    students_without_email = [s for s in students if not s[3]]
    students_unpaid_fees = [s for s in students if s[3] and s[4] != 'YES']

    if students_without_email:
        st.warning(f"⚠️ {len(students_without_email)} student(s) do not have email addresses: {', '.join([s[1] for s in students_without_email])}")

    if students_unpaid_fees:
        st.info(f"ℹ️ {len(students_unpaid_fees)} student(s) have email but haven't paid school fees (cannot receive reports via email): {', '.join([s[1] for s in students_unpaid_fees])}")

    if not students_eligible:
        st.warning(f"⚠️ No students are eligible to receive reports via email. Students must have email and paid fees.")
        return

    st.success(f"📧 {len(students_eligible)} student(s) are eligible to receive report cards via email: {', '.join([s[1] for s in students_eligible])}")

    # Individual Email
    st.markdown("### Email Report Card")
    student_names_eligible = [s[1] for s in students_eligible]
    selected_student = st.selectbox("Select Student", student_names_eligible, key="email_student")
    
    # Track student selection
    ActivityTracker.watch_value("email_reports_student", selected_student)
    
    student_data = next((s for s in students_eligible if s[1] == selected_student), None)
    if student_data:
        st.write(f"📧 Email: {student_data[3]}")

    if st.button("Send"):
        # Track send button
        ActivityTracker.update()
        
        if not student_data or not student_data[3]:
            st.error("❌ Student email not found.")
            return
            
        with st.spinner(f"Generating and sending report for {selected_student}..."):
            # Generate PDF
            pdf_path = generate_report_card(selected_student, class_name, term, session, is_secondary_class, is_primary_class)
            if pdf_path and os.path.exists(pdf_path):
                # Send email
                if send_email(student_data[3], selected_student, pdf_path, term, session):
                    st.success(f"✅ Report card sent to {student_data[3]}")
                else:
                    st.error("❌ Failed to send email. Please check email configuration.")
            else:
                st.error("❌ Failed to generate report card. Make sure the student has scores entered.")

    st.markdown("---")

    # Batch Email
    st.markdown("### Send All Report Cards via Email")
    st.warning("⚠️ This will generate and send report cards to all students with email addresses. This may take some time.")
    
    if st.button("Send All"):
        # Track send all button
        ActivityTracker.update()
        
        st.info(f"Generating and sending report cards for {len(students_eligible)} students...")
        
        success_count = 0
        failed_students = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, student in enumerate(students_eligible):
            student_name = student[1]
            student_email = student[3]
            
            status_text.text(f"Processing {student_name} ({i+1}/{len(students_eligible)})...")
            
            # Generate PDF
            pdf_path = generate_report_card(student_name, class_name, term, session, is_secondary_class, is_primary_class)
            if pdf_path and os.path.exists(pdf_path):
                # Send email
                if send_email(student_email, student_name, pdf_path, term, session):
                    success_count += 1
                    status_text.text(f"✅ Sent to {student_name}")
                else:
                    failed_students.append(f"{student_name} (email failed)")
            else:
                failed_students.append(f"{student_name} (PDF generation failed)")
                
            progress_bar.progress((i + 1) / len(students_eligible))

        status_text.text("Complete!")
        st.success(f"✅ Successfully sent {success_count}/{len(students_eligible)} report cards.")
        
        if failed_students:
            st.error(f"❌ Failed to send reports for: {', '.join(failed_students)}")

def report_card_section():
    """Display report card generation section with tabs"""
    if not st.session_state.get("authenticated", False):
        st.error("⚠️ Please log in first.")
        st.switch_page("main.py")
        return

    if st.session_state.role not in ["superadmin", "admin", "class_teacher"]:
        st.error("⚠️ Access denied. Admins and Class Teachers only.")
        return

    # Initialize activity tracker
    ActivityTracker.init()

    st.set_page_config(page_title="Generate Report Card")
    
    # Page header
    render_page_header("Generate Report Card")

    inject_login_css("templates/tabs_styles.css")
    # Create tabs
    tab1, tab2 = st.tabs(["Generate Reports", "Email Reports"])
    
    # Track active tab
    active_tab = st.session_state.get("generate_reports_active_tab", 0)
    ActivityTracker.watch_tab("generate_reports", active_tab)
    
    with tab1:
        st.session_state.generate_reports_active_tab = 0
        generate_tab()
    
    with tab2:
        st.session_state.generate_reports_active_tab = 1
        email_tab()
