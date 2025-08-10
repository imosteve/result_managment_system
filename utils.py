import re
import json
import os
import streamlit as st


def load_css(file_path):
    """Load CSS from external file"""
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            css_content = f.read()
        return css_content
    else:
        st.error(f"CSS file not found: {file_path}")
        return ""

def inject_login_css(file_path):
    """Inject CSS for login page only"""
    css_content = load_css(file_path)
    if css_content:
        st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)

def create_metric_4col(class_name, term, session, subjects_or_students, type):
    col1, col2, col3, col4 = st.columns(4)

    # Custom CSS for metrics
    # st.markdown(inject_login_css("templates/metrics_styles.css"), unsafe_allow_html=True)
    inject_login_css("templates/metrics_styles.css")

    # Display metrics with custom style
    with col1:
        st.markdown(f"<div class='custom-metric'><div class='label'>Class</div><div class='value'>{class_name.title()}</div></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='custom-metric'><div class='label'>Term</div><div class='value'>{term}</div></div>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"<div class='custom-metric'><div class='label'>Session</div><div class='value'>{session}</div></div>", unsafe_allow_html=True)
    with col4:
        if type == "student":
            st.markdown(f"<div class='custom-metric'><div class='label'>Total Students</div><div class='value'>{len(subjects_or_students)}</div></div>", unsafe_allow_html=True)
        elif type == "subject":
            st.markdown(f"<div class='custom-metric'><div class='label'>Total Subjects</div><div class='value'>{len(subjects_or_students)}</div></div>", unsafe_allow_html=True)

def create_metric_5col_broadsheet(subjects, students, class_average, broadsheet_data, class_name, term, session, user_id, role):
    from database import get_subjects_by_class
    
    # Get all possible subjects for the class
    all_subjects = get_subjects_by_class(class_name, term, session, user_id, role)
    
    # Count subjects with scores (subjects that appear in broadsheet data)
    subjects_with_scores = set()
    for row in broadsheet_data:
        for subject in all_subjects:
            subject_name = subject[1]
            if subject_name in row and row[subject_name] != "-":
                subjects_with_scores.add(subject_name)
    
    subjects_added = len(subjects_with_scores)
    subjects_not_added = len(all_subjects) - subjects_added
    
    # Get list of subjects without scores
    subjects_without_scores = []
    for subject in all_subjects:
        subject_name = subject[1]
        if subject_name not in subjects_with_scores:
            subjects_without_scores.append(subject_name)

    col1, col2, col3, col4, col5 = st.columns(5)

    # Custom CSS for metrics
    inject_login_css("templates/metrics_styles.css")

    # Display metrics with custom style
    with col1:
        st.markdown(f"<div class='custom-metric'><div class='label'>Total Subjects</div><div class='value'>{len(all_subjects)}</div></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='custom-metric'><div class='label'>Subjects Added</div><div class='value'>{subjects_added}</div></div>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"<div class='custom-metric'><div class='label'>Subjects Not Added</div><div class='value'>{subjects_not_added}</div></div>", unsafe_allow_html=True)
    with col4:
        st.markdown(f"<div class='custom-metric'><div class='label'>Total Students</div><div class='value'>{len(students)}</div></div>", unsafe_allow_html=True)
    with col5:
        st.markdown(f"<div class='custom-metric'><div class='label'>Class Average</div><div class='value'>{class_average}</div></div>", unsafe_allow_html=True)
    
    # Display subjects without scores if any
    if subjects_without_scores:
        # st.markdown("---")
        st.markdown("**📋 Subjects Without Scores:**")
        subjects_text = ", ".join(subjects_without_scores)
        st.markdown(f"<div style='background-color: #fff3cd; padding: 10px; border-radius: 5px; border-left: 4px solid #ffc107;'>{subjects_text}</div>", unsafe_allow_html=True)
        st.markdown("---")

def create_metric_5col_report(gender, no_in_class, class_average, pupil_average, position):

    # Create summary metric
    col1, col2, col3, col4, col5 = st.columns(5)

    # Custom CSS for metrics
    inject_login_css("templates/metrics_styles.css")

    # Display metrics with custom style
    with col1:
        st.markdown(f"<div class='custom-metric'><div class='label'>Gender</div><div class='value'>{gender}</div></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='custom-metric'><div class='label'>No. in Class</div><div class='value'>{no_in_class}</div></div>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"<div class='custom-metric'><div class='label'>Class Average</div><div class='value'>{class_average}</div></div>", unsafe_allow_html=True)
    with col4:
        st.markdown(f"<div class='custom-metric'><div class='label'>Pupil Average</div><div class='value'>{pupil_average}</div></div>", unsafe_allow_html=True)
    with col5:
        st.markdown(f"<div class='custom-metric'><div class='label'>Position</div><div class='value'>{position}</div></div>", unsafe_allow_html=True)

def clean_input(value, input_type):
    """Clean and validate input data"""
    if not value or str(value).strip() == "":
        return ""
    
    value = str(value).strip()
    
    if input_type == "name":
        # Remove extra spaces and title case
        value = ' '.join(value.split())
        return value.title()
    
    elif input_type == "gender":
        value = value.upper()
        return value if value in ["M", "F"] else ""
    
    elif input_type == "email":
        # Basic email validation
        if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', value):
            return value.lower()
        return ""
    
    elif input_type == "subject":
        # Clean subject name
        return ' '.join(value.split()).title()
    
    elif input_type == "class":
        # Clean class name
        return value.upper().strip()
    
    return value

def assign_grade(score):
    """Assign letter grade based on numerical score"""
    if score >= 80:
        return "A"
    elif score >= 70:
        return "B"
    elif score >= 60:
        return "C"
    elif score >= 50:
        return "D"
    elif score >= 45:
        return "E"
    else:
        return "F"

def assign_remark(grade):
    """Assign letter grade based on numerical grade"""
    if grade == "A":
        return "Excellent"
    elif grade == "B":
        return "Very Good"
    elif grade == "C":
        return "Good"
    elif grade == "D":
        return "Pass"
    elif grade == "E":
        return "Weak Pass"
    elif grade == "F":
        return "Fail"
    else:
        return " "

def sanitize_filename(filename):
    """Sanitize filename for safe file operations"""
    # Remove or replace invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove extra spaces and replace with underscores
    filename = re.sub(r'\s+', '_', filename.strip())
    return filename

def format_ordinal(n):
    if not isinstance(n, int):
        return str(n)
    if 10 <= n % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f"{n}{suffix}"

def render_page_header(title, background_color="#c6b7b1", text_color="#000", font_size="24px"):
    """
    Renders a styled page header
    
    Args:
        title (str): The title text to display
        background_color (str): Background color (default: #c6b7b1)
        text_color (str): Text color (default: #000)
        font_size (str): Font size (default: 24px)
    """
    st.markdown(
        f"""
        <div style='width: auto; margin: auto; text-align: center; background-color: {background_color};'>
            <h2 style='color:{text_color}; font-size:{font_size}; margin-top:30px; margin-bottom:20px;'>
                {title}
            </h2>
        </div>
        """,
        unsafe_allow_html=True
    )

# # Custom styling
# render_page_header(
#     "Admin Dashboard", 
#     background_color="#2c3e50", 
#     text_color="#ffffff", 
#     font_size="28px"
# )

# In your existing code, replace the header with:
render_page_header("Manage Report Card Comments")