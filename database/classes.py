# database/classes.py

"""Class management operations"""

import sqlite3
import logging
from .connection import get_connection

logger = logging.getLogger(__name__)


def get_all_classes(user_id=None, role=None):
    """
    Get all classes with restrictions for non-admins
    
    Args:
        user_id: User ID (optional, for filtering)
        role: User role (optional, for filtering)
    
    Returns:
        list: List of class dictionaries with class_name, term, session
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Admins see all classes
    if role in ["superadmin", "admin"]:
        cursor.execute("""
            SELECT name, term, session 
            FROM classes 
            ORDER BY session DESC, term, name
        """)
    elif role == "class_teacher" and user_id:
        # Class teachers see only their class teacher assignments
        cursor.execute("""
            SELECT DISTINCT c.name, c.term, c.session
            FROM classes c
            JOIN teacher_assignments ta ON c.name = ta.class_name 
                AND c.term = ta.term AND c.session = ta.session
            WHERE ta.user_id = ? AND ta.assignment_type = 'class_teacher'
            ORDER BY c.session DESC, c.term, c.name
        """, (user_id,))
    elif role == "subject_teacher" and user_id:
        # Subject teachers see only their subject teacher assignments
        cursor.execute("""
            SELECT DISTINCT c.name, c.term, c.session
            FROM classes c
            JOIN teacher_assignments ta ON c.name = ta.class_name 
                AND c.term = ta.term AND c.session = ta.session
            WHERE ta.user_id = ? AND ta.assignment_type = 'subject_teacher'
            ORDER BY c.session DESC, c.term, c.name
        """, (user_id,))
    else:
        conn.close()
        return []
        
    rows = cursor.fetchall()
    classes = [
        {"class_name": row[0], "term": row[1], "session": row[2]}
        for row in rows
    ]
    conn.close()
    return classes


def create_class(class_name, term, session):
    """
    Create a new class
    
    Args:
        class_name: Name of the class
        term: Term (e.g., '1st Term', '2nd Term', '3rd Term')
        session: Session (e.g., '2024/2025')
    
    Returns:
        bool: True if created successfully, False if already exists
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO classes (name, term, session) VALUES (?, ?, ?)",
            (class_name, term, session)
        )
        conn.commit()
        logger.info(f"Class '{class_name}' created for {term} - {session}")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Class '{class_name}' already exists for {term} - {session}")
        return False
    finally:
        conn.close()


def update_class(original_class_name, original_term, original_session, 
                 new_class_name, new_term, new_session):
    """
    Update an existing class entry
    
    This function handles the update in a transaction with proper ordering
    to avoid foreign key constraint violations.
    
    Args:
        original_class_name: Original class name
        original_term: Original term
        original_session: Original session
        new_class_name: New class name
        new_term: New term
        new_session: New session
    
    Returns:
        bool: True if updated successfully, False otherwise
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Start transaction
        cursor.execute("BEGIN TRANSACTION")
        
        # Temporarily disable foreign key constraints
        cursor.execute("PRAGMA foreign_keys = OFF")
        
        # Update the class
        cursor.execute("""
            UPDATE classes
            SET name = ?, term = ?, session = ?
            WHERE name = ? AND term = ? AND session = ?
        """, (new_class_name, new_term, new_session, 
              original_class_name, original_term, original_session))
        
        # Re-enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # Commit transaction
        conn.commit()
        logger.info(f"Class updated from '{original_class_name}-{original_term}-{original_session}' to '{new_class_name}-{new_term}-{new_session}'")
        return True
        
    except sqlite3.Error as e:
        # Rollback on error
        conn.rollback()
        cursor.execute("PRAGMA foreign_keys = ON")  # Re-enable even on error
        logger.error(f"Error updating class: {str(e)}")
        return False
    finally:
        conn.close()


def delete_class(class_name, term, session):
    """
    Delete a class and all associated data (CASCADE)
    
    Args:
        class_name: Class name to delete
        term: Term
        session: Session
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM classes WHERE name = ? AND term = ? AND session = ?", 
        (class_name, term, session)
    )
    conn.commit()
    conn.close()
    logger.info(f"Class '{class_name}' deleted for {term} - {session}")


def clear_all_classes():
    """
    Delete all classes and associated data (students, subjects, scores) via CASCADE
    
    Returns:
        bool: True if successful, False otherwise
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM classes")
        conn.commit()
        logger.info("All classes cleared successfully")
        return True
    except sqlite3.Error as e:
        logger.error(f"Error clearing classes: {e}")
        return False
    finally:
        conn.close()