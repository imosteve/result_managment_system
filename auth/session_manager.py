# auth/session_manager.py  — FINAL VERSION
"""
Session management — handles two user types:

  platform_superadmin
    - Lives in master.db, not in any school DB
    - school_code / school_name / school_db_path are all None
    - Cookie 'school_code' is stored as empty string

  School users  (superadmin | admin | class_teacher | subject_teacher)
    - Live in a school's own SQLite DB
    - school_code, school_name, school_db_path set from school_info
    - Cookie 'school_code' stores the school code for session restore

restore_from_cookies() uses active_only=True for school users so that
deactivating a school kicks out all current cookie-session holders on
their next page load.
"""

import streamlit as st
import logging
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class SessionManager:
    """Handles user session management — multi-tenant, two-tier version"""

    # ── Create Session ────────────────────────────────────────────────────

    @staticmethod
    def create_session(
        user: Dict[str, Any],
        cookies,
        school_info: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Create a new user session after successful login.

        Args:
            user:        {id, username, role, email}
            cookies:     Streamlit EncryptedCookieManager
            school_info: School record from master_database.
                         Pass None for platform superadmins.

        Returns:
            True if session created successfully
        """
        try:
            # ── Auth ──────────────────────────────────────────────────────
            st.session_state.authenticated = True
            st.session_state.user_id       = user["id"]
            st.session_state.role          = user.get("role")
            st.session_state.username      = user["username"]
            st.session_state.login_time    = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            if "last_activity" not in st.session_state:
                st.session_state.last_activity = datetime.now()

            # ── School context ────────────────────────────────────────────
            if school_info:
                from master_database import get_school_db_path
                st.session_state.school_code    = school_info["school_code"]
                st.session_state.school_name    = school_info["school_name"]
                st.session_state.school_address = school_info["address"]
                st.session_state.school_db_path = get_school_db_path(
                    school_info["school_code"]
                )
            else:
                # Platform superadmin — no school context
                st.session_state.school_code    = None
                st.session_state.school_name    = None
                st.session_state.school_address = None
                st.session_state.school_db_path = None

            # ── Cookies ───────────────────────────────────────────────────
            cookies["authenticated"] = "true"
            cookies["user_id"]       = str(user["id"])
            cookies["role"]          = str(user.get("role") or "")
            cookies["username"]      = user["username"]
            cookies["login_time"]    = st.session_state.login_time
            cookies["last_activity"] = st.session_state.last_activity.isoformat()
            cookies["school_code"]   = st.session_state.school_code or ""
            cookies.save()

            logger.info(
                f"Session created — user: {user['username']} "
                f"| role: {user.get('role') or 'teacher'} "
                f"| school: {st.session_state.school_code or 'platform'}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Error creating session for '{user.get('username')}': {e}"
            )
            return False

    # ── Save Assignment ───────────────────────────────────────────────────

    @staticmethod
    def save_assignment(assignment_data: Dict[str, Any], cookies) -> bool:
        """Save a teacher's assignment selection to session and cookies"""
        try:
            subject_name    = assignment_data.get("subject_name") or ""
            assignment_type = assignment_data.get("assignment_type", "class_teacher")

            st.session_state.assignment = {
                "class_name":      assignment_data["class_name"],
                "term":            assignment_data["term"],
                "session":         assignment_data["session"],
                "subject_name":    subject_name,
                "assignment_type": assignment_type,
            }
            st.session_state.role = assignment_type

            cookies["assignment_class"]   = str(assignment_data["class_name"])
            cookies["assignment_term"]    = str(assignment_data["term"])
            cookies["assignment_session"] = str(assignment_data["session"])
            cookies["assignment_subject"] = subject_name
            cookies["assignment_type"]    = assignment_type
            cookies["role"]               = assignment_type
            cookies["last_activity"]      = st.session_state.last_activity.isoformat()

            logger.info(
                f"Assignment saved — {st.session_state.get('username')} "
                f"→ {assignment_data['class_name']} ({assignment_type})"
            )
            return True

        except Exception as e:
            logger.error(f"Error saving assignment: {e}")
            return False

    # ── Clear Session ─────────────────────────────────────────────────────

    @staticmethod
    def clear_session(cookies) -> bool:
        """Clear session state and cookies on logout"""
        try:
            if cookies:
                for key in [
                    "authenticated", "user_id", "role", "username",
                    "login_time", "last_activity", "school_code",
                    "assignment_class", "assignment_term",
                    "assignment_session", "assignment_subject",
                    "assignment_type",
                ]:
                    cookies[key] = ""
                cookies.save()
                SessionManager._clear_browser_storage()

            for key in [
                "authenticated", "user_id", "role", "username",
                "login_time", "last_activity", "assignment",
                "assignment_just_selected", "session_id",
                "school_code", "school_name", "school_address", "school_db_path",
            ]:
                st.session_state.pop(key, None)

            st.query_params.clear()
            logger.info("Session cleared")
            return True

        except Exception as e:
            logger.error(f"Error clearing session: {e}")
            return False

    # ── Restore from Cookies ──────────────────────────────────────────────

    @staticmethod
    def restore_from_cookies(cookies) -> bool:
        """
        Rebuild session state from cookies on every page reload.

        Platform superadmin:
          - school_code cookie is empty string → no school lookup
          - Session restored with school_* keys = None

        School users:
          - school_code cookie contains the school code
          - active_only=True enforces immediate effect of deactivation
          - Returns False if school is inactive → user hits login form

        Returns:
            True if session restored successfully, False otherwise
        """
        try:
            if (cookies.get("authenticated") != "true" or
                    not cookies.get("user_id")):
                return False

            # ── Auth ──────────────────────────────────────────────────────
            st.session_state.authenticated = True
            st.session_state.user_id       = int(cookies["user_id"])
            role = cookies.get("role", "")
            st.session_state.role          = role if role else None
            st.session_state.username      = cookies.get("username", "")
            st.session_state.login_time    = cookies.get("login_time", "")

            last_activity_str = cookies.get("last_activity")
            st.session_state.last_activity = (
                datetime.fromisoformat(last_activity_str)
                if last_activity_str else datetime.now()
            )

            # ── School context ────────────────────────────────────────────
            school_code = cookies.get("school_code", "")

            if school_code:
                # School user — verify school is still active
                from master_database import get_school_by_code, get_school_db_path

                school_info = get_school_by_code(school_code, active_only=True)
                if school_info is None:
                    logger.warning(
                        f"restore_from_cookies: school '{school_code}' "
                        "not found or inactive — rejecting session"
                    )
                    return False

                st.session_state.school_code    = school_code
                st.session_state.school_name    = school_info["school_name"]
                st.session_state.school_address = school_info["address"]
                st.session_state.school_db_path = get_school_db_path(school_code)

            else:
                # Platform superadmin or legacy — no school context
                st.session_state.school_code    = None
                st.session_state.school_name    = None
                st.session_state.school_address = None
                st.session_state.school_db_path = None

            # ── Assignment (teachers only) ─────────────────────────────────
            if (cookies.get("assignment_class") and
                    cookies.get("assignment_term") and
                    cookies.get("assignment_session")):
                st.session_state.assignment = {
                    "class_name":      cookies["assignment_class"],
                    "term":            cookies["assignment_term"],
                    "session":         cookies["assignment_session"],
                    "subject_name":    cookies.get("assignment_subject", ""),
                    "assignment_type": cookies.get("assignment_type",
                                                   "class_teacher"),
                }
                if st.session_state.role not in (
                    "admin", "superadmin", "platform_superadmin"
                ):
                    st.session_state.role = cookies.get(
                        "assignment_type", "class_teacher"
                    )

            logger.info(
                f"Session restored — {st.session_state.username} "
                f"(role: {st.session_state.role or 'teacher'}) "
                f"@ school: {school_code or 'platform'}"
            )
            return True

        except Exception as e:
            logger.error(f"Error restoring session from cookies: {e}")
            return False

    # ── Browser storage cleanup ───────────────────────────────────────────

    @staticmethod
    def _clear_browser_storage():
        """Force-expire cookies and clear local/session storage in the browser"""
        names = [
            "authenticated", "user_id", "role", "username", "login_time",
            "last_activity", "school_code", "assignment_class",
            "assignment_term", "assignment_session", "assignment_subject",
            "assignment_type",
        ]
        parts = [
            f'document.cookie="{n}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; '
            f'path=/; SameSite=Lax";'
            for n in names
        ]
        parts += ["localStorage.clear();", "sessionStorage.clear();"]
        st.markdown(f"<script>{''.join(parts)}</script>", unsafe_allow_html=True)

    # ── Utility ───────────────────────────────────────────────────────────

    @staticmethod
    def is_authenticated() -> bool:
        return st.session_state.get("authenticated", False)

    @staticmethod
    def get_current_user() -> Optional[Dict[str, Any]]:
        if not SessionManager.is_authenticated():
            return None
        return {
            "user_id":     st.session_state.get("user_id"),
            "username":    st.session_state.get("username"),
            "role":        st.session_state.get("role"),
            "login_time":  st.session_state.get("login_time"),
            "assignment":  st.session_state.get("assignment"),
            "school_code": st.session_state.get("school_code"),
            "school_name": st.session_state.get("school_name"),
            "school_address": st.session_state.get("school_address"),
        }

    @staticmethod
    def update_activity():
        if SessionManager.is_authenticated():
            st.session_state.last_activity = datetime.now()