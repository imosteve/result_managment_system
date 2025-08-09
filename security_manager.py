# security_manager.py
import streamlit as st
import logging
from datetime import datetime
from config import APP_CONFIG, SECURITY_CONFIG

logger = logging.getLogger(__name__)

class SecurityManager:
    """Handle security-related operations"""
    
    @staticmethod
    def initialize_security_headers():
        """Initialize security headers"""
        if not SECURITY_CONFIG['disable_right_click'] and not SECURITY_CONFIG['disable_dev_tools']:
            return
            
        st.markdown("""
        <script>
        // Disable right-click context menu
        document.addEventListener('contextmenu', function(e) {
            e.preventDefault();
        });
        
        // Disable certain keyboard shortcuts
        document.addEventListener('keydown', function(e) {
            // Disable F12, Ctrl+Shift+I, Ctrl+U
            if (e.keyCode === 123 || 
                (e.ctrlKey && e.shiftKey && e.keyCode === 73) || 
                (e.ctrlKey && e.keyCode === 85)) {
                e.preventDefault();
            }
        });
        </script>
        """, unsafe_allow_html=True)

    @staticmethod
    def check_session_timeout():
        """Check if user session has timed out"""
        if not SECURITY_CONFIG['session_timeout_enabled']:
            return True
            
        if 'last_activity' in st.session_state:
            time_diff = datetime.now() - st.session_state.last_activity
            if time_diff.total_seconds() > APP_CONFIG['session_timeout']:
                logger.warning(f"Session timeout for user {st.session_state.get('username')}")
                SecurityManager.force_logout("Session expired due to inactivity")
                return False
        
        st.session_state.last_activity = datetime.now()
        return True

    @staticmethod
    def force_logout(reason: str = "Security logout"):
        """Force user logout for security reasons"""
        logger.info(f"Force logout: {reason}")
        if 'cookies' in st.session_state:
            cookies = st.session_state.cookies
            cookies['authenticated'] = 'false'
            cookies.save()
        
        # Clear session state
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        
        st.error(f"🔒 {reason}. Please log in again.")
        st.rerun()