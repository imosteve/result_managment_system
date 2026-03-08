# database/student_subjects.py

"""Student subject selection operations (for SSS2 and SSS3)"""

import logging
from .connection import get_connection

logger = logging.getLogger(__name__)


def get_student_selected_subjects(student_name, class_name, term, session):
    """
    Get subjects selected by a specific student
    
    Args:
        student_name: Student name
        class_name: Class name
        term: Term
        session: Session
    
    Returns:
        list: List of subject names selected by the student
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT subject_name
        FROM student_subject_selections
        WHERE student_name = ? AND class_name = ? AND term = ? AND session = ?
    """, (student_name, class_name, term, session))
    subjects = [row[0] for row in cursor.fetchall()]
    conn.close()
    return subjects


def save_student_subject_selections(student_name, selected_subjects, class_name, term, session):
    """
    Save/update subject selections for a student
    
    Args:
        student_name: Student name
        selected_subjects: List of subject names
        class_name: Class name
        term: Term
        session: Session
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Delete existing selections
    cursor.execute("""
        DELETE FROM student_subject_selections
        WHERE student_name = ? AND class_name = ? AND term = ? AND session = ?
    """, (student_name, class_name, term, session))
    
    # Insert new selections
    for subject in selected_subjects:
        cursor.execute("""
            INSERT INTO student_subject_selections (student_name, subject_name, class_name, term, session)
            VALUES (?, ?, ?, ?, ?)
        """, (student_name, subject, class_name, term, session))
    
    conn.commit()
    conn.close()
    logger.info(f"Subject selections saved for {student_name}: {len(selected_subjects)} subjects")


def get_all_student_subject_selections(class_name, term, session):
    """
    Get all student subject selections for a class
    
    Args:
        class_name: Class name
        term: Term
        session: Session
    
    Returns:
        list: List of tuples (student_name, subject_name)
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT student_name, subject_name
        FROM student_subject_selections
        WHERE class_name = ? AND term = ? AND session = ?
        ORDER BY student_name, subject_name
    """, (class_name, term, session))
    selections = cursor.fetchall()
    conn.close()
    return selections