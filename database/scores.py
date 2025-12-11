# database/scores.py

"""Score management operations"""

import sqlite3
import logging
from .connection import get_connection
from utils import assign_grade

logger = logging.getLogger(__name__)


def get_scores_by_class_subject(class_name, subject_name, term, session, user_id=None, role=None):
    """
    Get all scores for a specific class and subject with role-based restrictions
    
    Args:
        class_name: Class name
        subject_name: Subject name
        term: Term
        session: Session
        user_id: User ID (optional, for filtering)
        role: User role (optional, for filtering)
    
    Returns:
        list: List of score records
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    if role in ["superadmin", "admin"]:
        cursor.execute("""
            SELECT id, student_name, subject_name, test_score, exam_score, 
                   total_score, grade, position
            FROM scores 
            WHERE class_name = ? AND subject_name = ? AND term = ? AND session = ?
            ORDER BY total_score DESC
        """, (class_name, subject_name, term, session))
    elif user_id:
        cursor.execute("""
            SELECT s.id, s.student_name, s.subject_name, s.test_score, s.exam_score, 
                   s.total_score, s.grade, s.position
            FROM scores s
            JOIN teacher_assignments ta ON s.class_name = ta.class_name 
                AND s.term = ta.term AND s.session = ta.session
            WHERE s.class_name = ? AND s.subject_name = ? 
                AND s.term = ? AND s.session = ? 
                AND ta.user_id = ?
                AND (ta.assignment_type = 'class_teacher' 
                     OR (ta.assignment_type = 'subject_teacher' AND ta.subject_name = ?))
            ORDER BY s.total_score DESC
        """, (class_name, subject_name, term, session, user_id, subject_name))
    else:
        conn.close()
        return []
    
    scores = cursor.fetchall()
    conn.close()
    return scores


def get_all_scores_by_class(class_name, term, session, user_id=None, role=None):
    """
    Get all scores for a class with role-based restrictions
    
    Args:
        class_name: Class name
        term: Term
        session: Session
        user_id: User ID (optional, for filtering)
        role: User role (optional, for filtering)
    
    Returns:
        list: List of score records
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    if role in ["superadmin", "admin"]:
        cursor.execute("""
            SELECT id, student_name, subject_name, test_score, exam_score, 
                   total_score, grade, position
            FROM scores 
            WHERE class_name = ? AND term = ? AND session = ?
            ORDER BY student_name, subject_name
        """, (class_name, term, session))
    elif user_id:
        cursor.execute("""
            SELECT DISTINCT s.id, s.student_name, s.subject_name, s.test_score, s.exam_score, 
                   s.total_score, s.grade, s.position
            FROM scores s
            JOIN teacher_assignments ta ON s.class_name = ta.class_name 
                AND s.term = ta.term AND s.session = ta.session
            WHERE s.class_name = ? AND s.term = ? AND s.session = ? 
                AND ta.user_id = ?
                AND (ta.assignment_type = 'class_teacher' 
                     OR (ta.assignment_type = 'subject_teacher' AND ta.subject_name = s.subject_name))
            ORDER BY s.student_name, s.subject_name
        """, (class_name, term, session, user_id))
    else:
        conn.close()
        return []
    
    scores = cursor.fetchall()
    conn.close()
    return scores


def get_student_scores(student_name, class_name, term, session, user_id=None, role=None):
    """
    Get all scores for a specific student with role-based restrictions
    
    Args:
        student_name: Student name
        class_name: Class name
        term: Term
        session: Session
        user_id: User ID (optional, for filtering)
        role: User role (optional, for filtering)
    
    Returns:
        list: List of score records
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    if role in ["superadmin", "admin"]:
        cursor.execute("""
            SELECT id, student_name, subject_name, test_score, exam_score, 
                   total_score, grade, position
            FROM scores 
            WHERE student_name = ? AND class_name = ? AND term = ? AND session = ?
            ORDER BY subject_name
        """, (student_name, class_name, term, session))
    elif user_id:
        cursor.execute("""
            SELECT DISTINCT s.id, s.student_name, s.subject_name, s.test_score, s.exam_score, 
                   s.total_score, s.grade, s.position
            FROM scores s
            JOIN teacher_assignments ta ON s.class_name = ta.class_name 
                AND s.term = ta.term AND s.session = ta.session
            WHERE s.student_name = ? AND s.class_name = ? 
                AND s.term = ? AND s.session = ? 
                AND ta.user_id = ?
                AND (ta.assignment_type = 'class_teacher' 
                     OR (ta.assignment_type = 'subject_teacher' AND ta.subject_name = s.subject_name))
            ORDER BY s.subject_name
        """, (student_name, class_name, term, session, user_id))
    else:
        conn.close()
        return []
    
    scores = cursor.fetchall()
    conn.close()
    return scores


def save_scores(scores_data, class_name, subject_name, term, session):
    """
    Save multiple scores with position calculation
    
    Args:
        scores_data: List of score dictionaries
        class_name: Class name
        subject_name: Subject name
        term: Term
        session: Session
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Sort scores in descending order
    sorted_scores = sorted(scores_data, key=lambda x: x['total'], reverse=True)
    
    # Calculate positions
    for i, score in enumerate(sorted_scores):
        if i > 0 and score['total'] == sorted_scores[i-1]['total']:
            score['position'] = sorted_scores[i-1]['position']
        else:
            score['position'] = i + 1
    
    # Delete existing scores
    cursor.execute("""
        DELETE FROM scores 
        WHERE class_name = ? AND subject_name = ? AND term = ? AND session = ?
    """, (class_name, subject_name, term, session))
    
    # Insert new scores
    for score in sorted_scores:
        cursor.execute("""
            INSERT INTO scores (
                student_name, subject_name, class_name, term, session,
                test_score, exam_score, total_score, grade, position
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            score['student'], score['subject'], score['class'], score['term'], score['session'],
            score['test'], score['exam'], score['total'], 
            score['grade'], score['position']
        ))
    
    conn.commit()
    conn.close()
    logger.info(f"Saved {len(sorted_scores)} scores for {subject_name} in {class_name}")


def update_score(student_name, subject_name, class_name, term, session, test_score, exam_score):
    """
    Update individual score
    
    Args:
        student_name: Student name
        subject_name: Subject name
        class_name: Class name
        term: Term
        session: Session
        test_score: Test score (0-30)
        exam_score: Exam score (0-70)
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    total_score = test_score + exam_score
    grade = assign_grade(total_score)
    
    cursor.execute("""
        INSERT OR REPLACE INTO scores (
            student_name, subject_name, class_name, term, session,
            test_score, exam_score, total_score, grade, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (student_name, subject_name, class_name, term, session, 
          test_score, exam_score, total_score, grade))
    
    conn.commit()
    recalculate_positions(class_name, subject_name, term, session)
    conn.close()
    logger.info(f"Score updated for {student_name} in {subject_name}")


def recalculate_positions(class_name, subject_name, term, session):
    """
    Recalculate positions for a subject in a class for specific term and session
    
    Args:
        class_name: Class name
        subject_name: Subject name
        term: Term
        session: Session
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, total_score 
        FROM scores 
        WHERE class_name = ? AND subject_name = ? AND term = ? AND session = ?
        ORDER BY total_score DESC
    """, (class_name, subject_name, term, session))
    
    scores = cursor.fetchall()
    
    for i, (score_id, total_score) in enumerate(scores):
        if i > 0 and total_score == scores[i-1][1]:
            cursor.execute("SELECT position FROM scores WHERE id = ?", (scores[i-1][0],))
            position = cursor.fetchone()[0]
        else:
            position = i + 1
        
        cursor.execute("UPDATE scores SET position = ? WHERE id = ?", (position, score_id))
    
    conn.commit()
    conn.close()


def get_class_average(class_name, term, session, user_id, role):
    """
    Calculate class average based on individual student averages
    
    Args:
        class_name: Class name
        term: Term
        session: Session
        user_id: User ID
        role: User role
    
    Returns:
        float: Class average score
    """
    from .students import get_students_by_class
    
    conn = get_connection()
    
    try:
        students = get_students_by_class(class_name, term, session, user_id, role)
        if not students:
            return 0
        
        student_averages = []
        for student in students:
            student_name = student[1]
            scores = get_student_scores(student_name, class_name, term, session, user_id, role)
            
            if scores:
                total_score = sum(score[5] for score in scores)
                student_avg = total_score / len(scores)
                student_averages.append(student_avg)
        
        if student_averages:
            class_average = sum(student_averages) / len(student_averages)
            return round(class_average, 2)
        return 0
        
    except Exception as e:
        logger.error(f"Error calculating class average: {str(e)}")
        return 0
    finally:
        conn.close()


def get_student_grand_totals(class_name, term, session, user_id=None, role=None):
    """
    Get grand totals and ranks for all students in a class
    
    Args:
        class_name: Class name
        term: Term
        session: Session
        user_id: User ID (optional, for filtering)
        role: User role (optional, for filtering)
    
    Returns:
        list: List of dictionaries with student_name, grand_total, position
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if role in ["superadmin", "admin"]:
            cursor.execute("""
                SELECT student_name, SUM(total_score) as grand_total
                FROM scores
                WHERE class_name = ? AND term = ? AND session = ?
                GROUP BY student_name
                ORDER BY grand_total DESC
            """, (class_name, term, session))
        elif user_id:
            cursor.execute("""
                SELECT s.student_name, SUM(s.total_score) as grand_total
                FROM scores s
                JOIN teacher_assignments ta ON s.class_name = ta.class_name 
                    AND s.term = ta.term AND s.session = ta.session
                WHERE s.class_name = ? AND s.term = ? AND s.session = ? 
                    AND ta.user_id = ?
                    AND (ta.assignment_type = 'class_teacher' 
                         OR (ta.assignment_type = 'subject_teacher' AND ta.subject_name = s.subject_name))
                GROUP BY s.student_name
                ORDER BY grand_total DESC
            """, (class_name, term, session, user_id))
        else:
            conn.close()
            return []
        
        student_totals = cursor.fetchall()

        result = []
        current_rank = 1
        previous_total = None
        for i, (student_name, grand_total) in enumerate(student_totals):
            if grand_total != previous_total:
                current_rank = i + 1
            result.append({
                'student_name': student_name,
                'grand_total': grand_total,
                'position': current_rank
            })
            previous_total = grand_total

        conn.close()
        return result
    except sqlite3.Error as e:
        logger.error(f"Error fetching grand totals: {e}")
        conn.close()
        return []


def clear_all_scores(class_name, subject_name, term, session):
    """
    Delete all scores for a specific class, subject, term, and session
    
    Args:
        class_name: Class name
        subject_name: Subject name
        term: Term
        session: Session
    
    Returns:
        bool: True if successful, False otherwise
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            DELETE FROM scores 
            WHERE class_name = ? AND subject_name = ? AND term = ? AND session = ?
        """, (class_name, subject_name, term, session))
        conn.commit()
        logger.info(f"All scores cleared for {subject_name} in {class_name}")
        return True
    except sqlite3.Error as e:
        logger.error(f"Error clearing scores: {e}")
        return False
    finally:
        conn.close()


def get_grade_distribution(student_name, class_name, term, session, user_id=None, role=None):
    """
    Get grade distribution for a student (for SSS2 and SSS3)
    Returns a string like "3As, 4Bs, 2Cs" or empty string if no grades
    
    Args:
        student_name: Student name
        class_name: Class name
        term: Term
        session: Session
        user_id: User ID (optional, for filtering)
        role: User role (optional, for filtering)
    
    Returns:
        str: Grade distribution string (e.g., "3A, 4B, 2C")
    """
    scores = get_student_scores(student_name, class_name, term, session, user_id, role)
    
    if not scores:
        return ""
    
    # Count grades
    grade_counts = {}
    for score in scores:
        grade = score[6]  # grade is at index 6
        if grade and grade.strip():
            grade_counts[grade] = grade_counts.get(grade, 0) + 1
    
    # Format as "3A, 4B, 2C" in grade order
    grade_order = ['A', 'B', 'C', 'D', 'E', 'F']
    parts = []
    for grade in grade_order:
        if grade in grade_counts:
            count = grade_counts[grade]
            parts.append(f"{count}{grade}")
    
    return ", ".join(parts) if parts else ""


def get_student_average(student_name, class_name, term, session, user_id=None, role=None):
    """
    Get the average score for a specific student
    
    Args:
        student_name: Student name
        class_name: Class name
        term: Term
        session: Session
        user_id: User ID (optional, for filtering)
        role: User role (optional, for filtering)
    
    Returns:
        float: Student's average score, 0 if no scores found
    """
    scores = get_student_scores(student_name, class_name, term, session, user_id, role)
    
    if not scores:
        return 0
    
    # Filter out None values
    valid_totals = [score[5] for score in scores if score[5] is not None]
    
    if not valid_totals:
        return 0
    
    return sum(valid_totals) / len(valid_totals)
