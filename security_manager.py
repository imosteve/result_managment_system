# security_manager.py  — MULTI-TENANT VERSION
"""
Changes from single-tenant version:
  - force_logout() now also clears school_code, school_name,
    school_db_path from session state
  - Session timeout log message includes school_code for easier debugging
  - Everything else is identical
"""

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
        """Inject security JS — only for authenticated users, only on desktop"""
        if not st.session_state.get("authenticated", False):
            return

        if not (
            SECURITY_CONFIG.get("disable_right_click", False) or
            SECURITY_CONFIG.get("disable_dev_tools", False)
        ):
            return

        st.markdown("""
        <script>
        const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i
                         .test(navigator.userAgent);
        if (!isMobile) {
            document.addEventListener('contextmenu', e => e.preventDefault());
            document.addEventListener('keydown', e => {
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
    def check_session_timeout() -> bool:
        """
        Check session timeout with mobile-aware threshold.
        Returns True if session is still valid, False if it has expired.
        """
        if not st.session_state.get("authenticated"):
            return True

        if "last_activity" in st.session_state:
            time_diff = datetime.now() - st.session_state.last_activity
            # Mobile gets the full 2-hour timeout; desktop uses auth.config value
            timeout_seconds = 7200 if _is_mobile_device() else SESSION_TIMEOUT

            if time_diff.total_seconds() > timeout_seconds:
                logger.warning(
                    f"Session timeout — user: {st.session_state.get('username')} "
                    f"| school: {st.session_state.get('school_code', 'N/A')}"
                )
                st.warning("Session expired. You have been logged out.")
                time.sleep(1)
                logout()
                return False

        return True

    @staticmethod
    def force_logout(reason: str = "Security logout"):
        """
        Force-logout a user for security reasons.

        Clears all session state including multi-tenant school context keys.
        """
        logger.info(
            f"Force logout: {reason} — user: {st.session_state.get('username')} "
            f"| school: {st.session_state.get('school_code', 'N/A')}"
        )

        # Blank the authenticated cookie so the cookie restore path
        # doesn't re-admit the user on the next page load
        if "cookies" in st.session_state:
            try:
                cookies = st.session_state.cookies
                cookies["authenticated"] = "false"
                cookies.save()
            except Exception as e:
                logger.warning(f"Could not clear auth cookie during force logout: {e}")

        # Wipe the entire session state
        for key in list(st.session_state.keys()):
            del st.session_state[key]

        st.error(f"🔒 {reason}. Please log in again.")
        st.rerun()


# ── Module-level helper ───────────────────────────────────────────────────────

def _is_mobile_device() -> bool:
    """Return True if the current session is on a mobile device"""
    return st.session_state.get("is_mobile", False)