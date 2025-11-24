# database/subjects.py

"""Subject management operations"""

import sqlite3
import logging
from .connection import get_connection

logger = logging.getLogger(__name__)


def get_subjects_by_class(class_name, term, session, user_id=None, role=None):
    """
    Get all subjects for a class in specific term and session with role-based restrictions
    
    Args:
        class_name: Class name
        term: Term
        session: Session
        user_id: User ID (optional, for filtering)
        role: User role (optional, for filtering)
    
    Returns:
        list: List of subject records
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    if role in ["superadmin", "admin"]:
        cursor.execute("""
            SELECT id, name 
            FROM subjects 
            WHERE class_name = ? AND term = ? AND session = ?
            ORDER BY name
        """, (class_name, term, session))
    elif user_id:
        # Teachers see subjects in their assigned classes
        cursor.execute("""
            SELECT DISTINCT s.id, s.name 
            FROM subjects s
            JOIN teacher_assignments ta ON s.class_name = ta.class_name 
                AND s.term = ta.term AND s.session = ta.session
            WHERE s.class_name = ? AND s.term = ? AND s.session = ? 
                AND ta.user_id = ?
            ORDER BY s.name
        """, (class_name, term, session, user_id))
    else:
        conn.close()
        return []
    
    subjects = cursor.fetchall()
    conn.close()
    return subjects


def create_subject(subject_name, class_name, term, session):
    """
    Create a new subject for a class in specific term and session
    
    Args:
        subject_name: Subject name
        class_name: Class name
        term: Term
        session: Session
    
    Returns:
        bool: True if created successfully, False if already exists
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO subjects (name, class_name, term, session) 
            VALUES (?, ?, ?, ?)
        """, (subject_name, class_name, term, session))
        conn.commit()
        logger.info(f"Subject '{subject_name}' created for {class_name} - {term} - {session}")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Subject '{subject_name}' already exists for {class_name} - {term} - {session}")
        return False
    finally:
        conn.close()


def update_subject(subject_id, new_subject_name, new_class_name, new_term, new_session):
    """
    Update an existing subject entry
    
    Args:
        subject_id: Subject ID to update
        new_subject_name: New subject name
        new_class_name: New class name
        new_term: New term
        new_session: New session
    
    Returns:
        bool: True if updated successfully, False otherwise
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE subjects
            SET name = ?, class_name = ?, term = ?, session = ?
            WHERE id = ?
        """, (new_subject_name, new_class_name, new_term, new_session, subject_id))
        conn.commit()
        logger.info(f"Subject ID {subject_id} updated")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Failed to update subject - may already exist")
        return False
    finally:
        conn.close()


def delete_subject(subject_id):
    """
    Delete a subject and all associated scores (CASCADE)
    
    Args:
        subject_id: Subject ID to delete
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))
    conn.commit()
    conn.close()
    logger.info(f"Subject ID {subject_id} deleted")


def clear_all_subjects(class_name, term, session):
    """
    Delete all subjects for a specific class, term, and session
    
    Args:
        class_name: Class name
        term: Term
        session: Session
    
    Returns:
        bool: True if successful, False otherwise
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            DELETE FROM subjects 
            WHERE class_name = ? AND term = ? AND session = ?
        """, (class_name, term, session))
        conn.commit()
        logger.info(f"All subjects cleared for {class_name} - {term} - {session}")
        return True
    except sqlite3.Error as e:
        logger.error(f"Error clearing subjects: {e}")
        return False
    finally:
        conn.close()