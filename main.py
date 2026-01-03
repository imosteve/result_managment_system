# main.py - Updated for Section-Based Navigation
import streamlit as st
import logging
import traceback
from datetime import datetime

# Import configuration first
from config import APP_CONFIG

# Setup logging
from logging_setup import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

# Import managers
from app_manager import ApplicationManager
from security_manager import SecurityManager

# Import authentication
from auth.login import login
from auth.logout import logout

# Import database functions
from database import create_user, get_user_by_username

def setup_default_users():
    """Create default superadmin and admin users if they don't exist"""
    try:
        # Check and create superadmin
        if not get_user_by_username("superadmin"):
            if create_user("superadmin", "superadmin", "superadmin"):
                logger.info("Default superadmin user created")
        
        # Check and create admin
        if not get_user_by_username("admin"):
            if create_user("admin", "admin", "admin"):
                logger.info("Default admin user created")
                
    except Exception as e:
        logger.error(f"Error setting up default users: {str(e)}")

def render_logout_button():
    """Render logout button with improved styling"""
    with st.sidebar:
        # st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚪 Logout", type="primary", width="stretch"):
            st.query_params.clear()
            logout()

def validate_session_data(role: str, username: str, user_id: int) -> bool:
    """Validate user session data - allows None role for teachers"""
    # Check username and user_id
    if not username or not user_id:
        logger.error(f"Invalid session data: role={role}, username={username}, user_id={user_id}")
        SecurityManager.force_logout("Invalid session data")
        return False
    
    # Role can be None for teachers who haven't selected an assignment yet
    return True

def check_teacher_assignment(role: str) -> bool:
    """
    Check if teacher has selected an assignment
    
    Args:
        role: User role
        
    Returns:
        True if assignment check passed, False otherwise
    """
    # Teachers must have an assignment selected
    if role in ["class_teacher", "subject_teacher"]:
        if "assignment" not in st.session_state:
            logger.warning(f"Teacher {st.session_state.get('username')} has no assignment selected")
            st.warning("⚠️ No assignment selected. Please logout and select an assignment.")
            
            # Add logout button for convenience
            if st.button("Logout to Select Assignment"):
                logout()
            
            st.stop()
            return False
    
    return True

def render_authenticated_app(app: ApplicationManager, cookies):
    """Render the main authenticated application with new navigation"""
    try:
        # Security checks
        if not SecurityManager.check_session_timeout():
            return  # Security manager will handle logout
        
        # Get user information
        role = st.session_state.get('role', 'unknown')
        username = st.session_state.get('username', 'Unknown User')
        user_id = st.session_state.get('user_id')
        
        # Validate user data
        if not validate_session_data(role, username, user_id):
            return  # Validation failed, user logged out
        
        # Check teacher assignment (if applicable)
        if not check_teacher_assignment(role):
            return  # Teacher needs to select assignment
        
        # Render main application
        st.markdown('<div class="main-content">', unsafe_allow_html=True)
        
        # Render header
        app.render_header()
        
        # Setup sidebar with logo and user info
        st.logo('static/logos/SU_logo.png', size='large')
        
        # Handle navigation with sections
        app.handle_navigation(role, username)
        
        # Render logout button
        render_logout_button()
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Update user activity timestamp
        st.session_state.last_activity = datetime.now()
        
    except Exception as e:
        logger.error(f"Error in authenticated app: {str(e)}\n{traceback.format_exc()}")
        st.error("❌ An error occurred. Please refresh the page or contact support.")
        
        # Show error details to admins
        if st.session_state.get('role') in ['superadmin', 'admin']:
            with st.expander("🔧 Error Details (Admin Only)"):
                st.code(f"{str(e)}\n\n{traceback.format_exc()}")

def main():
    """Main application entry point"""
    try:
        # Initialize application manager
        app = ApplicationManager()
        
        # Initialize security
        SecurityManager.initialize_security_headers()
        
        # Initialize database
        if not app.initialize_database():
            st.stop()
        
        # Setup default users (only runs once if users don't exist)
        setup_default_users()
        
        # Initialize mobile support
        app.initialize_mobile_support()

        # Initialize cookies
        cookies = app.initialize_cookies()
        if cookies is None:
            st.stop()
        
        # Handle authentication
        login(cookies)
        
        # If authenticated, render the app
        if st.session_state.get("authenticated", False):
            render_authenticated_app(app, cookies)
        else:
            logger.warning("User reached main app without authentication")
            st.stop()
            pass
        
    except Exception as e:
        logger.critical(f"Critical error in main application: {str(e)}\n{traceback.format_exc()}")
        st.error("❌ A critical error occurred. Please refresh the page or contact support.")
        
        # Show error details to admins
        if st.session_state.get('role') in ['superadmin', 'admin']:
            with st.expander("🔧 Critical Error Details (Admin Only)"):
                st.code(f"{str(e)}\n\n{traceback.format_exc()}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Final fallback error handling
        st.error("❌ Application failed to start. Please contact system administrator.")
        if logger:
            logger.critical(f"Application startup failed: {str(e)}")
        else:
            print(f"CRITICAL: Application startup failed: {str(e)}")