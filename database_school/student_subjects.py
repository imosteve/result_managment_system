# database/student_subjects.py
"""
Student subject selections — adapted for the enrollment_id model.

API surface unchanged. Callers pass (student_name, class_name, term, session).
Enrollment ID is resolved internally.
"""

import logging
from .connection import get_connection
from .students import get_enrollment_id

logger = logging.getLogger(__name__)


def get_student_selected_subjects(student_name, class_name, term, session):
    """
    Get subjects selected by a specific student.

    Returns:
        list of subject name strings.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sss.subject_name
        FROM   student_subject_selections sss
        JOIN   class_session_students css ON css.id = sss.enrollment_id
        JOIN   class_sessions cs ON cs.id = css.class_session_id
        WHERE  css.student_name = ? AND cs.class_name = ?
          AND  sss.term = ? AND cs.session = ?
    """, (student_name, class_name, term, session))
    subjects = [row[0] for row in cursor.fetchall()]
    conn.close()
    return subjects


def save_student_subject_selections(student_name, selected_subjects,
                                     class_name, term, session):
    """
    Save/update subject selections for a student.
    Replaces existing selections for this term.

    Args:
        student_name:      student full name
        selected_subjects: list of subject name strings
        class_name, term, session: context
    """
    enrollment_id = get_enrollment_id(student_name, class_name, session)
    if enrollment_id is None:
        logger.error(
            f"save_student_subject_selections: no enrollment for "
            f"'{student_name}' in '{class_name}' / '{session}'"
        )
        return

    conn = get_connection()
    cursor = conn.cursor()

    # Delete existing for this term only
    cursor.execute("""
        DELETE FROM student_subject_selections
        WHERE enrollment_id = ? AND term = ?
    """, (enrollment_id, term))

    # Insert new selections
    for subject in selected_subjects:
        cursor.execute("""
            INSERT OR IGNORE INTO student_subject_selections
                (enrollment_id, student_name, class_name, session,
                 term, subject_name)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (enrollment_id, student_name, class_name, session,
              term, subject))

    conn.commit()
    conn.close()
    logger.info(
        f"Subject selections saved for {student_name} / {term}: "
        f"{len(selected_subjects)} subjects"
    )


def get_all_student_subject_selections(class_name, term, session):
    """
    Get all student subject selections for a class.

    Returns:
        list of (student_name, subject_name) tuples.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sss.student_name, sss.subject_name
        FROM   student_subject_selections sss
        JOIN   class_session_students css ON css.id = sss.enrollment_id
        JOIN   class_sessions cs ON cs.id = css.class_session_id
        WHERE  cs.class_name = ? AND sss.term = ? AND cs.session = ?
        ORDER  BY sss.student_name, sss.subject_name
    """, (class_name, term, session))
    selections = cursor.fetchall()
    conn.close()
    return selections
