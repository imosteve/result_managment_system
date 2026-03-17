# database/classes.py
"""
Class management — session-independent class definitions and
per-session enrollment (class_sessions).

NOTE: class_teacher assignment is handled via teacher_assignments,
NOT a column on the classes table.
"""

import sqlite3
import logging
from .connection import get_connection

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════
# Permanent class registry
# ═════════════════════════════════════════════════════════════════

def create_class(class_name: str, description: str = None) -> bool:
    """
    Add a new permanent class definition.
    class_teacher is NOT stored here — use teacher_assignments.

    Returns True on success, False if name already exists.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO classes (class_name, description) VALUES (?, ?)",
            (class_name.strip(), description)
        )
        conn.commit()
        logger.info(f"Class '{class_name}' created")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Class '{class_name}' already exists")
        return False
    except Exception as e:
        logger.error(f"Error creating class: {e}")
        return False
    finally:
        conn.close()


def get_all_classes() -> list:
    """
    Return all permanent class definitions ordered by name.
    Returns list of dicts: {id, class_name, description, created_at}
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, class_name, description, created_at
        FROM   classes
        ORDER  BY class_name
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_class(class_name: str) -> dict | None:
    """Return a single class definition or None."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, class_name, description, created_at FROM classes WHERE class_name = ?",
        (class_name,)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def update_class(class_name: str, new_name: str = None,
                 description: str = None) -> bool:
    """
    Update a class definition.
    Renaming cascades to class_sessions, subjects, class_session_students
    via ON UPDATE CASCADE.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if new_name and new_name.strip() != class_name:
            cursor.execute(
                "UPDATE classes SET class_name = ? WHERE class_name = ?",
                (new_name.strip(), class_name)
            )
            class_name = new_name.strip()
        if description is not None:
            cursor.execute(
                "UPDATE classes SET description = ? WHERE class_name = ?",
                (description, class_name)
            )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Rename failed — '{new_name}' already exists")
        return False
    except Exception as e:
        logger.error(f"Error updating class: {e}")
        return False
    finally:
        conn.close()


def delete_class(class_name: str) -> tuple:
    """
    Delete a class. Refuses with a user-facing reason if session
    enrollments exist.
    Returns (True, "") or (False, reason_string).
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT COUNT(*) FROM class_sessions WHERE class_name = ?",
            (class_name,)
        )
        if cursor.fetchone()[0] > 0:
            return (
                False,
                f"Cannot delete '{class_name}': it has active session "
                "enrollments. Remove those first."
            )
        cursor.execute("DELETE FROM classes WHERE class_name = ?", (class_name,))
        conn.commit()
        return True, ""
    except Exception as e:
        logger.error(f"Error deleting class: {e}")
        return False, str(e)
    finally:
        conn.close()


# ═════════════════════════════════════════════════════════════════
# Session enrollment (class_sessions)
# ═════════════════════════════════════════════════════════════════

def open_class_for_session(class_name: str, session: str) -> bool:
    """
    Open a class for an academic session (creates class_sessions row).
    Idempotent — safe to call even if already open (INSERT OR IGNORE).
    Both class_name and session must exist in their parent tables.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO class_sessions (class_name, session)
            VALUES (?, ?)
        """, (class_name, session))
        conn.commit()
        logger.info(f"'{class_name}' opened for session '{session}'")
        return True
    except sqlite3.IntegrityError as e:
        logger.error(f"open_class_for_session FK error: {e}")
        return False
    except Exception as e:
        logger.error(f"Error opening class for session: {e}")
        return False
    finally:
        conn.close()


def get_class_session_id(class_name: str, session: str) -> int | None:
    """Return class_sessions.id for (class_name, session), or None."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM class_sessions WHERE class_name = ? AND session = ?",
        (class_name, session)
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def get_classes_for_session(session: str) -> list:
    """
    Return all classes open in a session, with enrollment counts.
    Returns list of dicts:
        {class_session_id, class_name, session, is_active,
         description, student_count}
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            cs.id           AS class_session_id,
            cs.class_name,
            cs.session,
            cs.is_active,
            c.description,
            COUNT(DISTINCT css.student_name) AS student_count
        FROM  class_sessions cs
        JOIN  classes c ON c.class_name = cs.class_name
        LEFT JOIN class_session_students css ON css.class_session_id = cs.id
        WHERE cs.session = ?
        GROUP BY cs.id
        ORDER BY cs.class_name
    """, (session,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_classes_for_teacher(teacher_username: str, session: str) -> list:
    """
    Return classes assigned to a teacher via teacher_assignments.
    (class_teacher is NOT a column on the classes table.)
    Returns list of dicts:
        {class_session_id, class_name, session, is_active,
         student_count, assignment_type}
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            cs.id                   AS class_session_id,
            cs.class_name,
            cs.session,
            cs.is_active,
            COUNT(DISTINCT css.id)  AS student_count,
            ta.assignment_type
        FROM  teacher_assignments ta
        JOIN  users u              ON u.id  = ta.user_id
        JOIN  class_sessions cs    ON cs.id = ta.class_session_id
        LEFT JOIN class_session_students css ON css.class_session_id = cs.id
        WHERE u.username = ?
          AND ta.session  = ?
        GROUP BY cs.id, ta.assignment_type
        ORDER BY cs.class_name
    """, (teacher_username, session))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def close_class_for_session(class_name: str, session: str) -> bool:
    """Soft-close a class_session (data preserved, is_active → 0)."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE class_sessions SET is_active = 0
            WHERE class_name = ? AND session = ?
        """, (class_name, session))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error closing class session: {e}")
        return False
    finally:
        conn.close()

def reopen_class_for_session(class_name: str, session: str) -> bool:
    """Re-activate a soft-closed class_session (is_active → 1)."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE class_sessions SET is_active = 1
            WHERE  class_name = ? AND session = ?
        """, (class_name, session))
        conn.commit()
        reopened = cursor.rowcount > 0
        if reopened:
            logger.info(f"'{class_name}' re-opened for session '{session}'")
        return reopened
    except Exception as e:
        logger.error(f"Error re-opening class session: {e}")
        return False
    finally:
        conn.close()


def delete_class_session(class_name: str, session: str) -> tuple:
    """
    Permanently remove a class from a session.

    CASCADE: deletes all class_session_students rows for this session,
    which in turn CASCADE-deletes all scores, comments, psychomotor
    ratings, and subject selections for those enrollments.

    Use this when you need to:
      - Undo accidentally opening a class for the wrong session
      - Fully remove a session's data for a class
      - Allow the class itself to be deleted (delete_class() refuses
        while class_sessions rows exist)

    Returns (True, "") or (False, reason_string).
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Count enrollments so we can warn the caller
        cursor.execute("""
            SELECT COUNT(*) FROM class_session_students css
            JOIN   class_sessions cs ON cs.id = css.class_session_id
            WHERE  cs.class_name = ? AND cs.session = ?
        """, (class_name, session))
        enrollment_count = cursor.fetchone()[0]

        cursor.execute("""
            DELETE FROM class_sessions
            WHERE  class_name = ? AND session = ?
        """, (class_name, session))
        conn.commit()

        if cursor.rowcount == 0:
            return False, f"No session record found for '{class_name}' / '{session}'."

        logger.warning(
            f"Class session deleted: '{class_name}' / '{session}' "
            f"({enrollment_count} enrollment(s) removed by CASCADE)"
        )
        return True, f"Removed '{class_name}' from {session}. {enrollment_count} enrollment(s) erased."
    except Exception as e:
        logger.error(f"Error deleting class session: {e}")
        return False, str(e)
    finally:
        conn.close()