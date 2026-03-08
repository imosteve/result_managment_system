# database/psychomotor.py

"""Psychomotor rating operations for student assessments"""

import logging
from .connection import get_connection

logger = logging.getLogger(__name__)


def create_psychomotor_rating(student_name, class_name, term, session, ratings):
    """
    Create or update psychomotor rating for a student
    
    Args:
        student_name: Name of the student
        class_name: Class name
        term: Term
        session: Session
        ratings: Dictionary with category names as keys and ratings (1-5) as values
                 Example: {"Punctuality": 5, "Neatness": 4, ...}
    
    Returns:
        bool: True if successful, False otherwise
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Convert category names to database column names
        db_ratings = {
            'punctuality': ratings.get('Punctuality', 3),
            'neatness': ratings.get('Neatness', 3),
            'honesty': ratings.get('Honesty', 3),
            'cooperation': ratings.get('Cooperation', 3),
            'leadership': ratings.get('Leadership', 3),
            'perseverance': ratings.get('Perseverance', 3),
            'politeness': ratings.get('Politeness', 3),
            'obedience': ratings.get('Obedience', 3),
            'attentiveness': ratings.get('Attentiveness', 3),
            'attitude_to_work': ratings.get('Attitude to work', 3)
        }
        
        cursor.execute("""
            INSERT OR REPLACE INTO psychomotor_ratings (
                student_name, class_name, term, session,
                punctuality, neatness, honesty, cooperation,
                leadership, perseverance, politeness, obedience,
                attentiveness, attitude_to_work, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            student_name, class_name, term, session,
            db_ratings['punctuality'], db_ratings['neatness'],
            db_ratings['honesty'], db_ratings['cooperation'],
            db_ratings['leadership'], db_ratings['perseverance'],
            db_ratings['politeness'], db_ratings['obedience'],
            db_ratings['attentiveness'], db_ratings['attitude_to_work']
        ))
        conn.commit()
        logger.info(f"Psychomotor rating saved for {student_name}")
        return True
    except Exception as e:
        logger.error(f"Error saving psychomotor rating: {e}")
        return False
    finally:
        conn.close()


def get_psychomotor_rating(student_name, class_name, term, session):
    """
    Get psychomotor rating for a student
    
    Args:
        student_name: Student name
        class_name: Class name
        term: Term
        session: Session
    
    Returns:
        dict or None: Dictionary with rating categories and values, or None if not found
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT punctuality, neatness, honesty, cooperation,
               leadership, perseverance, politeness, obedience,
               attentiveness, attitude_to_work
        FROM psychomotor_ratings
        WHERE student_name = ? AND class_name = ? AND term = ? AND session = ?
    """, (student_name, class_name, term, session))
    rating = cursor.fetchone()
    conn.close()
    
    if rating:
        return {
            'punctuality': rating[0],
            'neatness': rating[1],
            'honesty': rating[2],
            'cooperation': rating[3],
            'leadership': rating[4],
            'perseverance': rating[5],
            'politeness': rating[6],
            'obedience': rating[7],
            'attentiveness': rating[8],
            'attitude_to_work': rating[9]
        }
    return None


def delete_psychomotor_rating(student_name, class_name, term, session):
    """
    Delete psychomotor rating for a student
    
    Args:
        student_name: Student name
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
            DELETE FROM psychomotor_ratings
            WHERE student_name = ? AND class_name = ? AND term = ? AND session = ?
        """, (student_name, class_name, term, session))
        conn.commit()
        logger.info(f"Psychomotor rating deleted for {student_name}")
        return True
    except Exception as e:
        logger.error(f"Error deleting psychomotor rating: {e}")
        return False
    finally:
        conn.close()


def get_all_psychomotor_ratings(class_name, term, session):
    """
    Get all psychomotor ratings for a class
    
    Args:
        class_name: Class name
        term: Term
        session: Session
    
    Returns:
        list: List of rating records with student names and ratings
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT student_name, punctuality, neatness, honesty, cooperation,
               leadership, perseverance, politeness, obedience,
               attentiveness, attitude_to_work
        FROM psychomotor_ratings
        WHERE class_name = ? AND term = ? AND session = ?
        ORDER BY student_name
    """, (class_name, term, session))
    ratings = cursor.fetchall()
    conn.close()
    return ratings