# database/psychomotor.py

"""Psychomotor rating operations for student assessments"""

import logging
from .connection import get_connection

logger = logging.getLogger(__name__)


def create_psychomotor_rating(student_name, class_name, term, session, ratings):
    """
    Create or update psychomotor rating for a student.

    New schema: keyed by (enrollment_id, term). enrollment_id is resolved
    internally — callers still pass (student_name, class_name, term, session).

    Args:
        student_name: Name of the student
        class_name:   Class name
        term:         "First", "Second", or "Third"
        session:      e.g. "2024/2025"
        ratings:      Dict with display-name keys and int values (1-5)
                      e.g. {"Punctuality": 5, "Neatness": 4, ...}

    Returns:
        bool: True if successful, False otherwise
    """
    from .students import get_enrollment_id

    enrollment_id = get_enrollment_id(student_name, class_name, session, term)
    if enrollment_id is None:
        logger.error(
            f"create_psychomotor_rating: no enrollment for '{student_name}' "
            f"in '{class_name}' / '{session}'"
        )
        return False

    db_ratings = {
        'punctuality':      ratings.get('Punctuality', 3),
        'neatness':         ratings.get('Neatness', 3),
        'honesty':          ratings.get('Honesty', 3),
        'cooperation':      ratings.get('Cooperation', 3),
        'leadership':       ratings.get('Leadership', 3),
        'perseverance':     ratings.get('Perseverance', 3),
        'politeness':       ratings.get('Politeness', 3),
        'obedience':        ratings.get('Obedience', 3),
        'attentiveness':    ratings.get('Attentiveness', 3),
        'attitude_to_work': ratings.get('Attitude to work', 3),
    }

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO psychomotor_ratings (
                enrollment_id, student_name, class_name, session, term,
                punctuality, neatness, honesty, cooperation,
                leadership, perseverance, politeness, obedience,
                attentiveness, attitude_to_work, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(enrollment_id, term) DO UPDATE SET
                punctuality      = excluded.punctuality,
                neatness         = excluded.neatness,
                honesty          = excluded.honesty,
                cooperation      = excluded.cooperation,
                leadership       = excluded.leadership,
                perseverance     = excluded.perseverance,
                politeness       = excluded.politeness,
                obedience        = excluded.obedience,
                attentiveness    = excluded.attentiveness,
                attitude_to_work = excluded.attitude_to_work,
                updated_at       = excluded.updated_at
        """, (
            enrollment_id, student_name, class_name, session, term,
            db_ratings['punctuality'],     db_ratings['neatness'],
            db_ratings['honesty'],         db_ratings['cooperation'],
            db_ratings['leadership'],      db_ratings['perseverance'],
            db_ratings['politeness'],      db_ratings['obedience'],
            db_ratings['attentiveness'],   db_ratings['attitude_to_work'],
        ))
        conn.commit()
        logger.info(f"Psychomotor rating saved for {student_name} / {term} / {session}")
        return True
    except Exception as e:
        logger.error(f"Error saving psychomotor rating: {e}")
        return False
    finally:
        conn.close()


def get_psychomotor_rating(student_name, class_name, term, session):
    """
    Get psychomotor rating for a student.

    New schema: joins via class_session_students to resolve enrollment_id.
    Callers still pass (student_name, class_name, term, session) — unchanged API.

    Returns:
        dict or None: Dictionary with rating categories and values, or None if not found
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT pr.punctuality, pr.neatness, pr.honesty, pr.cooperation,
               pr.leadership, pr.perseverance, pr.politeness, pr.obedience,
               pr.attentiveness, pr.attitude_to_work
        FROM   psychomotor_ratings pr
        JOIN   class_session_students css ON css.id = pr.enrollment_id
        JOIN   class_sessions cs          ON cs.id  = css.class_session_id
        WHERE  css.student_name = ? AND cs.class_name = ?
          AND  pr.term = ? AND cs.session = ?
    """, (student_name, class_name, term, session))
    rating = cursor.fetchone()
    conn.close()

    if rating:
        return {
            'punctuality':     rating[0],
            'neatness':        rating[1],
            'honesty':         rating[2],
            'cooperation':     rating[3],
            'leadership':      rating[4],
            'perseverance':    rating[5],
            'politeness':      rating[6],
            'obedience':       rating[7],
            'attentiveness':   rating[8],
            'attitude_to_work': rating[9],
        }
    return None


def delete_psychomotor_rating(student_name, class_name, term, session):
    """
    Delete psychomotor rating for a student.

    Resolves enrollment_id internally. Callers API unchanged.

    Returns:
        bool: True if successful, False otherwise
    """
    from .students import get_enrollment_id

    enrollment_id = get_enrollment_id(student_name, class_name, session, term)
    if enrollment_id is None:
        logger.warning(
            f"delete_psychomotor_rating: no enrollment for '{student_name}' "
            f"in '{class_name}' / '{session}'"
        )
        return False

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            DELETE FROM psychomotor_ratings
            WHERE enrollment_id = ? AND term = ?
        """, (enrollment_id, term))
        conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info(f"Psychomotor rating deleted for {student_name} / {term} / {session}")
        return deleted
    except Exception as e:
        logger.error(f"Error deleting psychomotor rating: {e}")
        return False
    finally:
        conn.close()


def get_all_psychomotor_ratings(class_name, term, session):
    """
    Get all psychomotor ratings for a class.

    New schema: joins via enrollment to get the right term/session.
    Returns same shape as before so callers need no changes.

    Returns:
        list of tuples: (student_name, punctuality, neatness, honesty,
                         cooperation, leadership, perseverance, politeness,
                         obedience, attentiveness, attitude_to_work)
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT css.student_name,
               pr.punctuality, pr.neatness, pr.honesty, pr.cooperation,
               pr.leadership, pr.perseverance, pr.politeness, pr.obedience,
               pr.attentiveness, pr.attitude_to_work
        FROM   psychomotor_ratings pr
        JOIN   class_session_students css ON css.id = pr.enrollment_id
        JOIN   class_sessions cs          ON cs.id  = css.class_session_id
        WHERE  cs.class_name = ? AND pr.term = ? AND cs.session = ?
        ORDER  BY css.student_name
    """, (class_name, term, session))
    ratings = cursor.fetchall()
    conn.close()
    return ratings