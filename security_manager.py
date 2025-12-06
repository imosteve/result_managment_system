# security_manager.py - CLEANED VERSION
import streamlit as st
import logging
import time
from datetime import datetime
from config import APP_CONFIG, SECURITY_CONFIG
from auth.logout import logout
from auth.config import SESSION_TIMEOUT

logger = logging.getLogger(__name__)

class SecurityManager:
    """Handle security-related operations"""
    
    @staticmethod
    def initialize_security_headers():
        """Initialize security headers - ONLY FOR AUTHENTICATED USERS"""
        # Only load security scripts after login, not on login page
        if not st.session_state.get("authenticated", False):
            return
            
        if not SECURITY_CONFIG.get('disable_right_click', False) and not SECURITY_CONFIG.get('disable_dev_tools', False):
            return
            
        st.markdown("""
        <script>
        // Check if mobile device
        const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
        
        if (!isMobile) {
            // Only apply desktop security restrictions
            document.addEventListener('contextmenu', function(e) {
                e.preventDefault();
            });
            
            document.addEventListener('keydown', function(e) {
                if (e.keyCode === 123 || 
                    (e.ctrlKey && e.shiftKey && e.keyCode === 73) || 
                    (e.ctrlKey && e.keyCode === 85)) {
                    e.preventDefault();
                }
            });
        }
        </script>
        """, unsafe_allow_html=True)

    @staticmethod
    def check_session_timeout():
        """Check session timeout with mobile-friendly settings"""
        if not st.session_state.get('authenticated'):
            return True
            
        if 'last_activity' in st.session_state:
            time_diff = datetime.now() - st.session_state.last_activity
            # Longer timeout for mobile (2 hours vs 1 hour)
            timeout_seconds = 7200 if is_mobile_device() else SESSION_TIMEOUT
            print(f"time_diff = {time_diff}")
            print(f"Last activity time: {st.session_state.last_activity}")
            print(f"Date time now: {datetime.now()}")
            print(f"SESSION_TIMEOUT: {SESSION_TIMEOUT}")
            print("Expired:", time_diff.total_seconds() > timeout_seconds)

            if time_diff.total_seconds() > timeout_seconds:
                logger.warning(f"Session timeout for user {st.session_state.get('username')}")
                st.warning("Session expired. You have been logged out.")
                time.sleep(2)
                logout()
                return False

        # st.session_state.last_activity = datetime.now()
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

def is_mobile_device():
    """Simple mobile detection helper"""
    return st.session_state.get('is_mobile', False)