# database/subjects.py

"""Subject management operations — new schema (subjects are per-class only, no term/session)"""

import sqlite3
import logging
from .connection import get_connection

logger = logging.getLogger(__name__)


def get_subjects_by_class(class_name: str) -> list:
    """
    Get all subjects for a class.
    Subjects are session/term-independent in the new schema.

    Returns:
        list of dicts: {id, class_name, subject_name}
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, class_name, subject_name
        FROM   subjects
        WHERE  class_name = ?
        ORDER  BY subject_name
    """, (class_name,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_subject(subject_name: str, class_name: str) -> bool:
    """
    Create a new subject for a class.

    Returns:
        True if created, False if already exists.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO subjects (subject_name, class_name)
            VALUES (?, ?)
        """, (subject_name.strip(), class_name))
        conn.commit()
        logger.info(f"Subject '{subject_name}' created for class '{class_name}'")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Subject '{subject_name}' already exists for class '{class_name}'")
        return False
    finally:
        conn.close()


def update_subject(subject_id: int, new_subject_name: str, class_name: str) -> bool:
    """
    Update an existing subject's name.

    Returns:
        True if updated, False on conflict or error.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE subjects
            SET    subject_name = ?, class_name = ?
            WHERE  id = ?
        """, (new_subject_name.strip(), class_name, subject_id))
        conn.commit()
        logger.info(f"Subject ID {subject_id} updated to '{new_subject_name}'")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Failed to update subject ID {subject_id} — name may already exist")
        return False
    finally:
        conn.close()


def delete_subject(subject_id: int) -> bool:
    """
    Delete a subject by ID.

    Returns:
        True if a row was deleted, False otherwise.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info(f"Subject ID {subject_id} deleted")
        return deleted
    except Exception as e:
        logger.error(f"Error deleting subject ID {subject_id}: {e}")
        return False
    finally:
        conn.close()


def clear_all_subjects(class_name: str) -> bool:
    """
    Delete ALL subjects for a class.

    Returns:
        True if successful, False on error.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM subjects WHERE class_name = ?", (class_name,))
        conn.commit()
        logger.warning(f"All subjects cleared for class '{class_name}'")
        return True
    except sqlite3.Error as e:
        logger.error(f"Error clearing subjects for '{class_name}': {e}")
        return False
    finally:
        conn.close()