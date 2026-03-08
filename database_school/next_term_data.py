# database/next_term_info.py

"""Next term information operations for report cards"""

import logging
from .connection import get_connection

logger = logging.getLogger(__name__)


def create_or_update_next_term_info(term, session, next_term_begins, fees_json, user_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO next_term_info (
                term, session, next_term_begins, fees_json, updated_at, updated_by
            ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
        """, (term, session, next_term_begins, fees_json, user_id))
        
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error saving next term info: {e}")
        return False
    finally:
        conn.close()


def get_next_term_info(term, session):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM next_term_info
        WHERE term = ? AND session = ?
    """, (term, session))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        # Convert tuple to dictionary
        columns = ['id', 'term', 'session', 'next_term_begins', 'fees_json', 'updated_at', 'updated_by']
        info = dict(zip(columns, row))
        # Parse fees_json string back to dictionary
        import json
        info['fees'] = json.loads(info.get('fees_json', '{}'))
        return info
    return None


def get_all_next_term_info():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, term, session, next_term_begins, fees_json, updated_at, updated_by
        FROM next_term_info
        ORDER BY session DESC, term
    """)
    rows = cursor.fetchall()
    conn.close()
    
    # Convert tuples to dictionaries
    infos = []
    for row in rows:
        columns = ['id', 'term', 'session', 'next_term_begins', 'fees_json', 'updated_at', 'updated_by']
        info = dict(zip(columns, row))
        infos.append(info)
    
    return infos


def delete_next_term_info(term, session):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            DELETE FROM next_term_info
            WHERE term = ? AND session = ?
        """, (term, session))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error deleting next term info: {e}")
        return False
    finally:
        conn.close()


def get_next_term_begin_date(term, session):
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
