# auth/validators.py  — POST-MIGRATION VERSION
"""
Two credential validation paths:

  validate_platform_admin_credentials(platform_admin_record, password)
    → checks password against the master.db platform_admins record
    → called when login.py has already confirmed the email is a platform admin

  validate_school_user_credentials(email, password, school_info)
    → opens the school's SQLite DB directly (session state not set yet)
    → queries users by email — role is read directly from users.role
    → called for all school users (superadmin, admin, teachers)

  validate_session_cookies(cookies)
    → restores full session from cookies on every page reload
    → re-validates school active status for school users
    → platform admins have no school_code cookie — handled separately
"""

import streamlit as st
import sqlite3
import os
import logging
from typing import Optional, Dict, Any
from .session_manager import SessionManager

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Platform admin credential check
# ─────────────────────────────────────────────

def validate_platform_admin_credentials(
    platform_admin: Dict[str, Any],
    password: str,
) -> bool:
    """
    Validate password for a platform admin.

    Args:
        platform_admin: Record from master_database.get_platform_admin_by_email()
        password:       Plain-text password from the login form

    Returns:
        True if password matches, False otherwise
    """
    if not platform_admin or not password:
        return False

    # Plain text for now — swap for bcrypt in production
    if platform_admin["password"] != password:
        logger.warning(
            f"Invalid password for platform admin '{platform_admin['email']}'"
        )
        return False

    logger.info(f"Platform admin credentials validated: '{platform_admin['email']}'")
    return True


# ─────────────────────────────────────────────
# School user credential check
# ─────────────────────────────────────────────

def validate_school_user_credentials(
    email:       str,
    password:    str,
    school_info: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Validate email + password against a specific school's database.

    Opens the school DB directly via an explicit path because
    st.session_state['school_db_path'] has not been set yet at this point
    (that happens in SessionManager.create_session() after this returns).

    Args:
        email:       Full email address (already lowercased)
        password:    Plain-text password
        school_info: Active school record from master_database

    Returns:
        User data dict {id, username, role, email} on success, None on failure
    """
    from database_master import get_school_db_path

    db_path = get_school_db_path(school_info["school_code"])
    user_record = _get_user_by_email_direct(email, db_path)

    if user_record is None:
        logger.warning(
            f"Login failed — '{email}' not found in "
            f"school '{school_info['school_code']}'"
        )
        return None

    if user_record[2] != password:   # index 2 = password column
        logger.warning(
            f"Login failed — wrong password for '{email}' "
            f"in school '{school_info['school_code']}'"
        )
        return None

    user_data = {
        "id":       user_record[0],
        "username": user_record[1],
        # ── CHANGE: role now comes directly from users.role ──
        # values: 'superadmin' | 'admin' | 'teacher'
        "role":     user_record[3],
        "email":    user_record[4],
    }

    logger.info(
        f"School user credentials validated — '{email}' "
        f"(role: {user_data['role']}) "
        f"in school '{school_info['school_code']}'"
    )
    return user_data


# ─────────────────────────────────────────────
# Session cookie validation
# ─────────────────────────────────────────────

def validate_session_cookies(cookies) -> bool:
    """
    Validate and restore a full session from cookies on every page load.

    For school users:
      - Verifies the school is still ACTIVE (guards against deactivation
        while a user has a live cookie-based session)
      - If school is inactive, clears the session and shows an error

    For platform admins:
      - No school_code in cookie — session is restored as-is

    Returns:
        True if a valid session was restored, False otherwise
    """
    try:
        if cookies.get("authenticated") != "true":
            return False

        if not SessionManager.restore_from_cookies(cookies):
            return False

        # School users — re-validate school status
        school_code = st.session_state.get("school_code")
        role        = st.session_state.get("role")

        if school_code and role != "platform_superadmin":
            from database_master import get_school_by_code
            school = get_school_by_code(school_code, active_only=True)

            if school is None:
                logger.warning(
                    f"Session rejected — school '{school_code}' is "
                    "inactive or no longer exists"
                )
                SessionManager.clear_session(cookies)
                st.error(
                    "🔒 Your school account has been deactivated. "
                    "Please contact the platform administrator."
                )
                st.stop()
                return False

        logger.info(
            f"Session restored — {st.session_state.get('username')} "
            f"(role: {role or 'teacher'}) "
            f"@ school: {school_code or 'platform'}"
        )
        return True

    except Exception as e:
        logger.error(f"Error validating session cookies: {e}")
        return False


# ─────────────────────────────────────────────
# Internal helper
# ─────────────────────────────────────────────

def _get_user_by_email_direct(email: str, db_path: str) -> Optional[tuple]:
    """
    Query users by email using an explicit DB path.

    Bypasses get_connection()'s session-state resolution because
    session state is not populated yet at credential-check time.

    Returns:
        Tuple (id, username, password, role, email) or None
    """
    if not os.path.exists(db_path):
        logger.error(f"School database not found at: '{db_path}'")
        return None

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()
        # ── CHANGE: plain SELECT on users — no admin_users JOIN needed ──
        cursor.execute("""
            SELECT id, username, password, role, email
            FROM   users
            WHERE  LOWER(email) = LOWER(?)
        """, (email.strip(),))
        result = cursor.fetchone()
        conn.close()
        return tuple(result) if result else None
    except Exception as e:
        logger.error(f"Error querying '{db_path}' for email '{email}': {e}")
        return None