# database/comments.py
"""
Comment management — adapted for the enrollment_id model.

The API surface is UNCHANGED from the old version — callers still pass
(student_name, class_name, term, session). This module resolves the
enrollment_id internally so existing app_sections code needs no changes.

Internal storage uses (enrollment_id, term) as the unique key, which
ensures comments from different sessions/terms never collide.
"""

import sqlite3
import logging
from .connection import get_connection
from .students import get_enrollment_id

logger = logging.getLogger(__name__)


def create_comment(student_name, class_name, term, session,
                   class_teacher_comment=None, head_teacher_comment=None,
                   head_teacher_comment_custom=0):
    """
    Create or update a comment for a student.

    Args:
        student_name, class_name, term, session — same as before
        class_teacher_comment: optional text
        head_teacher_comment:  optional text
        head_teacher_comment_custom: 1 if typed, 0 if from template

    Returns:
        bool: True on success
    """
    enrollment_id = get_enrollment_id(student_name, class_name, session)
    if enrollment_id is None:
        logger.error(
            f"create_comment: no enrollment for '{student_name}' "
            f"in '{class_name}' / '{session}'"
        )
        return False

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO comments
                (enrollment_id, student_name, class_name, session, term,
                 class_teacher_comment, head_teacher_comment,
                 head_teacher_comment_custom, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(enrollment_id, term) DO UPDATE SET
                class_teacher_comment       = excluded.class_teacher_comment,
                head_teacher_comment        = excluded.head_teacher_comment,
                head_teacher_comment_custom = excluded.head_teacher_comment_custom,
                updated_at                  = excluded.updated_at
        """, (
            enrollment_id, student_name, class_name, session, term,
            class_teacher_comment, head_teacher_comment,
            head_teacher_comment_custom
        ))
        conn.commit()
        logger.info(f"Comment saved for {student_name} / {term} / {session}")
        return True
    except Exception as e:
        logger.error(f"Error saving comment for {student_name}: {e}")
        return False
    finally:
        conn.close()


def get_comment(student_name, class_name, term, session):
    """
    Get comments for a student.

    Returns:
        dict with class_teacher_comment, head_teacher_comment,
        head_teacher_comment_custom — or None if no comment exists.
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.class_teacher_comment, c.head_teacher_comment,
               c.head_teacher_comment_custom
        FROM   comments c
        JOIN   class_session_students css ON css.id = c.enrollment_id
        JOIN   class_sessions cs ON cs.id = css.class_session_id
        WHERE  css.student_name = ? AND cs.class_name = ?
          AND  c.term = ? AND cs.session = ?
    """, (student_name, class_name, term, session))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def delete_comment(student_name, class_name, term, session):
    """
    Delete a comment for a student.

    Returns:
        bool: True if deleted, False on error or not found.
    """
    enrollment_id = get_enrollment_id(student_name, class_name, session)
    if enrollment_id is None:
        return False

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            DELETE FROM comments
            WHERE enrollment_id = ? AND term = ?
        """, (enrollment_id, term))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error deleting comment: {e}")
        return False
    finally:
        conn.close()
