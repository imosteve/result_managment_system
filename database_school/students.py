# database/students.py

"""Student management operations"""

import sqlite3
import logging
from .connection import get_connection

logger = logging.getLogger(__name__)


def get_students_by_class(class_name, term, session, user_id=None, role=None):
    """
    Get all students in a class for specific term and session with role-based restrictions
    
    Args:
        class_name: Class name
        term: Term
        session: Session
        user_id: User ID (optional, for filtering)
        role: User role (optional, for filtering)
    
    Returns:
        list: List of student records
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    if role in ["superadmin", "admin"]:
        cursor.execute("""
            SELECT id, name, gender, email, school_fees_paid
            FROM students 
            WHERE class_name = ? AND term = ? AND session = ?
            ORDER BY name
        """, (class_name, term, session))
    elif user_id:
        # Teachers see students in their assigned classes
        cursor.execute("""
            SELECT DISTINCT s.id, s.name, s.gender, s.email, s.school_fees_paid
            FROM students s
            JOIN teacher_assignments ta ON s.class_name = ta.class_name 
                AND s.term = ta.term AND s.session = ta.session
            WHERE s.class_name = ? AND s.term = ? AND s.session = ? 
                AND ta.user_id = ?
            ORDER BY s.name
        """, (class_name, term, session, user_id))
    else:
        conn.close()
        return []
    
    students = cursor.fetchall()
    conn.close()
    return students


def create_student(name, gender, email, class_name, term, session, school_fees_paid='NO'):
    """
    Create a new student with optional school fees status
    
    Args:
        name: Student name
        gender: 'M' or 'F'
        email: Email address (optional)
        class_name: Class name
        term: Term
        session: Session
        school_fees_paid: 'YES' or 'NO' (default: 'NO')
    
    Returns:
        bool: True if created successfully, False if already exists
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO students (name, gender, email, school_fees_paid, class_name, term, session) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, gender or None, email or None, school_fees_paid, class_name, term, session))
        conn.commit()
        logger.info(f"Student '{name}' created in {class_name} - {term} - {session}")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Student '{name}' already exists in {class_name} - {term} - {session}")
        return False
    finally:
        conn.close()


def create_students_batch(students_data, class_name, term, session):
    """
    Create multiple students in a single transaction
    
    Args:
        students_data: List of dictionaries with student data
        class_name: Class name
        term: Term
        session: Session
    
    Returns:
        bool: True if all created successfully, False otherwise
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.executemany("""
            INSERT INTO students (name, gender, email, school_fees_paid, class_name, term, session) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [(s['name'], s.get('gender'), s.get('email'), 
               s.get('school_fees_paid', 'NO'), class_name, term, session) 
              for s in students_data])
        conn.commit()
        logger.info(f"Batch created {len(students_data)} students in {class_name}")
        return True
    except sqlite3.IntegrityError as e:
        logger.error(f"Batch student creation failed: {str(e)}")
        return False
    finally:
        conn.close()


def update_student(student_id, name, gender, email, school_fees_paid='NO'):
    """
    Update student information including school fees status
    
    Args:
        student_id: Student ID
        name: Student name
        gender: 'M' or 'F'
        email: Email address
        school_fees_paid: 'YES' or 'NO'
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE students 
        SET name = ?, gender = ?, email = ?, school_fees_paid = ?
        WHERE id = ?
    """, (name, gender or None, email or None, school_fees_paid, student_id))
    conn.commit()
    conn.close()
    logger.info(f"Student ID {student_id} updated")


def delete_student(student_id):
    """
    Delete a student and all associated scores (CASCADE)
    
    Args:
        student_id: Student ID to delete
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM students WHERE id = ?", (student_id,))
    conn.commit()
    conn.close()
    logger.info(f"Student ID {student_id} deleted")


def delete_all_students(class_name, term, session):
    """
    Delete all students for a specific class, term, and session
    
    Args:
        class_name: Class name
        term: Term
        session: Session
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM students 
        WHERE class_name = ? AND term = ? AND session = ?
    """, (class_name, term, session))
    conn.commit()
    conn.close()
    logger.info(f"All students deleted from {class_name} - {term} - {session}")


def get_students_with_paid_fees(class_name, term, session, user_id=None, role=None):
    """
    Get only students who have paid school fees and have email addresses
    
    Args:
        class_name: Class name
        term: Term
        session: Session
        user_id: User ID (optional, for filtering)
        role: User role (optional, for filtering)
    
    Returns:
        list: List of students with paid fees and email addresses
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    if role in ["superadmin", "admin"]:
        cursor.execute("""
            SELECT id, name, gender, email, school_fees_paid
            FROM students 
            WHERE class_name = ? AND term = ? AND session = ?
                AND school_fees_paid = 'YES' AND email IS NOT NULL AND email != ''
            ORDER BY name
        """, (class_name, term, session))
    elif user_id:
        cursor.execute("""
            SELECT DISTINCT s.id, s.name, s.gender, s.email, s.school_fees_paid
            FROM students s
            JOIN teacher_assignments ta ON s.class_name = ta.class_name 
                AND s.term = ta.term AND s.session = ta.session
            WHERE s.class_name = ? AND s.term = ? AND s.session = ? 
                AND ta.user_id = ?
                AND s.school_fees_paid = 'YES' AND s.email IS NOT NULL AND s.email != ''
            ORDER BY s.name
        """, (class_name, term, session, user_id))
    else:
        conn.close()
        return []
    
    students = cursor.fetchall()
    conn.close()
    return students