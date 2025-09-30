# app_sections/generate_reports.py

import streamlit as st
import os
import zipfile
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS
from utils import assign_grade, create_metric_5col_report, format_ordinal, render_page_header
from database import (
    get_all_classes, get_students_by_class, get_student_scores, 
    get_class_average, get_student_grand_totals, get_comment, get_subjects_by_class
)

def generate_report_card(student_name, class_name, term, session):
    """Generate PDF report card for a student"""
    user_id = st.session_state.user_id
    role = st.session_state.role

    # Fetch student data with role-based restrictions
    students = get_students_by_class(class_name, term, session, user_id, role)
    student_data = next((s for s in students if s[1] == student_name), None)
    if not student_data:
        return None
    gender = student_data[2]  # Gender from students table
    class_size = len(students)  # Number of students in class

    # Fetch student scores with role-based restrictions
    student_scores = get_student_scores(student_name, class_name, term, session, user_id, role)
    
    # Get all subjects for the class
    all_subjects = get_subjects_by_class(class_name, term, session, user_id, role)
    if not all_subjects:
        return None

    # Calculate student average and totals (only from actual scores)
    if student_scores:
        total_score = sum(score[5] for score in student_scores)  # total_score column
        total_test = sum(int(score[3]) for score in student_scores)  # test_score column as int
        total_exam = sum(int(score[4]) for score in student_scores)  # exam_score column as int
        grand_total = int(total_test + total_exam)  # Should match sum of total_score
        avg = total_score / len(student_scores) if student_scores else 0
        grade = assign_grade(avg)
    else:
        total_score = total_test = total_exam = grand_total = 0
        avg = 0
        grade = "-"

    # Calculate class average - use the same method as broadsheet for consistency
    class_average = get_class_average(class_name, term, session, user_id, role)

    # Get position based on grand total comparison
    grand_totals = get_student_grand_totals(class_name, term, session, user_id, role)
    position_data = next((gt for gt in grand_totals if gt['student_name'] == student_name), None)
    position = format_ordinal(position_data['position']) if position_data else "-"

    # Fetch dynamic comments
    comment = get_comment(student_name, class_name, term, session)
    class_teacher_comment = comment['class_teacher_comment'] if comment and comment['class_teacher_comment'] else "No comment provided."
    head_teacher_comment = comment['head_teacher_comment'] if comment and comment['head_teacher_comment'] else "No comment provided."

    # Create score dictionary for quick lookup
    score_dict = {score[2]: score for score in student_scores}

    # Prepare data for template with all subjects - convert scores to integers
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
                'grade': score[6],
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

    # Load and render template
    try:
        env = Environment(loader=FileSystemLoader("templates"))
        template = env.get_template("report_template.html")
        html_out = template.render(
            name=student_name,
            class_name=class_name,
            term=term,
            session=session,
            gender=gender,
            class_size=class_size,
            class_average=class_average,
            average=round(avg, 2),
            grade=grade,
            position=position,
            subjects=subjects_data,
            total_test=total_test,
            total_exam=total_exam,
            grand_total=grand_total,
            class_teacher_comment=class_teacher_comment,
            head_teacher_comment=head_teacher_comment,
            next_term_date="To be announced"  # Static placeholder
        )

        # Generate PDF
        os.makedirs("data/reports", exist_ok=True)
        safe_name = "".join(c if c.isalnum() or c in (' ', '_') else "_" for c in student_name)
        output_path = os.path.join("data/reports", f"{safe_name.replace(' ', '_')}_{term.replace(' ', '_')}_{session.replace('/', '_')}_report.pdf")
        
        HTML(string=html_out, base_url=os.getcwd()).write_pdf(
            output_path,
            stylesheets=[CSS('templates/report_card_styles.css')]
        )
        return output_path
        
    except Exception as e:
        st.error(f"Error generating PDF: {e}")
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
                    # Add file to zip with just the filename (not full path)
                    zipf.write(pdf_path, os.path.basename(pdf_path))
        
        return zip_path
    except Exception as e:
        st.error(f"Error creating zip file: {e}")
        return None

def report_card_section():
    """Display report card generation section"""
    if not st.session_state.get("authenticated", False):
        st.error("⚠️ Please log in first.")
        st.switch_page("main.py")
        return

    if st.session_state.role not in ["superadmin", "admin", "class_teacher"]:
        st.error("⚠️ Access denied. Admins and Class Teachers only.")
        return

    user_id = st.session_state.user_id
    role = st.session_state.role

    st.set_page_config(page_title="Generate Report Card")
    
    # Subheader
    render_page_header("Generate Report Card")

    classes = get_all_classes(user_id, role)
    if not classes:
        st.warning("⚠️ No classes found.")
        return

    class_options = [f"{cls['class_name']} - {cls['term']} - {cls['session']}" for cls in classes]
    if role == "class_teacher":
        assignment = st.session_state.get("assignment")
        if not assignment:
            st.error("⚠️ Please select a class assignment first.")
            return
        allowed_class = f"{assignment['class_name']} - {assignment['term']} - {assignment['session']}"
        if allowed_class not in class_options:
            st.error("⚠️ Assigned class not found.")
            return
        class_options = [allowed_class]
        selected_class_display = st.selectbox("Select Class", class_options, disabled=True)
    else:
        selected_class_display = st.selectbox("Select Class", class_options)

    selected_index = class_options.index(selected_class_display)
    selected_class_data = classes[selected_index]
    class_name = selected_class_data['class_name']
    term = selected_class_data['term']
    session = selected_class_data['session']

    students = get_students_by_class(class_name, term, session, user_id, role)
    if not students:
        st.warning(f"⚠️ No students found for {class_name} - {term} - {session}.")
        return

    st.markdown(
        """
        <div style='width: auto; margin: auto; text-align: center; background-color: #c6b7b1;'>
            <h3 style='color:#000; font-size:20px; margin-top:30px;'>
                Report Card Summary
            </h3>
        </div>
        """,
        unsafe_allow_html=True
    )

    student_names = [s[1] for s in students]
    selected_student = st.selectbox("Select Student", student_names)

    # Calculate summary metrics for selected student
    student_data = next((s for s in students if s[1] == selected_student), None)
    gender = student_data[2] if student_data else "-"
    no_in_class = len(students)
    student_scores = get_student_scores(selected_student, class_name, term, session, user_id, role)
    total_score = sum(score[5] for score in student_scores) if student_scores else 0
    pupil_average = round(total_score / len(student_scores), 2) if student_scores else 0
    class_average = get_class_average(class_name, term, session, user_id, role)
    grand_totals = get_student_grand_totals(class_name, term, session, user_id, role)
    position_data = next((gt for gt in grand_totals if gt['student_name'] == selected_student), None)
    position = format_ordinal(position_data['position']) if position_data else "-"

    # Create summary metric
    create_metric_5col_report(gender, no_in_class, class_average, pupil_average, position)

    # Individual Report Card
    if st.button("📄 Generate Individual Report Card"):
        pdf_path = generate_report_card(selected_student, class_name, term, session)
        if pdf_path and os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                st.download_button(
                    label=f"📥 Download {selected_student}'s Report Card",
                    data=f,
                    file_name=os.path.basename(pdf_path),
                    mime="application/pdf"
                )
            st.success(f"✅ Report card generated for {selected_student}")
        else:
            st.error("❌ Failed to generate report card. Make sure the student has scores entered.")

    st.markdown("---")

    # Batch Report Cards
    if st.button("🗂️ Generate All Report Cards for Class"):
        st.info(f"Generating report cards for {class_name} - {term} - {session}...")
        
        success_count = 0
        failed_students = []
        pdf_paths = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, student in enumerate(students):
            student_name = student[1]
            status_text.text(f"Generating report for {student_name}...")
            
            pdf_path = generate_report_card(student_name, class_name, term, session)
            if pdf_path and os.path.exists(pdf_path):
                success_count += 1
                pdf_paths.append(pdf_path)
            else:
                failed_students.append(student_name)
                
            progress_bar.progress((i + 1) / len(students))

        status_text.text("Creating zip file...")
        
        if pdf_paths:
            zip_path = create_zip_file(pdf_paths, class_name, term, session)
            
            if zip_path and os.path.exists(zip_path):
                status_text.text("Complete!")
                st.success(f"✅ Generated {success_count}/{len(students)} report cards successfully.")
                
                with open(zip_path, "rb") as f:
                    st.download_button(
                        label=f"📥 Download All Report Cards (ZIP)",
                        data=f,
                        file_name=os.path.basename(zip_path),
                        mime="application/zip"
                    )
            else:
                status_text.text("Complete!")
                st.error("❌ Failed to create zip file.")
        else:
            status_text.text("Complete!")
            st.error("❌ No report cards were generated successfully.")
        
        if failed_students:
            st.warning(f"⚠️ Failed to generate reports for: {', '.join(failed_students)}")
            st.info("Make sure these students have scores entered for at least one subject.")