# auth/logout.py
"""Logout functionality"""

import streamlit as st
import time
import logging
from .config import MESSAGES
from .session_manager import SessionManager

logger = logging.getLogger(__name__)

def logout():
    """
    Handle user logout process
    """
    cookies = st.session_state.get("cookies")
    username = st.session_state.get("username", "Unknown")
    
    try:
        # Clear session and cookies
        if SessionManager.clear_session(cookies):
            logger.info(f"User {username} logged out successfully")
            # st.success(MESSAGES["logout_success"])
            # time.sleep(0.5)  # Brief pause for user feedback
            st.session_state.authenticated = False
            st.rerun()
        else:
            raise Exception("Failed to clear session")
            
    except Exception as e:
        logger.error(f"Logout error for user {username}: {str(e)}")
        st.error(MESSAGES["logout_failed"].format(str(e)))
        
        # Force clear session state as fallback
        _force_clear_session_state()
        st.rerun()

def _force_clear_session_state():
    """Force clear session state as a fallback"""
    try:
        session_keys = [
            "authenticated", "user_id", "role", "username", "login_time",
            "assignment", "last_activity", "session_id"
        ]
        
        for key in session_keys:
            if key in st.session_state:
                del st.session_state[key]
        
        # Set authentication to False explicitly
        st.session_state.authenticated = False
        st.session_state.user_id = None
        st.session_state.role = None
        st.session_state.assignment = None
        
        logger.info("Session state forcefully cleared")
    except Exception as e:
        logger.error(f"Error force clearing session state: {str(e)}")

def is_logout_requested() -> bool:
    """
    Check if logout has been requested
    
    Returns:
        True if logout requested, False otherwise
    """
    return st.session_state.get("logout_requested", False)

def request_logout():
    """Request logout (useful for programmatic logout)"""
    st.session_state.logout_requested = True

def clear_logout_request():
    """Clear logout request flag"""
    if "logout_requested" in st.session_state:
        del st.session_state.logout_requested