import streamlit as st
import os
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS
from utils import assign_grade, create_metric_5col_report
from database import (
    get_all_classes, get_students_by_class, get_student_scores, get_class_average, get_student_grand_totals
)

def generate_report_card(student_name, class_name, term, session):
    """Generate PDF report card for a student"""
    # Fetch student data
    students = get_students_by_class(class_name, term, session)
    student_data = next((s for s in students if s[1] == student_name), None)
    if not student_data:
        return None
    gender = student_data[2]  # Gender from students table
    class_size = len(students)  # Number of students in class

    # Fetch student scores
    student_scores = get_student_scores(student_name, class_name, term, session)
    if not student_scores:
        return None

    # Calculate student average and totals
    total_score = sum(score[5] for score in student_scores)  # total_score column
    total_test = sum(score[3] for score in student_scores)  # test_score column
    total_exam = sum(score[4] for score in student_scores)  # exam_score column
    grand_total = total_test + total_exam  # Should match sum of total_score
    avg = total_score / len(student_scores) if student_scores else 0
    grade = assign_grade(avg)

    # Calculate class average
    class_average = get_class_average(class_name, term, session)

    # Get position based on grand total comparison
    grand_totals = get_student_grand_totals(class_name, term, session)
    position_data = next((gt for gt in grand_totals if gt['student_name'] == student_name), None)
    position = format_ordinal(position_data['position']) if position_data else "-"

    # Prepare data for template
    subjects_data = []
    for score in student_scores:
        subjects_data.append({
            'subject': score[2],
            'test': score[3],
            'exam': score[4],
            'total': score[5],
            'grade': score[6],
            'position': format_ordinal(position_data['position']) if position_data else "-"
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
            grand_total=grand_total
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

def report_card_section():
    # Check authentication
    if not st.session_state.get("authenticated", False):
        st.error("⚠️ Please log in first.")
        st.switch_page("main.py")
        return

    st.set_page_config(page_title="Generate Report Card")
    
    st.markdown(
        """
        <div style='width: auto; margin: auto; text-align: center; background-color: #c6b7b1;'>
            <h3 style='color:#000; font-size:20px; margin-top:30px;'>
                Generate Report Card
            </h3>
        </div>
        """,
        unsafe_allow_html=True
    )

    classes = get_all_classes()
    if not classes:
        st.warning("⚠️ No classes found.")
        return

    # Create class display options with all three components
    class_options = [f"{cls['class_name']} - {cls['term']} - {cls['session']}" for cls in classes]
    selected_class_display = st.selectbox("Select Class", class_options)
    
    # Find the selected class data
    selected_index = class_options.index(selected_class_display)
    selected_class_data = classes[selected_index]
    
    class_name = selected_class_data['class_name']
    term = selected_class_data['term']
    session = selected_class_data['session']

    students = get_students_by_class(class_name, term, session)
    
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
    gender = "Male" if gender == "M" else "Female" if gender == "F" else "-"

    no_in_class = len(students)

    student_scores = get_student_scores(selected_student, class_name, term, session)
    total_score = sum(score[5] for score in student_scores) if student_scores else 0
    pupil_average = round(total_score / len(student_scores), 2) if student_scores else 0
    class_average = get_class_average(class_name, term, session)

    grand_totals = get_student_grand_totals(class_name, term, session)
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
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, student in enumerate(students):
            student_name = student[1]
            status_text.text(f"Generating report for {student_name}...")
            
            pdf_path = generate_report_card(student_name, class_name, term, session)
            if pdf_path and os.path.exists(pdf_path):
                success_count += 1
            else:
                failed_students.append(student_name)
                
            progress_bar.progress((i + 1) / len(students))

        status_text.text("Complete!")
        
        if success_count > 0:
            st.success(f"✅ Generated {success_count}/{len(students)} report cards successfully.")
        
        if failed_students:
            st.warning(f"⚠️ Failed to generate reports for: {', '.join(failed_students)}")
            st.info("Make sure these students have scores entered for at least one subject.")

def format_ordinal(n):
    """Convert number to ordinal string (e.g., 1 -> '1st', 2 -> '2nd')"""
    if not isinstance(n, int):
        return str(n)
    if 10 <= n % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f"{n}{suffix}"