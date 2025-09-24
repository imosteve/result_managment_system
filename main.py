# main.py - Refactored for Production
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

def handle_navigation(app: ApplicationManager, options: dict):
    """Handle navigation logic with error handling"""
    option_keys = list(options.keys())
    if not option_keys:
        st.error("❌ No navigation options available for your role.")
        return

    # Handle URL parameters
    param_page = st.query_params.get("page", None)
    if param_page in option_keys:
        current_page = param_page
    else:
        current_page = option_keys[0]

    st.sidebar.header("Navigate to:")
    # Navigation selectbox
    choice = st.sidebar.selectbox(
        "🧭 Navigate to:",
        option_keys,
        index=option_keys.index(current_page),
        label_visibility = "collapsed",
    )

    # Update URL parameters if choice changed
    if choice != st.query_params.get("page"):
        st.query_params["page"] = choice
        st.rerun()

    # Execute selected function
    try:
        logger.info(f"User {st.session_state.get('username')} accessed {choice}")
        options[choice]()
    except Exception as e:
        logger.error(f"Error in {choice}: {str(e)}\n{traceback.format_exc()}")
        st.error(f"❌ Error loading {choice}. Please try again or contact support.")
        
        # Show error details to admins
        if st.session_state.get('role') == 'admin':
            with st.expander("🔧 Error Details (Admin Only)"):
                st.code(str(e))

def render_logout_button():
    """Render logout button with confirmation"""
    with st.sidebar:
        # st.markdown("---")
        if st.button("🚪 Logout", type="secondary", use_container_width=True):
            # Clear query parameters
            st.query_params.clear()
            logout()
            st.rerun()

def validate_session_data(role: str, username: str, user_id: int) -> bool:
    """Validate user session data"""
    if not all([role, username, user_id]):
        logger.error(f"Invalid session data: role={role}, username={username}, user_id={user_id}")
        SecurityManager.force_logout("Invalid session data")
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
        
        # Render main application
        st.markdown('<div class="main-content">', unsafe_allow_html=True)
        
        # Render header
        app.render_header()
        
        # Render user info
        app.render_user_info(role, username)
        
        # Render logout button
        render_logout_button()
        
        # Get navigation options based on role
        options = app.get_navigation_options(role)
        
        # Handle navigation
        handle_navigation(app, options)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Update user activity timestamp
        st.session_state.last_activity = datetime.now()
        
    except Exception as e:
        logger.error(f"Error in authenticated app: {str(e)}\n{traceback.format_exc()}")
        st.error("❌ An error occurred. Please refresh the page or contact support.")
        
        # Show error details to admins
        if st.session_state.get('role') == 'admin':
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
        if st.session_state.get('role') == 'admin':
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