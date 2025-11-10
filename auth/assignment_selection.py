# auth/assignment_selection.py
"""Assignment selection for teachers - ROLE-BASED VERSION"""

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

def get_user_roles(user_id: int) -> Dict[str, List[Dict[str, Any]]]:
    """
    Get user's available roles with their assignments
    
    Returns:
        Dictionary with 'class_teacher' and 'subject_teacher' keys,
        each containing a list of assignments for that role
    """
    try:
        assignments = get_user_assignments(user_id)
        if not assignments:
            logger.warning(f"No assignments found for user: {user_id}")
            return {"class_teacher": [], "subject_teacher": []}
        
        # Group assignments by role
        roles = {
            "class_teacher": [],
            "subject_teacher": []
        }
        
        for assignment in assignments:
            assignment_dict = {
                'id': assignment['id'],
                'class_name': assignment['class_name'],
                'term': assignment['term'],
                'session': assignment['session'],
                'subject_name': assignment['subject_name'],
                'assignment_type': assignment['assignment_type']
            }
            
            if assignment['assignment_type'] == 'class_teacher':
                roles['class_teacher'].append(assignment_dict)
            else:
                roles['subject_teacher'].append(assignment_dict)
        
        logger.info(f"User {user_id} has {len(roles['class_teacher'])} class teacher assignments and {len(roles['subject_teacher'])} subject teacher assignments")
        return roles
        
    except Exception as e:
        logger.error(f"Error getting roles for user {user_id}: {str(e)}")
        return {"class_teacher": [], "subject_teacher": []}

def render_role_selection_form(roles: Dict[str, List[Dict[str, Any]]]) -> tuple[str, bool, bool]:
    """Render role selection form"""
    role_options = []
    
    if roles['class_teacher']:
        role_options.append("Class Teacher")
    if roles['subject_teacher']:
        role_options.append("Subject Teacher")
    
    if not role_options:
        st.error("No valid roles found. Please contact administrator.")
        return None, False, False
    
    # Show role selection
    selected_role = st.selectbox("**Login as:**", role_options, label_visibility="visible")
    
    col1, col2 = st.columns(2)
    with col1:
        confirm_clicked = st.button("Confirm Selection", type="primary", width=200)
    with col2:
        logout_clicked = st.button("Logout", type="secondary", width=200)
    
    return selected_role, confirm_clicked, logout_clicked

def select_first_assignment_for_role(role_type: str, roles: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    """
    Select the first assignment for the given role type
    
    Args:
        role_type: Either 'class_teacher' or 'subject_teacher'
        roles: Dictionary containing assignments grouped by role
        
    Returns:
        First assignment for the role
    """
    if role_type == "class_teacher":
        return roles['class_teacher'][0] if roles['class_teacher'] else None
    else:
        return roles['subject_teacher'][0] if roles['subject_teacher'] else None

def handle_role_confirmation(selected_role: str, roles: Dict[str, List[Dict[str, Any]]]) -> bool:
    """Handle role confirmation and select first assignment for that role"""
    try:
        cookies = st.session_state.get("cookies")
        if not cookies:
            st.error("Session error. Please login again.")
            return False
        
        # Determine role type from selection
        if "Class Teacher" in selected_role:
            role_type = "class_teacher"
            assignment_data = select_first_assignment_for_role(role_type, roles)
        else:
            role_type = "subject_teacher"
            assignment_data = select_first_assignment_for_role(role_type, roles)
        
        if not assignment_data:
            st.error("No assignment found for selected role.")
            return False
        
        # Save assignment to session
        if SessionManager.save_assignment(assignment_data, cookies):
            st.success(f"✅ Logged in as {selected_role.replace('Login as ', '')}")
            time.sleep(0.5)
            
            st.session_state.assignment_just_selected = True
            
            # Update role in session state
            st.session_state.role = role_type
            
            # Update role in cookies
            cookies["role"] = role_type
            
            st.rerun()
            return True
        else:
            st.error("Failed to save assignment. Please try again.")
            return False
            
    except Exception as e:
        logger.error(f"Error confirming role: {str(e)}")
        st.error("An error occurred while saving assignment. Please try again.")
        return False

def select_assignment():
    """Display role-based assignment selection for teachers"""
    st.markdown(f'<div class="{CSS_CLASSES["login_container"]}">', unsafe_allow_html=True)
    st.markdown(f'<h2 class="{CSS_CLASSES["assignment_title"]}">Select Your Role</h2>', unsafe_allow_html=True)
    
    user_id = st.session_state.get('user_id')
    if not user_id:
        st.error("Session error. Please login again.")
        logout()
        return
    
    # Get user roles
    roles = get_user_roles(user_id)
    
    # Check if user has any assignments
    total_assignments = len(roles['class_teacher']) + len(roles['subject_teacher'])
    if total_assignments == 0:
        st.warning(MESSAGES["no_assignments"])
        time.sleep(2)
        logout()
        return
    
    # User has both roles - show selection
    try:
        selected_role, confirm_clicked, logout_clicked = render_role_selection_form(roles)
        
        if logout_clicked:
            logout()
            return
        
        if confirm_clicked and selected_role:
            handle_role_confirmation(selected_role, roles)
            
    except Exception as e:
        logger.error(f"Error in role selection: {str(e)}")
        st.error("An error occurred during role selection. Please try again.")
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()