# database/comments.py

"""Comment management operations for student report cards"""

import sqlite3
import logging
from .connection import get_connection

logger = logging.getLogger(__name__)


def create_comment(student_name, class_name, term, session, 
                   class_teacher_comment=None, head_teacher_comment=None):
    """
    Create or update a comment for a student
    
    Args:
        student_name: Student name
        class_name: Class name
        term: Term
        session: Session
        class_teacher_comment: Comment from class teacher (optional)
        head_teacher_comment: Comment from head teacher (optional)
    
    Returns:
        bool: True if successful, False otherwise
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO comments (
                student_name, class_name, term, session, 
                class_teacher_comment, head_teacher_comment, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (student_name, class_name, term, session, 
              class_teacher_comment, head_teacher_comment))
        conn.commit()
        logger.info(f"Comment saved for {student_name}")
        return True
    except sqlite3.IntegrityError:
        logger.error(f"Failed to save comment for {student_name}")
        return False
    finally:
        conn.close()


def get_comment(student_name, class_name, term, session):
    """
    Get comments for a student
    
    Args:
        student_name: Student name
        class_name: Class name
        term: Term
        session: Session
    
    Returns:
        sqlite3.Row or None: Comment record with class_teacher_comment and head_teacher_comment
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT class_teacher_comment, head_teacher_comment
        FROM comments
        WHERE student_name = ? AND class_name = ? AND term = ? AND session = ?
    """, (student_name, class_name, term, session))
    comment = cursor.fetchone()
    conn.close()
    return comment


def delete_comment(student_name, class_name, term, session):
    """
    Delete a comment for a student
    
    Args:
        student_name: Student name
        class_name: Class name
        term: Term
        session: Session
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM comments
        WHERE student_name = ? AND class_name = ? AND term = ? AND session = ?
    """, (student_name, class_name, term, session))
    conn.commit()
    conn.close()
    logger.info(f"Comment deleted for {student_name}")