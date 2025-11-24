# database/next_term_info.py

"""Next term information operations for report cards"""

import logging
from .connection import get_connection

logger = logging.getLogger(__name__)


def create_or_update_next_term_info(term, session, info_data, user_id):
    """
    Create or update next term information
    
    Args:
        term: Term name
        session: Session name
        info_data: Dictionary containing all the information fields
        user_id: ID of user making the update
    
    Returns:
        bool: True if successful, False otherwise
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO next_term_info (
                term, session, next_term_begins, next_term_ends,
                vacation_starts, vacation_ends, fees_due_date,
                registration_starts, registration_ends,
                school_hours, assembly_time, closing_time,
                important_dates, holidays, events_schedule,
                uniform_requirements, book_list,
                pta_meeting_date, visiting_day, sports_day, cultural_day,
                excursion_info, health_requirements,
                contact_person, contact_email, contact_phone,
                principal_message, special_instructions,
                bus_schedule, cafeteria_info, library_hours,
                updated_at, updated_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
        """, (
            term, session,
            info_data.get('next_term_begins'),
            info_data.get('next_term_ends'),
            info_data.get('vacation_starts'),
            info_data.get('vacation_ends'),
            info_data.get('fees_due_date'),
            info_data.get('registration_starts'),
            info_data.get('registration_ends'),
            info_data.get('school_hours'),
            info_data.get('assembly_time'),
            info_data.get('closing_time'),
            info_data.get('important_dates'),
            info_data.get('holidays'),
            info_data.get('events_schedule'),
            info_data.get('uniform_requirements'),
            info_data.get('book_list'),
            info_data.get('pta_meeting_date'),
            info_data.get('visiting_day'),
            info_data.get('sports_day'),
            info_data.get('cultural_day'),
            info_data.get('excursion_info'),
            info_data.get('health_requirements'),
            info_data.get('contact_person'),
            info_data.get('contact_email'),
            info_data.get('contact_phone'),
            info_data.get('principal_message'),
            info_data.get('special_instructions'),
            info_data.get('bus_schedule'),
            info_data.get('cafeteria_info'),
            info_data.get('library_hours'),
            user_id
        ))
        conn.commit()
        logger.info(f"Next term info saved for {term} - {session}")
        return True
    except Exception as e:
        logger.error(f"Error saving next term info: {e}")
        return False
    finally:
        conn.close()


def get_next_term_info(term, session):
    """
    Get next term information for specific term and session
    
    Args:
        term: Term name
        session: Session name
    
    Returns:
        sqlite3.Row or None: Next term information record
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM next_term_info
        WHERE term = ? AND session = ?
    """, (term, session))
    info = cursor.fetchone()
    conn.close()
    return info


def get_all_next_term_info():
    """
    Get all next term information entries
    
    Returns:
        list: List of next term information records (summary view)
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT term, session, next_term_begins, updated_at
        FROM next_term_info
        ORDER BY session DESC, term
    """)
    infos = cursor.fetchall()
    conn.close()
    return infos


def delete_next_term_info(term, session):
    """
    Delete next term information for specific term and session
    
    Args:
        term: Term name
        session: Session name
    
    Returns:
        bool: True if successful, False otherwise
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            DELETE FROM next_term_info
            WHERE term = ? AND session = ?
        """, (term, session))
        conn.commit()
        logger.info(f"Next term info deleted for {term} - {session}")
        return True
    except Exception as e:
        logger.error(f"Error deleting next term info: {e}")
        return False
    finally:
        conn.close()


def get_next_term_begin_date(term, session):
    """
    Get only the next term begin date for a specific term and session
    This is used for report card generation
    
    Args:
        term: Term name
        session: Session name
    
    Returns:
        str: Next term begin date or "To be announced" if not set
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT next_term_begins FROM next_term_info
        WHERE term = ? AND session = ?
    """, (term, session))
    result = cursor.fetchone()
    conn.close()
    
    if result and result[0]:
        return result[0]
    return "To be announced"