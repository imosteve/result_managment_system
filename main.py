# main.py - Refactored for Production with Assignment Navigation Fix
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

def get_first_app_section(options: dict, role: str) -> str:
    """
    Get the first appropriate app section after assignment selection
    
    Args:
        options: Navigation options dictionary
        role: User role
        
    Returns:
        First appropriate section key
    """
    option_keys = list(options.keys())
    
    # Skip Dashboard, Admin Panel, and Change Assignment for initial navigation
    skip_keys = ["🏠 Dashboard", "👥 Admin Panel", "🔄 Change Assignment"]
    
    for key in option_keys:
        if key not in skip_keys:
            return key
    
    # If all keys are in skip list, return first available
    return option_keys[0] if option_keys else None

def handle_post_assignment_navigation(app: ApplicationManager, role: str, options: dict) -> str:
    """
    Handle navigation after assignment selection
    
    Args:
        app: Application manager instance
        role: User role
        options: Navigation options
        
    Returns:
        The page to navigate to
    """
    # Check if assignment was just selected
    if st.session_state.get('assignment_just_selected'):
        # Clear the flag
        del st.session_state['assignment_just_selected']
        
        # Get the first appropriate section
        first_section = get_first_app_section(options, role)
        
        if first_section:
            logger.info(f"Navigating to first section after assignment: {first_section}")
            # Set query parameter to navigate to this page
            st.query_params["page"] = first_section
            return first_section
    
    return None

def handle_navigation(app: ApplicationManager, options: dict, role: str):
    """Handle navigation logic with clickable menu buttons"""
    option_keys = list(options.keys())
    if not option_keys:
        st.error("❌ No navigation options available for your role.")
        return

    # Handle post-assignment navigation
    post_assignment_page = handle_post_assignment_navigation(app, role, options)
    if post_assignment_page:
        current_page = post_assignment_page
    else:
        # Handle URL parameters
        param_page = st.query_params.get("page", None)
        if param_page in option_keys:
            current_page = param_page
        else:
            current_page = option_keys[0]

    # Navigation with clickable buttons
    st.markdown("""
        <style>
            .sidebar-title {
                font-family: 'Arial', sans-serif;
                # background: #0a84ff22;
                padding: 6px 10px;
                border-radius: 6px;
                font-size: 19px;
                # font-weight: 10;
            }
        </style>
    """, unsafe_allow_html=True)

    st.sidebar.markdown("<div class='sidebar-title'>NAVIGATION</div>", unsafe_allow_html=True)

    for page in option_keys:
        # Check if this is the current page
        is_current = (page == current_page)
        
        # Create button with different styling for current page
        if st.sidebar.button(
            page,
            key=f"nav_{page}",
            # width="stretch",
            type="secondary" if is_current else "tertiary",
        ):
            # Update URL and navigate
            st.query_params["page"] = page
            st.rerun()

    # Execute selected function
    try:
        logger.info(f"User {st.session_state.get('username')} accessed {current_page}")
        options[current_page]()
    except Exception as e:
        logger.error(f"Error in {current_page}: {str(e)}\n{traceback.format_exc()}")
        st.error(f"❌ Error loading {current_page}. Please try again or contact support.")
        
        # Show error details to admins
        if st.session_state.get('role') in ['superadmin', 'admin']:
            with st.expander("🔧 Error Details (Admin Only)"):
                st.code(str(e))

def render_logout_button():
    """Render logout button"""
    with st.sidebar:
        if st.button("Logout", type="primary", use_container_width=True):
            # Clear query parameters
            st.query_params.clear()
            logout()

def validate_session_data(role: str, username: str, user_id: int) -> bool:
    """Validate user session data - UPDATED to allow None role for teachers"""
    # Check username and user_id
    if not username or not user_id:
        logger.error(f"Invalid session data: role={role}, username={username}, user_id={user_id}")
        SecurityManager.force_logout("Invalid session data")
        return False
    
    # Role can be None for teachers who haven't selected an assignment yet
    # This is valid and expected behavior
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

def render_authenticated_app(app: ApplicationManager):
    """Render the main authenticated application"""
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
        
        # Render user info
        app.render_user_info(role, username)
        
        # Get navigation options based on role
        options = app.get_navigation_options(role)
        
        # Handle navigation (including post-assignment redirect)
        handle_navigation(app, options, role)
        
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
        
        # Handle authentication - this will either show login form or proceed if authenticated
        login(cookies)
        
        # If we reach this point, user is authenticated
        # Check if user is actually authenticated (login function should handle this)
        if st.session_state.get("authenticated"):
            render_authenticated_app(app)
        else:
            # This should not happen if login function works correctly
            logger.warning("User reached main app without authentication")
            st.stop()
        
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
            # If logger is not available, at least print to console
            print(f"CRITICAL: Application startup failed: {str(e)}")