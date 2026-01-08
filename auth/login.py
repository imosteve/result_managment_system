# auth/login.py
"""Login functionality - IMPROVED VERSION"""

import streamlit as st
import time
import logging
from main_utils import inject_login_css
from .config import MESSAGES, CSS_CLASSES
from .validators import validate_credentials, validate_session_cookies, validate_user_input
from .session_manager import SessionManager
from .assignment_selection import select_assignment
from database import get_user_assignments

logger = logging.getLogger(__name__)

def reset_main_app_styles():
    """Reset styles for main app after login"""
    try:
        inject_login_css("templates/main_styles.css")
    except Exception as e:
        logger.warning(f"Could not load main styles: {e}")

def render_login_form() -> tuple[str, str, bool]:
    """Render the login form"""
    # st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown(f'<div class="{CSS_CLASSES["login_container"]}">', unsafe_allow_html=True)
    st.markdown(f'<h1 class="{CSS_CLASSES["login_title"]}">🎓 Login</h1>', unsafe_allow_html=True)
    
    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        login_button = st.form_submit_button("Sign in", width="content")
        
        return username, password, login_button

def handle_login_attempt(username: str, password: str, cookies) -> bool:
    """
    Handle login attempt - IMPROVED VERSION
    """
    # Validate input
    is_valid, error_msg = validate_user_input(username, password)
    if not is_valid:
        st.error(f"⚠️ {error_msg}")
        return False
    
    # Validate credentials
    user = validate_credentials(username, password)
    if not user:
        st.error(MESSAGES["invalid_credentials"])
        return False
    
    # Create session and cookies
    if not SessionManager.create_session(user, cookies):
        st.error("Failed to create session. Please try again.")
        return False
    
    # Show success message
    st.success(MESSAGES["login_success"])
    
    # Add a small delay to ensure cookies are saved
    time.sleep(1.0)
    
    # Set a flag to indicate successful login
    st.session_state.login_successful = True
    
    # Rerun to proceed to main app
    st.rerun()
    
    return True

def handle_login_attempts(username: str, password: str) -> bool:
    """
    Handle login attempt - IMPROVED VERSION
    """
    # Validate input
    is_valid, error_msg = validate_user_input(username, password)
    if not is_valid:
        st.error(f"⚠️ {error_msg}")
        return False
    
    # Validate credentials
    user = validate_credentials(username, password)
    if not user:
        st.error(MESSAGES["invalid_credentials"])
        return False
    
    
    # Show success message
    st.success(MESSAGES["login_success"])
    
    # Add a small delay to ensure cookies are saved
    time.sleep(1.0)
    
    # Set a flag to indicate successful login
    st.session_state.login_successful = True
    
    # Rerun to proceed to main app
    st.rerun()
    
    return True

def show_loading_screen():
    """Show loading screen while initializing"""
    with st.spinner(MESSAGES["loading_auth"]):
        time.sleep(0.5)

def login(cookies):
    """Main login function - UPDATED VERSION"""
    try:
        # Handle post-login redirect
        if st.session_state.get('login_successful'):
            del st.session_state['login_successful']
            
            role = st.session_state.get('role')
            user_id = st.session_state.get('user_id')
            
            # Admins go directly to main app
            if role in ["admin", "superadmin"]:
                # reset_main_app_styles()
                inject_login_css("templates/main_styles.css")
                return
            
            # Teachers need assignment selection
            assignments = get_user_assignments(user_id)
            
            if not assignments:
                st.error("⚠️ You don't have any class or subject assignments yet.")
                if st.button("Logout"):
                    from .logout import logout
                    logout()
                st.stop()
                return
            
            # Show assignment selection if needed
            if "assignment" not in st.session_state:
                inject_login_css("templates/login_styles.css")
                select_assignment()
                return
            else:
                reset_main_app_styles()
                return
        
        # Check for existing valid session
        if validate_session_cookies(cookies):
            role = st.session_state.get('role')
            user_id = st.session_state.get('user_id')
            
            # Admins can proceed
            if role in ["admin", "superadmin"]:
                reset_main_app_styles()
                return
            
            # Teachers need assignment
            if "assignment" not in st.session_state:
                assignments = get_user_assignments(user_id)
                if not assignments:
                    st.error("⚠️ You don't have any assignments yet.")
                    if st.button("🚪 Logout"):
                        from .logout import logout
                        logout()
                    st.stop()
                    return
                inject_login_css("templates/login_styles.css")
                select_assignment()
                return
            else:
                reset_main_app_styles()
                return
        
        # Show login form
        inject_login_css("templates/login_styles.css")
        username, password, login_clicked = render_login_form()
        
        if login_clicked:
            handle_login_attempt(username, password, cookies)
        
        st.markdown('</div>', unsafe_allow_html=True)
        st.stop()
        
    except Exception as e:
        logger.error(f"Error in login function: {str(e)}")
        st.error("An error occurred during authentication. Please refresh the page.")
        st.stop()
