# main_utils.py

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
            # st.warning(f"CSS file not found: {file_path}")
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
                font-size: 24px !important;
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
                padding: 10px;
                text-align: center;
                box-shadow: 0 2px 6px rgba(0,0,0,0.05);
            }
            /* Adjust layout spacing */
            div[data-testid="stHorizontalBlock"] > div {
                padding: 4px;
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


def create_metric_5col_broadsheet(subjects, students, class_average, broadsheet_data, class_name, term, session, user_id=None, role=None):
    from database_school import get_subjects_by_class, get_scores_for_class

    # All subjects defined for this class (session/term-independent)
    all_subjects = get_subjects_by_class(class_name)
    all_subject_names = {
        (s["subject_name"] if isinstance(s, dict) else s[1])
        for s in all_subjects
    }

    # Subjects that have at least one real score row in the DB for this class/session/term
    score_rows = get_scores_for_class(class_name, session, term)
    subjects_with_scores = {row["subject_name"] for row in score_rows}

    subjects_added          = len(subjects_with_scores)
    subjects_without_scores = sorted(all_subject_names - subjects_with_scores)
    subjects_not_added      = len(subjects_without_scores)

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
        st.markdown("**Subjects Without Scores:**")
        subjects_text = ", ".join(subjects_without_scores)
        st.markdown(f"<div style='background-color: #fff3cd; padding: 10px; border-radius: 5px; border-left: 4px solid #ffc107;'>{subjects_text}</div>", unsafe_allow_html=True)


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
            <h2 style='color:{text_color}; font-size:{font_size}; margin-top:0; margin-bottom:20px;'>
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
            'class_name':     None,
            'display_string': None,
        }

def get_persistent_class_data():
    """Get the currently selected class name from session state"""
    initialize_class_persistence()
    return st.session_state.class_selection_state

def set_persistent_class_data(class_name: str, term: str = None, session: str = None):
    """
    Store the selected class name in session state.
    term and session are accepted for backwards compatibility but ignored —
    they are read from academic_settings at runtime.
    """
    initialize_class_persistence()
    st.session_state.class_selection_state = {
        'class_name':     class_name,
        'display_string': class_name,
    }

def render_persistent_class_selector(classes: List[Dict[str, Any]], 
                                    widget_key: str = "global_class_selector") -> Optional[Dict[str, Any]]:
    """
    Render a class selector that persists selection across page navigation.

    New schema: classes are session-independent permanent definitions.
    They only carry {id, class_name, description, created_at}.
    Active session/term are read from academic_settings, not from the class.

    Args:
        classes:    List of class dicts — must contain at least 'class_name'.
        widget_key: Unique key for this selector widget.

    Returns:
        Dict with at least 'class_name', or None if no classes available.
    """
    if not classes:
        return None

    initialize_class_persistence()

    class_options = [c["class_name"] for c in classes]
    class_map     = {c["class_name"]: c for c in classes}

    # Restore last selection
    widget_state_key = f"{widget_key}_value"
    last_selection = (
        st.session_state.get(widget_state_key)
        or st.session_state.class_selection_state.get("class_name")
    )

    default_index = 0
    if last_selection and last_selection in class_options:
        try:
            default_index = class_options.index(last_selection)
        except ValueError:
            default_index = 0

    def on_class_change():
        selected = st.session_state[widget_key]
        if selected in class_map:
            st.session_state.class_selection_state["class_name"]     = selected
            st.session_state.class_selection_state["display_string"] = selected
            st.session_state[widget_state_key] = selected

    selected_class_name = st.selectbox(
        "Select Class",
        class_options,
        index=default_index,
        key=widget_key,
        on_change=on_class_change,
    )

    if selected_class_name in class_map:
        st.session_state.class_selection_state["class_name"]     = selected_class_name
        st.session_state.class_selection_state["display_string"] = selected_class_name
        return class_map[selected_class_name]

    return classes[0] if classes else None

def render_persistent_next_term_selector(
    classes: List[Dict[str, Any]],
    widget_key: str = "global_term_session_selector"
) -> Optional[Dict[str, Any]]:
    """
    In the new schema, term and session are global (from academic_settings),
    not per-class. This selector simply reads the active context and returns
    it so callers can use it to load / save next_term_info records.

    The `classes` argument is accepted for backwards compatibility but unused.

    Returns:
        dict: {"term": str, "session": str} from the active academic settings,
              or None if not configured.
    """
    from database_school import get_active_session, get_active_term_name

    session = get_active_session()
    term    = get_active_term_name()

    if not session:
        st.warning("⚠️ No active session configured. Ask an admin to set one in Academic Settings.")
        return None

    st.info(f"**Active:** {session} — {term} Term")
    return {"term": term, "session": session}

def clear_persistent_class_selection():
    """Clear the persistent class selection"""
    if 'class_selection_state' in st.session_state:
        st.session_state.class_selection_state = {
            'class_name': None,
            'term': None,
            'session': None,
            'display_string': None
        }