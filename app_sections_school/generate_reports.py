# app_sections/generate_reports.py

import streamlit as st
import re
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from main_utils import (
    assign_grade, create_metric_5col_report, format_ordinal,
    render_page_header, inject_login_css, render_class_term_session_selector
)
from database_school import (
    get_active_session, get_active_term_name, get_classes_for_session,
    get_enrolled_students, get_scores_for_subject, get_subjects_by_class,
    get_student_average, get_student_grand_totals, get_grade_distribution,
    is_configured, get_user_assignments
)
from auth.activity_tracker import ActivityTracker
from config import APP_CONFIG

# Email Configuration
SMTP_SERVER = os.getenv('SMTP_SERVER', "smtp.gmail.com")
SMTP_PORT = int(os.getenv('SMTP_PORT', 465))
EMAIL_SENDER = os.getenv('EMAIL_SENDER', "SUIS Terminal Result <ideas.elites@gmail.com>")
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', "lkydcrsaritupygu")

from pdf_generators.report_card_pdf_reportlab import (
    generate_report_card, 
    merge_pdfs_into_single_file,
)

def send_email(to_email, student_name, pdf_buffer, term, session):
    """Send email with PDF attachment using HTML template"""
    import re
    import socket
    import tempfile
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
            school_name=st.session_state.get("school_name", "School Administration"),
            student_name=student_name,
            term=term,
            session=session,
            year=datetime.now().year
        )
        
        school_name=st.session_state.get("school_name", "School Administration")
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

    # Write buffer to a temp file only for the duration of the email send
    safe_name = "".join(c if c.isalnum() or c in (' ', '_') else "_" for c in student_name)
    attachment_filename = f"{safe_name.replace(' ', '_')}_{term.replace(' ', '_')}_{session.replace('/', '_')}_report.pdf"

    try:
        # Use delete=False so Windows doesn't lock the file while it's open
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        try:
            pdf_buffer.seek(0)
            tmp.write(pdf_buffer.read())
            tmp.close()  # Must close before re-opening on Windows

            with open(tmp.name, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition", f"attachment; filename={attachment_filename}"
                )
                msg.attach(part)
        finally:
            # Always clean up the temp file regardless of success or failure
            try:
                os.unlink(tmp.name)
            except Exception:
                pass

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

    _ctx = render_class_term_session_selector("generate_reports", allow_term_session_override=True)
    if _ctx is None:
        return
    class_name = _ctx["class_name"]
    term       = _ctx["term"]
    session    = _ctx["session"]
    ActivityTracker.watch_value("generate_reports_class", f"{class_name}_{session}_{term}")

    is_senior_class = bool(re.match(r"SSS [123].*$", class_name))
    is_junior_class = bool(re.match(r"JSS [123].*$", class_name))
    is_secondary_class = is_senior_class or is_junior_class
    
    is_kg_class = bool(re.match(r"KINDERGARTEN [12345].*$", class_name))
    is_nursery_class = bool(re.match(r"NURSERY [12345].*$", class_name))
    is_pri_class = bool(re.match(r"PRIMARY [123456].*$", class_name))
    is_primary_class = is_kg_class or is_nursery_class or is_pri_class

    students = get_enrolled_students(class_name, session)
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

    student_names = [s["student_name"] for s in students]
    selected_student = st.selectbox("Select Student", student_names)
    
    # Track student selection
    ActivityTracker.watch_value("generate_reports_student", selected_student)

    # Calculate summary metrics for selected student
    student_data = next((s for s in students if s["student_name"] == selected_student), None)
    gender = student_data.get("gender", "-") if student_data else "-"
    no_in_class = len(students)
    # New schema: use get_student_average directly
    student_average = get_student_average(selected_student, class_name, session, term) or 0
    grand_totals = get_student_grand_totals(class_name, session, term)
    position_data = next((gt for gt in grand_totals if gt['student_name'] == selected_student), None)
    # Class average: mean of each student's per-subject average across the class
    if grand_totals:
        num_subjects = get_subjects_by_class(class_name)
        num_subjects = len(num_subjects) if num_subjects else 1
        class_average = round(
            sum(gt['grand_total'] for gt in grand_totals) / len(grand_totals) / num_subjects, 1
        )
    else:
        class_average = 0
    
    is_sss2_or_sss3 = bool(re.match(r"SSS [23].*$", class_name))
    if is_sss2_or_sss3:
        # For SSS2 and SSS3, get grade distribution instead of position
        grade_distribution = get_grade_distribution(selected_student, class_name, session, term)
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
        
        with st.spinner(f"Generating report for {selected_student}..."):
            pdf_buffer = generate_report_card(selected_student, class_name, term, session, is_secondary_class, is_primary_class)
            if pdf_buffer:
                safe_name = "".join(c if c.isalnum() or c in (' ', '_') else "_" for c in selected_student)
                file_name = f"{safe_name.replace(' ', '_')}_{term.replace(' ', '_')}_{session.replace('/', '_')}_report.pdf"
                st.download_button(
                    label=f"📥 Download {selected_student}'s Report Card",
                    data=pdf_buffer,
                    file_name=file_name,
                    mime="application/pdf",
                    on_click=ActivityTracker.update
                )
                st.success(f"✅ Report card generated for {selected_student}")
            else:
                st.error("❌ Failed to generate report card. Make sure subjects has been added to class.")

    # Batch Report Cards
    if st.button("Generate All Report Cards"):
        # Track batch generate button
        ActivityTracker.update()
        
        st.info(f"Generating report cards for {class_name} - {term} - {session}...")
        
        success_count = 0
        failed_students = []
        pdf_buffers = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, student in enumerate(students):
            student_name = student["student_name"]
            status_text.text(f"Generating report for {student_name}...")
            
            pdf_buffer = generate_report_card(student_name, class_name, term, session, is_secondary_class, is_primary_class)
            if pdf_buffer:
                success_count += 1
                pdf_buffers.append(pdf_buffer)
            else:
                failed_students.append(student_name)
                
            progress_bar.progress((i + 1) / len(students))

        status_text.text("Merging all reports into a single PDF...")
        
        if pdf_buffers:
            merged_buffer = merge_pdfs_into_single_file(pdf_buffers, class_name, term, session)
            
            if merged_buffer:
                status_text.text("Complete!")
                st.success(f"✅ Generated {success_count}/{len(students)} report cards successfully and merged into single PDF.")
                merged_filename = f"{class_name.replace(' ', '_')}_{term.replace(' ', '_')}_{session.replace('/', '_')}_All_Reports.pdf"
                st.download_button(
                    label=f"📥 Download All Report Cards (Single PDF)",
                    data=merged_buffer,
                    file_name=merged_filename,
                    mime="application/pdf",
                    on_click=ActivityTracker.update
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

    _ctx = render_class_term_session_selector("email_reports", allow_term_session_override=True)
    if _ctx is None:
        return
    class_name = _ctx["class_name"]
    term       = _ctx["term"]
    session    = _ctx["session"]
    ActivityTracker.watch_value("email_reports_class", f"{class_name}_{session}_{term}")

    import re
    is_senior_class = bool(re.match(r"SSS [123].*$", class_name))
    is_junior_class = bool(re.match(r"JSS [123].*$", class_name))
    is_secondary_class = is_senior_class or is_junior_class
    
    is_kg_class = bool(re.match(r"KINDERGARTEN [12345].*$", class_name))
    is_nursery_class = bool(re.match(r"NURSERY [12345].*$", class_name))
    is_pri_class = bool(re.match(r"PRIMARY [123456].*$", class_name))
    is_primary_class = is_kg_class or is_nursery_class or is_pri_class

    students = get_enrolled_students(class_name, session)
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

    students_eligible = [s for s in students if s.get("email") and s.get("school_fees_paid") == "YES"]
    students_without_email = [s for s in students if not s.get("email")]
    students_unpaid_fees = [s for s in students if s.get("email") and s.get("school_fees_paid") != "YES"]

    if students_without_email:
        st.warning(f"⚠️ {len(students_without_email)} student(s) do not have email addresses: {', '.join([s["student_name"] for s in students_without_email])}")

    if students_unpaid_fees:
        st.info(f"ℹ️ {len(students_unpaid_fees)} student(s) have email but haven't paid school fees (cannot receive reports via email): {', '.join([s["student_name"] for s in students_unpaid_fees])}")

    if not students_eligible:
        st.warning(f"⚠️ No students are eligible to receive reports via email. Students must have email and paid fees.")
        return

    st.success(f"📧 {len(students_eligible)} student(s) are eligible to receive report cards via email: {', '.join([s["student_name"] for s in students_eligible])}")

    # Individual Email
    st.markdown("### Email Report Card")
    student_names_eligible = [s["student_name"] for s in students_eligible]
    selected_student = st.selectbox("Select Student", student_names_eligible, key="email_student")
    
    # Track student selection
    ActivityTracker.watch_value("email_reports_student", selected_student)
    
    student_data = next((s for s in students_eligible if s["student_name"] == selected_student), None)
    if student_data:
        st.write(f"📧 Email: {student_data.get('email', '')}")

    if st.button("Send"):
        # Track send button
        ActivityTracker.update()
        
        if not student_data or not student_data.get("email"):
            st.error("❌ Student email not found.")
            return
            
        with st.spinner(f"Generating and sending report for {selected_student}..."):
            # Generate PDF
            pdf_buffer = generate_report_card(selected_student, class_name, term, session, is_secondary_class, is_primary_class)
            if pdf_buffer:
                # Send email
                if send_email(student_data["email"], selected_student, pdf_buffer, term, session):
                    st.success(f"✅ Report card sent to {student_data['email']}")
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
            student_name = student["student_name"]
            student_email = student.get("email", "")
            
            status_text.text(f"Processing {student_name} ({i+1}/{len(students_eligible)})...")
            
            # Generate PDF
            pdf_buffer = generate_report_card(student_name, class_name, term, session, is_secondary_class, is_primary_class)
            if pdf_buffer:
                # Send email
                if send_email(student_email, student_name, pdf_buffer, term, session):
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
    
    # Tab-based interface for different operations
    inject_login_css("templates/tabs_styles.css")

    # Page header
    render_page_header("Generate Report Card")

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