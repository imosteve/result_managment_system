# utils.py

import re
import json
import os
import streamlit as st
from pathlib import Path


def get_project_root():
    """Get the absolute path to the project root directory"""
    # Get the directory where utils.py is located
    return Path(__file__).resolve().parent


def load_css(file_path):
    """Load CSS from external file with absolute path handling"""
    try:
        # Convert to absolute path
        project_root = get_project_root()
        absolute_path = project_root / file_path
        
        if absolute_path.exists():
            with open(absolute_path, 'r') as f:
                css_content = f.read()
            return css_content
        else:
            st.warning(f"CSS file not found: {file_path}")
            return ""
    except Exception as e:
        st.error(f"Error loading CSS file {file_path}: {str(e)}")
        return ""


def inject_login_css(file_path):
    """Inject CSS for login page only"""
    css_content = load_css(file_path)
    if css_content:
        st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)

def inject_metric_css():
    # Inject custom CSS for metric styling
    st.markdown("""
        <style>
            /* Make metric boxes look nice and uniform */
            [data-testid="stMetricValue"] {
                font-size: 30px !important;
                color: #1f77b4;
            }
            [data-testid="stMetricLabel"] {
                font-size: 16px !important;
                color: #555;
            }
            div[data-testid="stMetric"] {
                background: #f8f9fa;
                border: 2px solid #4CAF50;
                border-radius: 12px;
                padding: 12px;
                text-align: center;
                box-shadow: 0 2px 6px rgba(0,0,0,0.05);
            }
            /* Adjust layout spacing */
            div[data-testid="stHorizontalBlock"] > div {
                padding: 5px;
            }
        </style>
    """, unsafe_allow_html=True)

def create_metric_4col(class_name, term, session, subjects_or_students, type):
    col1, col2, col3, col4 = st.columns(4)

    # Custom CSS for metrics
    inject_login_css("templates/metrics_styles.css")

    # Display metrics with custom style
    with col1:
        st.markdown(f"<div class='custom-metric'><div class='label'>Class</div><div class='value'>{class_name.upper()}</div></div>", unsafe_allow_html=True)
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
    
    # Count subjects with scores (subjects that appear in broadsheet data with Total column)
    subjects_with_scores = set()
    for row in broadsheet_data:
        for subject in all_subjects:
            subject_name = subject[1]
            # Check the Total column for this subject
            total_key = f"{subject_name} (Total)"
            if total_key in row and row[total_key] != "-":
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
        st.markdown(f"<div class='custom-metric'><div class='label'>Class Average</div><div class='value'>{class_average:.1f}</div></div>", unsafe_allow_html=True)
    
    # Display subjects without scores if any
    if subjects_without_scores:
        st.markdown("**📋 Subjects Without Scores:**")
        subjects_text = ", ".join(subjects_without_scores)
        st.markdown(f"<div style='background-color: #fff3cd; padding: 10px; border-radius: 5px; border-left: 4px solid #ffc107;'>{subjects_text}</div>", unsafe_allow_html=True)
        st.markdown("---")


def create_metric_5col_report(gender, no_in_class, class_average, student_average, position, grade_distribution, is_secondary_class, is_primary_class, is_sss2_or_sss3):

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
        if is_secondary_class:
            st.markdown(f"<div class='custom-metric'><div class='label'>Student Average</div><div class='value'>{student_average}</div></div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='custom-metric'><div class='label'>Pupil Average</div><div class='value'>{student_average}</div></div>", unsafe_allow_html=True)
    with col5:
        if is_sss2_or_sss3:
            st.markdown(f"<div class='custom-metric'><div class='label'>Grade</div><div class='value'>{grade_distribution}</div></div>", unsafe_allow_html=True)
        else:
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
            <h2 style='color:{text_color}; font-size:{font_size}; margin-top:10px; margin-bottom:20px;'>
                {title}
            </h2>
        </div>
        """,
        unsafe_allow_html=True
    )


from typing import List, Dict, Any, Optional

def initialize_class_persistence():
    """Initialize the global class persistence storage in session state"""
    if 'class_selection_state' not in st.session_state:
        st.session_state.class_selection_state = {
            'class_name': None,
            'term': None,
            'session': None,
            'display_string': None
        }

def get_persistent_class_data():
    """Get the currently selected class data from session state"""
    initialize_class_persistence()
    return st.session_state.class_selection_state

def set_persistent_class_data(class_name: str, term: str, session: str):
    """Store the selected class data in session state"""
    initialize_class_persistence()
    st.session_state.class_selection_state = {
        'class_name': class_name,
        'term': term,
        'session': session,
        'display_string': f"{class_name} - {term} - {session}"
    }

def render_persistent_class_selector(classes: List[Dict[str, Any]], 
                                    widget_key: str = "global_class_selector") -> Optional[Dict[str, Any]]:
    """
    Render a class selector that persists selection across page navigation
    
    Args:
        classes: List of class dictionaries with class_name, term, session
        widget_key: Unique key for this selector (use different keys if you need multiple selectors)
        
    Returns:
        Dictionary with selected class data (class_name, term, session) or None
    """
    if not classes:
        return None
    
    initialize_class_persistence()
    
    # Create class options
    class_options = [f"{cls['class_name']} - {cls['term']} - {cls['session']}" for cls in classes]
    
    # Create a mapping from display string to class data
    class_map = {f"{cls['class_name']} - {cls['term']} - {cls['session']}": cls for cls in classes}
    
    # Get the last selected class from widget state (if exists) or session state
    # Widget state takes precedence to handle immediate updates
    widget_state_key = f"{widget_key}_value"
    
    if widget_state_key in st.session_state:
        # Use the widget's current value
        last_selection = st.session_state[widget_state_key]
    else:
        # Use the persisted session state
        last_selection = st.session_state.class_selection_state.get('display_string')
    
    # Find the index of the last selection, default to 0 if not found
    default_index = 0
    if last_selection and last_selection in class_options:
        try:
            default_index = class_options.index(last_selection)
        except ValueError:
            default_index = 0
    
    # Callback function to update session state immediately when selection changes
    def on_class_change():
        selected_display = st.session_state[widget_key]
        if selected_display in class_map:
            selected_data = class_map[selected_display]
            set_persistent_class_data(
                selected_data['class_name'],
                selected_data['term'],
                selected_data['session']
            )
            # Store in widget state as well
            st.session_state[widget_state_key] = selected_display
    
    # Render the selectbox with the remembered index and callback
    selected_class_display = st.selectbox(
        "Select Class", 
        class_options,
        index=default_index,
        key=widget_key,
        on_change=on_class_change
    )
    
    # Get selected class details
    if selected_class_display in class_map:
        selected_class_data = class_map[selected_class_display]
        
        # Update session state with the new selection (in case callback wasn't triggered)
        set_persistent_class_data(
            selected_class_data['class_name'],
            selected_class_data['term'],
            selected_class_data['session']
        )
        
        return selected_class_data
    
    # Fallback to first class if something goes wrong
    if classes:
        return classes[0]
    return None

def render_persistent_next_term_selector(
    classes: List[Dict[str, Any]], 
    widget_key: str = "global_term_session_selector"
) -> Optional[Dict[str, Any]]:

    if not classes:
        return None

    initialize_class_persistence()
    
    seen = set()
    class_options = []
    unique_map = {}   # maps display → (term, session)

    for cls in classes:
        display = f"{cls['term']} - {cls['session']}"
        if display not in seen:
            seen.add(display)
            class_options.append(display)
            unique_map[display] = {
                "term": cls["term"],
                "session": cls["session"]
            }
    
    # Get the last selected value from widget state or session state
    widget_state_key = f"{widget_key}_value"
    
    if widget_state_key in st.session_state:
        last_selection = st.session_state[widget_state_key]
    else:
        last_selection = st.session_state.class_selection_state.get("display_string")
    
    default_index = class_options.index(last_selection) if last_selection in class_options else 0

    # Callback function to update session state immediately
    def on_term_change():
        selected_display = st.session_state[widget_key]
        selected = unique_map.get(selected_display)
        if selected:
            set_persistent_class_data(
                None,  # class_name not needed
                selected["term"],
                selected["session"]
            )
            st.session_state[widget_state_key] = selected_display

    selected_display = st.selectbox(
        "Select Term / Session",
        class_options,
        index=default_index,
        key=widget_key,
        on_change=on_term_change
    )
    
    selected = unique_map.get(selected_display)

    if selected:
        # For persistence, store minimal data (no class name needed)
        set_persistent_class_data(
            None,                   # class_name not needed in this selector
            selected["term"],
            selected["session"]
        )

        return selected

    return None

def clear_persistent_class_selection():
    """Clear the persistent class selection"""
    if 'class_selection_state' in st.session_state:
        st.session_state.class_selection_state = {
            'class_name': None,
            'term': None,
            'session': None,
            'display_string': None
        }