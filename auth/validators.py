"""Authentication validation functions"""

import streamlit as st
import logging
from typing import Optional, Dict, Any
from database import get_user_by_username

logger = logging.getLogger(__name__)

def validate_credentials(username: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Validate user credentials against database
    
    Args:
        username: Username to validate
        password: Password to validate
        
    Returns:
        User data if valid, None if invalid
    """
    if not username or not password:
        return None
        
    try:
        user = get_user_by_username(username)
        if user and user["password"] == password:
            logger.info(f"Successful login for user: {username}")
            return user
        else:
            logger.warning(f"Failed login attempt for user: {username}")
            return None
    except Exception as e:
        logger.error(f"Error validating credentials for {username}: {str(e)}")
        return None

def validate_session_cookies(cookies) -> bool:
    """
    Validate session cookies for existing authentication
    
    Args:
        cookies: Cookie manager instance
        
    Returns:
        True if valid session exists, False otherwise
    """
    if not cookies:
        logger.debug("Cookies object is None or falsy")
        return False

    try:
        # Safely attempt to get cookie values with default fallbacks
        authenticated = cookies.get("authenticated", "false") == "true"
        user_id = cookies.get("user_id")
        role = cookies.get("role")

        # Validate all required cookie values are present and correct
        if not authenticated or not user_id or not role:
            logger.debug("Missing or invalid session cookies")
            return False

        # Convert user_id to integer, handle potential conversion errors
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            logger.debug("Invalid user_id format in cookies")
            return False

        # Set session state
        st.session_state.authenticated = True
        st.session_state.user_id = user_id
        st.session_state.role = role
        st.session_state.username = cookies.get("username", f"User_{user_id}")

        # Restore assignment if exists
        if role in ["class_teacher", "subject_teacher"]:
            assignment_class = cookies.get("assignment_class")
            assignment_term = cookies.get("assignment_term")
            assignment_session = cookies.get("assignment_session")
            assignment_subject = cookies.get("assignment_subject")

            if assignment_class and assignment_term and assignment_session:
                st.session_state.assignment = {
                    "class_name": assignment_class,
                    "term": assignment_term,
                    "session": assignment_session,
                    "subject_name": assignment_subject if assignment_subject else None
                }
            else:
                logger.debug("Incomplete assignment data in cookies")

        logger.info(f"Session validated for user_id: {user_id}, role: {role}")
        return True

    except Exception as e:
        logger.error(f"Error validating session cookies: {str(e)}")
        return False

def validate_session_with_mobile_support(cookies):
    """Enhanced session validation with mobile support"""
    try:
        # Import here to avoid circular imports
        from auth.session_manager import SessionManager
        
        # First check if session exists in session_state
        if st.session_state.get("authenticated"):
            SessionManager.update_activity()
            return True
        
        # Try to validate from cookies (works for both desktop and mobile)
        if SessionManager.validate_mobile_session(cookies):
            return True
        
        # If all else fails, clear any stale data
        SessionManager.clear_session(cookies)
        return False
        
    except Exception as e:
        logger.error(f"Error in session validation: {e}")
        return False
    
def validate_user_input(username: str, password: str) -> tuple[bool, str]:
    """
    Validate user input for login form
    
    Args:
        username: Username input
        password: Password input
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not username or not password:
        return False, "Please fill in both fields."
    
    if len(username.strip()) == 0:
        return False, "Username cannot be empty."
    
    if len(password) < 4:  # Minimum password length
        return False, "Password too short."
    
    return True, ""

# Additional debug function (keep for troubleshooting)
def debug_cookies(cookies):
    """
    Debug function to understand your cookie manager better
    Call this from your login function to see what's happening
    """
    print("=== COOKIE DEBUG INFO ===")
    print(f"Cookie object type: {type(cookies)}")
    print(f"Cookie object: {cookies}")
    
    if cookies:
        print("Cookie object attributes:")
        for attr in dir(cookies):
            if not attr.startswith('_'):
                try:
                    value = getattr(cookies, attr)
                    print(f"  - {attr}: {value} (type: {type(value)})")
                except Exception as e:
                    print(f"  - {attr}: Error getting value - {e}")
    
    print("=== END DEBUG INFO ===")