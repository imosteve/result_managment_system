# auth/login.py  — FINAL VERSION
"""
Login — email-only authentication with two-tier resolution:

  Tier 1 — Platform admin (master.db)
    Email is checked against platform_admins table first.
    If matched: authenticate against master.db, set role='platform_superadmin',
    NO school_db_path set. These users see only the Platform Admin panel.

  Tier 2 — School user (school DB)
    Email domain is resolved to a school via master.db schools table.
    If matched: authenticate against that school's SQLite database.
    school_db_path is set in session state — all subsequent DB calls
    route there automatically via database/connection.get_db_path().

Login is email-only. No username field, no school selector dropdown.
"""

import streamlit as st
import time
import logging
from main_utils import inject_login_css
from .config import MESSAGES, CSS_CLASSES
from .validators import validate_platform_admin_credentials, validate_school_user_credentials, validate_session_cookies
from .session_manager import SessionManager
from .assignment_selection import select_assignment
from database_school import get_user_assignments
from database_master import (
    create_master_tables,
    get_platform_admin_by_email,
    resolve_school_from_email,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Style helpers
# ─────────────────────────────────────────────

def _load_main_styles():
    try:
        inject_login_css("templates/main_styles.css")
    except Exception as e:
        logger.warning(f"Could not load main styles: {e}")


def _load_login_styles():
    try:
        inject_login_css("templates/login_styles.css")
    except Exception as e:
        logger.warning(f"Could not load login styles: {e}")


# ─────────────────────────────────────────────
# Login form
# ─────────────────────────────────────────────

def render_login_form() -> tuple[str, str, bool]:
    """Render the email + password login form"""
    st.markdown(
        f'<div class="{CSS_CLASSES["login_container"]}">',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<h1 class="{CSS_CLASSES["login_title"]}">🎓 Login</h1>',
        unsafe_allow_html=True,
    )

    with st.form("login_form", clear_on_submit=False):
        email = st.text_input(
            "Email Address",
            placeholder="you@yourschool.edu",
        )
        password = st.text_input(
            "Password",
            type="password",
            placeholder="Enter your password",
        )
        login_button = st.form_submit_button("Sign in", width="content")

    return email, password, login_button


# ─────────────────────────────────────────────
# Login attempt handler
# ─────────────────────────────────────────────

def handle_login_attempt(email: str, password: str, cookies) -> bool:
    """
    Process a login attempt.

    Resolution order:
      1. Basic input validation
      2. Check platform_admins table (master.db) — no school needed
      3. Resolve school from email domain — school users only
      4. Validate credentials against the school's database
      5. Create session (with or without school context)
    """
    # ── 1. Input validation ───────────────────────────────────────────────
    email = email.strip().lower()

    if not email:
        st.error("⚠️ Please enter your email address.")
        return False
    if "@" not in email:
        st.error("⚠️ Please enter a valid email address.")
        return False
    if not password or not password.strip():
        st.error("⚠️ Please enter your password.")
        return False
    if len(password) < 4:
        st.error("⚠️ Password must be at least 4 characters.")
        return False

    # ── 2. Platform admin check ───────────────────────────────────────────
    platform_admin = get_platform_admin_by_email(email)
    if platform_admin:
        return _handle_platform_admin_login(platform_admin, password, cookies)

    # ── 3. School resolution ──────────────────────────────────────────────
    school_info = resolve_school_from_email(email)
    if school_info is None:
        st.error(
            "❌ Your email domain is not registered on this platform, "
            "or your school account has been deactivated. "
            "Please contact your administrator."
        )
        return False

    # ── 4 & 5. School user credential check + session ────────────────────
    return _handle_school_user_login(email, password, school_info, cookies)


def _handle_platform_admin_login(
    platform_admin: dict, password: str, cookies
) -> bool:
    """Authenticate and create a session for a platform admin"""
    if not validate_platform_admin_credentials(platform_admin, password):
        st.error(MESSAGES["invalid_credentials"])
        return False

    user_data = {
        "id":       platform_admin["id"],
        "username": platform_admin["username"],
        "role":     "platform_superadmin",
        "email":    platform_admin["email"],
    }

    # No school_info — platform admins have no school context
    if not SessionManager.create_session(user_data, cookies, school_info=None):
        st.error("Failed to create session. Please try again.")
        return False

    logger.info(f"Platform admin '{platform_admin['email']}' logged in")
    st.success(MESSAGES["login_success"])
    time.sleep(1.0)
    st.session_state.login_successful = True
    st.rerun()
    return True


def _handle_school_user_login(
    email: str, password: str, school_info: dict, cookies
) -> bool:
    """Authenticate and create a session for a school user"""
    user_data = validate_school_user_credentials(email, password, school_info)

    if user_data is None:
        st.error(MESSAGES["invalid_credentials"])
        return False

    if not SessionManager.create_session(user_data, cookies, school_info=school_info):
        st.error("Failed to create session. Please try again.")
        return False

    st.success(MESSAGES["login_success"])
    time.sleep(1.0)
    st.session_state.login_successful = True
    st.rerun()
    return True


# ─────────────────────────────────────────────
# Post-login redirect helpers
# ─────────────────────────────────────────────

def _handle_admin_post_login():
    _load_main_styles()


def _handle_teacher_post_login(user_id: int):
    assignments = get_user_assignments(user_id)

    if not assignments:
        st.error(
            "⚠️ You don't have any class or subject assignments yet. "
            "Please contact your administrator."
        )
        if st.button("Logout"):
            from .logout import logout
            logout()
        st.stop()
        return

    if "assignment" not in st.session_state:
        _load_login_styles()
        select_assignment()
    else:
        _load_main_styles()


# ─────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────

def login(cookies):
    """
    Called from main.py on every page load.

    Handles:
      • Post-login redirect (assignment selection for teachers,
        platform admin panel for platform superadmins)
      • Session restore from cookies
      • First-time login form
    """
    try:
        create_master_tables()

        # ── Post-login redirect ───────────────────────────────────────────
        if st.session_state.get("login_successful"):
            del st.session_state["login_successful"]

            role    = st.session_state.get("role")
            user_id = st.session_state.get("user_id")

            # Platform admin — goes straight to app (Platform Admin panel in nav)
            if role == "platform_superadmin":
                _load_main_styles()
                return

            # School admin — straight to app
            if role in ("admin", "superadmin"):
                _handle_admin_post_login()
                return

            # Teacher — needs assignment selection
            _handle_teacher_post_login(user_id)
            return

        # ── Restore session from cookies ──────────────────────────────────
        if validate_session_cookies(cookies):
            role    = st.session_state.get("role")
            user_id = st.session_state.get("user_id")

            if role == "platform_superadmin":
                _load_main_styles()
                return

            if role in ("admin", "superadmin"):
                _load_main_styles()
                return

            if "assignment" not in st.session_state:
                assignments = get_user_assignments(user_id)
                if not assignments:
                    st.error("⚠️ You don't have any assignments yet.")
                    if st.button("🚪 Logout"):
                        from .logout import logout
                        logout()
                    st.stop()
                    return
                _load_login_styles()
                select_assignment()
                return
            else:
                _load_main_styles()
                return

        # ── Show login form ───────────────────────────────────────────────
        _load_login_styles()
        email, password, login_clicked = render_login_form()

        if login_clicked:
            handle_login_attempt(email, password, cookies)

        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

    except Exception as e:
        logger.error(f"Error in login(): {e}")
        st.error("An error occurred during authentication. Please refresh the page.")
        st.stop()