import streamlit as st
import pandas as pd
import logging
from typing import Optional, List, Dict, Any
from utils import assign_grade, inject_login_css
from database import (
    get_all_classes, get_students_by_class, get_subjects_by_class,
    get_scores_by_class_subject, save_scores, clear_all_scores,
    get_user_assignments
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def enter_scores():
    """Main function to handle score entry with role-based access control"""
    try:
        # Authentication check
        if not _check_authentication():
            return

        # Role-based authorization check
        if not _check_authorization():
            return

        # Initialize session state variables
        _initialize_session_state()

        # Set page configuration
        st.set_page_config(page_title="Enter Scores", layout="wide")
        inject_login_css("templates/tabs_styles.css")

        # Render page header
        _render_page_header()

        # Main application logic
        _render_score_management_interface()

    except Exception as e:
        logger.error(f"Error in enter_scores: {str(e)}")
        st.error("❌ An unexpected error occurred. Please try again or contact support.")

def _check_authentication() -> bool:
    """Check if user is authenticated"""
    if not st.session_state.get("authenticated", False):
        st.error("⚠️ Please log in first.")
        st.switch_page("main.py")
        return False
    return True

def _check_authorization() -> bool:
    """Check if user has proper role-based authorization"""
    allowed_roles = ["admin", "class_teacher", "subject_teacher"]
    user_role = st.session_state.get("role")
    
    if user_role not in allowed_roles:
        st.error("⚠️ Access denied. You don't have permission to enter scores.")
        logger.warning(f"Unauthorized access attempt by user {st.session_state.get('user_id')} with role {user_role}")
        return False
    return True

def _initialize_session_state():
    """Initialize required session state variables"""
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    if 'role' not in st.session_state:
        st.session_state.role = None
    if 'assignment' not in st.session_state:
        st.session_state.assignment = None

def _render_page_header():
    """Render the page header"""
    st.markdown(
        """
        <div style='width: auto; margin: auto; text-align: center; background-color: #c6b7b1; padding: 20px; border-radius: 10px;'>
            <h3 style='color:#000; font-size:30px; margin:0;'>
                Manage Subject Scores
            </h3>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.markdown("<br>", unsafe_allow_html=True)

def _render_score_management_interface():
    """Render the main score management interface"""
    user_id = st.session_state.user_id
    role = st.session_state.role

    # Get classes based on user role
    classes = _get_accessible_classes(user_id, role)
    if not classes:
        st.warning("⚠️ No classes found or accessible to you.")
        return

    # Class selection interface
    selected_class_data = _render_class_selection(classes, role)
    if not selected_class_data:
        return

    # Extract class details
    class_name = selected_class_data['class_name']
    term = selected_class_data['term']
    session = selected_class_data['session']

    # Get subjects for the selected class
    subjects = _get_accessible_subjects(class_name, term, session, user_id, role)
    if not subjects:
        st.warning(f"⚠️ No subjects found for {class_name} - {term} - {session}.")
        return

    # Subject selection interface
    selected_subject = _render_subject_selection(subjects, role)
    if not selected_subject:
        return

    # Get students for the selected class
    students = _get_accessible_students(class_name, term, session, user_id, role)
    if not students:
        st.warning(f"⚠️ No students found in {class_name} - {term} - {session}.")
        return

    # Get existing scores
    existing_scores = _get_existing_scores(class_name, selected_subject, term, session, user_id, role)
    
    # Render tabs for different operations
    _render_score_tabs(students, existing_scores, class_name, selected_subject, term, session)

def _get_accessible_classes(user_id: int, role: str) -> List[Dict[str, Any]]:
    """Get classes accessible to the user based on their role"""
    try:
        return get_all_classes(user_id, role)
    except Exception as e:
        logger.error(f"Error fetching classes for user {user_id}: {str(e)}")
        st.error("❌ Failed to load classes. Please try again.")
        return []

def _render_class_selection(classes: List[Dict[str, Any]], role: str) -> Optional[Dict[str, Any]]:
    """Render class selection interface"""
    class_options = [f"{cls['class_name']} - {cls['term']} - {cls['session']}" for cls in classes]
    
    # For non-admin users, check if they have specific assignments
    if role in ["class_teacher", "subject_teacher"]:
        assignment = st.session_state.get("assignment")
        if assignment:
            allowed_class = f"{assignment['class_name']} - {assignment['term']} - {assignment['session']}"
            if allowed_class in class_options:
                class_options = [allowed_class]
                selected_class_display = st.selectbox("Select Class", class_options, disabled=True)
            else:
                st.error("⚠️ Your assigned class is not available.")
                return None
        else:
            selected_class_display = st.selectbox("Select Class", class_options)
    else:
        selected_class_display = st.selectbox("Select Class", class_options)

    # Get selected class details
    try:
        selected_index = class_options.index(selected_class_display)
        return classes[selected_index]
    except (ValueError, IndexError) as e:
        logger.error(f"Error selecting class: {str(e)}")
        st.error("❌ Invalid class selection.")
        return None

def _get_accessible_subjects(class_name: str, term: str, session: str, user_id: int, role: str) -> List[tuple]:
    """Get subjects accessible to the user for the selected class"""
    try:
        return get_subjects_by_class(class_name, term, session, user_id, role)
    except Exception as e:
        logger.error(f"Error fetching subjects for class {class_name}: {str(e)}")
        st.error("❌ Failed to load subjects. Please try again.")
        return []

def _render_subject_selection(subjects: List[tuple], role: str) -> Optional[str]:
    """Render subject selection interface"""
    subject_names = [s[1] for s in subjects]
    
    # For subject teachers, restrict to assigned subject
    if role == "subject_teacher":
        assignment = st.session_state.get("assignment", {})
        allowed_subject = assignment.get("subject_name")
        if allowed_subject and allowed_subject in subject_names:
            subject_names = [allowed_subject]
            return st.selectbox("Select Subject", subject_names, disabled=True)
        elif allowed_subject:
            st.error("⚠️ Your assigned subject is not available in this class.")
            return None
    
    return st.selectbox("Select Subject", subject_names)

def _get_accessible_students(class_name: str, term: str, session: str, user_id: int, role: str) -> List[tuple]:
    """Get students accessible to the user for the selected class"""
    try:
        return get_students_by_class(class_name, term, session, user_id, role)
    except Exception as e:
        logger.error(f"Error fetching students for class {class_name}: {str(e)}")
        st.error("❌ Failed to load students. Please try again.")
        return []

def _get_existing_scores(class_name: str, subject: str, term: str, session: str, user_id: int, role: str) -> Dict[str, tuple]:
    """Get existing scores for the class and subject"""
    try:
        scores = get_scores_by_class_subject(class_name, subject, term, session, user_id, role)
        return {score[1]: score for score in scores}  # score[1] is student_name
    except Exception as e:
        logger.error(f"Error fetching existing scores: {str(e)}")
        st.error("❌ Failed to load existing scores.")
        return {}

def _render_score_tabs(students: List[tuple], score_map: Dict[str, tuple], 
                      class_name: str, subject: str, term: str, session: str):
    """Render the tabs for score management operations"""
    tab1, tab2, tab3 = st.tabs(["📝 Enter Scores", "👀 Preview Scores", "🗑️ Clear All Scores"])

    with tab1:
        _render_score_entry_tab(students, score_map, class_name, subject, term, session)

    with tab2:
        _render_score_preview_tab(students, score_map)

    with tab3:
        _render_clear_scores_tab(score_map, class_name, subject, term, session)

def _render_score_entry_tab(students: List[tuple], score_map: Dict[str, tuple],
                           class_name: str, subject: str, term: str, session: str):
    """Render the score entry tab"""
    st.subheader("📝 Enter Scores")
    
    # Build editable data
    editable_rows = []
    for student in students:
        student_name = student[1]
        existing = score_map.get(student_name)
        test_score = float(existing[3]) if existing and existing[3] is not None else 0.0
        exam_score = float(existing[4]) if existing and existing[4] is not None else 0.0
        
        editable_rows.append({
            "Student": student_name,
            "Test (30%)": test_score,
            "Exam (70%)": exam_score,
        })

    if not editable_rows:
        st.warning("⚠️ No students available for score entry.")
        return

    # Create editable DataFrame with validation
    try:
        editable_df = st.data_editor(
            pd.DataFrame(editable_rows),
            column_config={
                "Student": st.column_config.TextColumn(
                    "Student", 
                    disabled=True, 
                    width="large"
                ),
                "Test (30%)": st.column_config.NumberColumn(
                    "Test (30%)", 
                    min_value=0, 
                    max_value=30, 
                    width="medium",
                    format="%.1f"
                ),
                "Exam (70%)": st.column_config.NumberColumn(
                    "Exam (70%)", 
                    min_value=0, 
                    max_value=70, 
                    width="medium",
                    format="%.1f"
                ),
            },
            hide_index=True,
            use_container_width=True,
            key="score_editor"
        )

        # Validate scores before saving
        if _validate_scores(editable_df):
            if st.button("💾 Save All Scores", key="save_scores", type="primary"):
                _save_scores_to_database(editable_df, class_name, subject, term, session)
        else:
            st.warning("⚠️ Please correct invalid scores before saving.")

    except Exception as e:
        logger.error(f"Error in score entry interface: {str(e)}")
        st.error("❌ Error creating score entry interface.")

def _validate_scores(df: pd.DataFrame) -> bool:
    """Validate score data before saving"""
    try:
        for _, row in df.iterrows():
            test_score = float(row.get("Test (30%)", 0))
            exam_score = float(row.get("Exam (70%)", 0))
            
            # Check score ranges
            if not (0 <= test_score <= 30):
                st.error(f"❌ Invalid test score for {row['Student']}: {test_score}. Must be between 0 and 30.")
                return False
            
            if not (0 <= exam_score <= 70):
                st.error(f"❌ Invalid exam score for {row['Student']}: {exam_score}. Must be between 0 and 70.")
                return False
        
        return True
    except Exception as e:
        logger.error(f"Error validating scores: {str(e)}")
        return False

def _save_scores_to_database(df: pd.DataFrame, class_name: str, subject: str, term: str, session: str):
    """Save scores to the database"""
    try:
        scores_to_save = []
        
        for _, row in df.iterrows():
            student = row["Student"]
            test = float(row.get("Test (30%)", 0))
            exam = float(row.get("Exam (70%)", 0))
            total = test + exam
            grade = assign_grade(total)
            
            scores_to_save.append({
                "student": student,
                "class": class_name,
                "subject": subject,
                "term": term,
                "session": session,
                "test": test,
                "exam": exam,
                "total": total,
                "grade": grade
            })
        
        # Save scores with position calculation
        save_scores(scores_to_save, class_name, subject, term, session)
        
        # Success message
        st.success(f"✅ All scores saved successfully for {subject} in {class_name} - {term} - {session}!")
        logger.info(f"Scores saved for {subject} in {class_name} - {term} - {session} by user {st.session_state.user_id}")
        
        # Refresh the page to show updated data
        st.rerun()
        
    except Exception as e:
        logger.error(f"Error saving scores: {str(e)}")
        st.error("❌ Failed to save scores. Please try again.")

def _render_score_preview_tab(students: List[tuple], score_map: Dict[str, tuple]):
    """Render the score preview tab"""
    st.subheader("👀 Preview Scores")
    
    # Build preview data
    preview_data = []
    for idx, student in enumerate(students, 1):
        student_name = student[1]
        existing = score_map.get(student_name)
        
        if existing:
            test = float(existing[3]) if existing[3] is not None else 0.0
            exam = float(existing[4]) if existing[4] is not None else 0.0
            total = float(existing[5]) if existing[5] is not None else test + exam
            grade = existing[6] if existing[6] else assign_grade(total)
            position = _format_ordinal(existing[7]) if existing[7] else "-"
        else:
            test = exam = total = 0.0
            grade = assign_grade(0.0)
            position = "-"
        
        preview_data.append({
            "S/N": str(idx),
            "Student": student_name,
            "Test": f"{test:.1f}",
            "Exam": f"{exam:.1f}",
            "Total": f"{total:.1f}",
            "Grade": grade,
            "Position": position
        })

    if preview_data:
        st.dataframe(
            pd.DataFrame(preview_data),
            column_config={
                "S/N": st.column_config.TextColumn("S/N", width="small"),
                "Student": st.column_config.TextColumn("Student", width="large"),
                "Test": st.column_config.TextColumn("Test", width="medium"),
                "Exam": st.column_config.TextColumn("Exam", width="medium"),
                "Total": st.column_config.TextColumn("Total", width="medium"),
                "Grade": st.column_config.TextColumn("Grade", width="medium"),
                "Position": st.column_config.TextColumn("Position", width="medium")
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("📝 No scores available to preview.")

def _render_clear_scores_tab(score_map: Dict[str, tuple], class_name: str, 
                           subject: str, term: str, session: str):
    """Render the clear scores tab"""
    st.subheader("🗑️ Clear All Scores")
    
    st.warning("⚠️ **DANGER ZONE**: This action will permanently delete all scores for the selected subject in this class. This action cannot be undone.")
    
    if score_map:
        st.info(f"📊 Found {len(score_map)} student scores to be cleared.")
        
        # Double confirmation for safety
        confirm_clear = st.checkbox("I understand this action cannot be undone")
        confirm_text = st.text_input(
            "Type 'DELETE' to confirm:",
            placeholder="Type DELETE to confirm"
        )
        
        is_confirmed = confirm_clear and confirm_text.strip().upper() == "DELETE"
        
        if st.button(
            "🗑️ Clear All Scores", 
            key="clear_all_scores", 
            disabled=not is_confirmed,
            type="secondary"
        ):
            if _clear_all_scores_from_database(class_name, subject, term, session):
                st.success(f"✅ All scores cleared successfully for {subject} in {class_name} - {term} - {session}!")
                logger.info(f"Scores cleared for {subject} in {class_name} - {term} - {session} by user {st.session_state.user_id}")
                st.rerun()
    else:
        st.info("📝 No scores available to clear.")

def _clear_all_scores_from_database(class_name: str, subject: str, term: str, session: str) -> bool:
    """Clear all scores from the database"""
    try:
        return clear_all_scores(class_name, subject, term, session)
    except Exception as e:
        logger.error(f"Error clearing scores: {str(e)}")
        st.error("❌ Failed to clear scores. Please try again.")
        return False

def _format_ordinal(n: int) -> str:
    """Format number as ordinal (1st, 2nd, 3rd, etc.)"""
    if not isinstance(n, int) or n <= 0:
        return str(n) if n is not None else "-"
    
    if 10 <= n % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    
    return f"{n}{suffix}"

# Additional utility functions for production readiness

def _get_user_assignment_context() -> Optional[Dict[str, Any]]:
    """Get the user's assignment context for role-based restrictions"""
    user_id = st.session_state.get("user_id")
    role = st.session_state.get("role")
    
    if not user_id or role == "admin":
        return None
    
    try:
        assignments = get_user_assignments(user_id)
        if assignments:
            # Return the first assignment for simplicity
            # In a more complex system, you might need assignment selection logic
            assignment = assignments[0]
            return {
                "class_name": assignment[1],
                "term": assignment[2], 
                "session": assignment[3],
                "subject_name": assignment[4]
            }
    except Exception as e:
        logger.error(f"Error fetching user assignments: {str(e)}")
    
    return None

def _display_role_info():
    """Display user role and permissions information"""
    role = st.session_state.get("role", "Unknown")
    username = st.session_state.get("username", "Unknown User")
    
    role_descriptions = {
        "admin": "Full access to all classes, subjects, and students",
        "class_teacher": "Access to assigned classes and all their subjects",
        "subject_teacher": "Access to assigned subjects in assigned classes"
    }
    
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 👤 User Information")
        st.markdown(f"**User:** {username}")
        st.markdown(f"**Role:** {role.replace('_', ' ').title()}")
        st.markdown(f"**Permissions:** {role_descriptions.get(role, 'Limited access')}")
        
        if role in ["class_teacher", "subject_teacher"]:
            assignment = _get_user_assignment_context()
            if assignment:
                st.markdown("### 📋 Assignment")
                st.markdown(f"**Class:** {assignment['class_name']}")
                st.markdown(f"**Term:** {assignment['term']}")
                st.markdown(f"**Session:** {assignment['session']}")
                if assignment.get('subject_name'):
                    st.markdown(f"**Subject:** {assignment['subject_name']}")

# Initialize assignment context on page load
if 'assignment_loaded' not in st.session_state:
    st.session_state.assignment = _get_user_assignment_context()
    st.session_state.assignment_loaded = True

# Display role information in sidebar
_display_role_info()

if __name__ == "__main__":
    enter_scores()