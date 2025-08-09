# auth/assignment_selection.py
"""Assignment selection for teachers"""

import streamlit as st
import time
import logging
from typing import List, Dict, Any
from database import get_user_assignments
from .config import MESSAGES, CSS_CLASSES
from .session_manager import SessionManager
from .logout import logout
from utils import inject_login_css

logger = logging.getLogger(__name__)

def format_assignment_display(assignment: Dict[str, Any]) -> str:
    """
    Format assignment data for display
    
    Args:
        assignment: Assignment data dictionary
        
    Returns:
        Formatted display string
    """
    class_display = f"{assignment['class_name']} - {assignment['term']} - {assignment['session']}"
    # Handle sqlite3.Row objects which don't have .get() method
    subject_name = assignment.get('subject_name') if hasattr(assignment, 'get') else assignment['subject_name']
    if subject_name:
        class_display += f" - {subject_name}"
    return class_display

def get_user_assignment_options(user_id: int) -> List[Dict[str, Any]]:
    """
    Get formatted assignment options for user
    
    Args:
        user_id: User ID
        
    Returns:
        List of assignment data converted to dictionaries
    """
    try:
        assignments = get_user_assignments(user_id)
        if not assignments:
            logger.warning(f"No assignments found for user ID: {user_id}")
            return []
        
        # Convert sqlite3.Row objects to dictionaries
        assignment_dicts = []
        for assignment in assignments:
            assignment_dict = {
                'id': assignment['id'],
                'class_name': assignment['class_name'],
                'term': assignment['term'],
                'session': assignment['session'],
                'subject_name': assignment['subject_name']
            }
            assignment_dicts.append(assignment_dict)
        
        logger.info(f"Found {len(assignment_dicts)} assignments for user ID: {user_id}")
        return assignment_dicts
    except Exception as e:
        logger.error(f"Error getting assignments for user {user_id}: {str(e)}")
        return []

def render_assignment_selection_form(assignments: List[Dict[str, Any]]) -> tuple[str, int, bool]:
    """
    Render assignment selection form
    
    Args:
        assignments: List of assignment data
        
    Returns:
        Tuple of (selected_assignment, selected_index, confirm_clicked)
    """
    assignment_options = [format_assignment_display(assignment) for assignment in assignments]
    
    selected_assignment = st.selectbox("Select Your Assignment", assignment_options)
    selected_index = assignment_options.index(selected_assignment)
    confirm_clicked = st.button("Confirm Selection")
    
    return selected_assignment, selected_index, confirm_clicked

def handle_assignment_confirmation(assignment_data: Dict[str, Any]) -> bool:
    """
    Handle assignment confirmation
    
    Args:
        assignment_data: Selected assignment data
        
    Returns:
        True if successful, False otherwise
    """
    try:
        cookies = st.session_state.get("cookies")
        if not cookies:
            st.error("Session error. Please login again.")
            return False
        
        # Save assignment to session
        if SessionManager.save_assignment(assignment_data, cookies):
            st.success(MESSAGES["assignment_selected"])
            time.sleep(0.5)  # Brief pause for user feedback
            st.rerun()
            return True
        else:
            st.error("Failed to save assignment. Please try again.")
            return False
    except Exception as e:
        logger.error(f"Error confirming assignment: {str(e)}")
        st.error("An error occurred while saving assignment. Please try again.")
        return False

def select_assignment():
    """
    Display assignment selection for class/subject teachers
    """
    # Show login form
    inject_login_css("templates/login_styles.css")
    st.markdown(f'<div class="{CSS_CLASSES["login_container"]}">', unsafe_allow_html=True)
    st.markdown(f'<h2 class="{CSS_CLASSES["assignment_title"]}">Select Assignment</h2>', unsafe_allow_html=True)
    
    user_id = st.session_state.get('user_id')
    if not user_id:
        st.error("Session error. Please login again.")
        logout()
        return
    
    # Get user assignments
    assignments = get_user_assignment_options(user_id)
    
    if not assignments:
        st.warning(MESSAGES["no_assignments"])
        time.sleep(2)  # Brief delay to show warning
        logout()  # Automatically log out
        return
    
    # Render selection form
    try:
        selected_assignment, selected_index, confirm_clicked = render_assignment_selection_form(assignments)
        
        if confirm_clicked:
            selected_assignment_data = assignments[selected_index]
            handle_assignment_confirmation(selected_assignment_data)
            
    except Exception as e:
        logger.error(f"Error in assignment selection: {str(e)}")
        st.error("An error occurred during assignment selection. Please try again.")
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()