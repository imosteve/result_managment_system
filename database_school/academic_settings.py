# database/academic_settings.py
"""
Academic settings — controls the active session and term school-wide.

This is the central piece of the new session model:
  • Admins call set_active_term() to switch the current context.
  • All teacher-facing views call get_active_term() to know which
    session/term to display and accept scores for.
  • Teachers NEVER select a session/term themselves — they always
    work in the currently active context.

The academic_settings table has exactly one row (id=1), enforced
by a CHECK constraint in schema.py.
"""

import logging
from .connection import get_connection

logger = logging.getLogger(__name__)

VALID_TERMS = ("First", "Second", "Third")


# ═════════════════════════════════════════════════════════════════
# Read
# ═════════════════════════════════════════════════════════════════

def get_active_term() -> dict:
    """
    Return the current active session and term.

    Returns:
        dict with keys: current_session, current_term, updated_at, updated_by
        Returns defaults if the settings row has never been configured.
    """
    conn = get_connection()
    conn.row_factory = __import__("sqlite3").Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM academic_settings WHERE id = 1")
    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    # Should never happen (seeded in schema.py), but safe fallback
    return {
        "current_session": "",
        "current_term":    "First",
        "updated_at":      None,
        "updated_by":      None,
    }


def get_active_session() -> str:
    """Convenience — returns just the session string."""
    return get_active_term()["current_session"]


def get_active_term_name() -> str:
    """Convenience — returns just the term string."""
    return get_active_term()["current_term"]


def is_configured() -> bool:
    """Return True if a session has been set (not blank)."""
    return bool(get_active_term()["current_session"])


# ═════════════════════════════════════════════════════════════════
# Write (admin only)
# ═════════════════════════════════════════════════════════════════

def set_active_term(session: str, term: str, performed_by: str = "") -> bool:
    """
    Set the school-wide active session and term.

    Args:
        session:      Academic year string, e.g. "2024/2025".
                      Must exist in the sessions table.
        term:         "First", "Second", or "Third"
        performed_by: Username making the change (for audit trail)

    Returns:
        True on success, False if session not found or invalid term.
    """
    if term not in VALID_TERMS:
        logger.error(f"Invalid term '{term}'. Must be one of {VALID_TERMS}")
        return False

    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Verify session exists
        cursor.execute(
            "SELECT id FROM sessions WHERE session = ?", (session,)
        )
        if not cursor.fetchone():
            logger.error(f"Session '{session}' not found in sessions table")
            return False

        cursor.execute("""
            INSERT INTO academic_settings (id, current_session, current_term,
                                           updated_at, updated_by)
            VALUES (1, ?, ?, CURRENT_TIMESTAMP, ?)
            ON CONFLICT(id) DO UPDATE SET
                current_session = excluded.current_session,
                current_term    = excluded.current_term,
                updated_at      = excluded.updated_at,
                updated_by      = excluded.updated_by
        """, (session, term, performed_by))
        conn.commit()
        logger.info(
            f"Active term set to {session} / {term} by {performed_by}"
        )
        return True
    except Exception as e:
        logger.error(f"Error setting active term: {e}")
        return False
    finally:
        conn.close()


# ═════════════════════════════════════════════════════════════════
# Sessions CRUD
# ═════════════════════════════════════════════════════════════════

def get_all_sessions() -> list:
    """
    Return all academic sessions, newest first.

    Returns:
        list of dicts: {id, session, is_active, created_at}
    """
    conn = get_connection()
    conn.row_factory = __import__("sqlite3").Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, session, is_active, created_at
        FROM   sessions
        ORDER  BY session DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_session(session: str, performed_by: str = "") -> bool:
    """
    Create a new academic session.

    Args:
        session: e.g. "2025/2026"
        performed_by: username

    Returns:
        True on success, False if duplicate.
    """
    import sqlite3
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO sessions (session) VALUES (?)", (session,)
        )
        conn.commit()
        logger.info(f"Session '{session}' created by {performed_by}")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Session '{session}' already exists")
        return False
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        return False
    finally:
        conn.close()


def delete_session(session: str, performed_by: str = "") -> tuple:
    """
    Delete an academic session.

    Refuses if:
      - The session is currently active (academic_settings)
      - Any class_sessions reference it (enrolled students exist)

    Returns:
        (True, "") on success
        (False, reason_string) on refusal
    """
    active = get_active_term()
    if active["current_session"] == session:
        return False, "Cannot delete the currently active session."

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT COUNT(*) FROM class_sessions WHERE session = ?", (session,)
        )
        count = cursor.fetchone()[0]
        if count > 0:
            return (
                False,
                f"Cannot delete: {count} class enrollment(s) exist for this session. "
                "Archive or transfer data first.",
            )

        cursor.execute("DELETE FROM sessions WHERE session = ?", (session,))
        conn.commit()
        logger.info(f"Session '{session}' deleted by {performed_by}")
        return True, ""
    except Exception as e:
        logger.error(f"Error deleting session: {e}")
        return False, str(e)
    finally:
        conn.close()
