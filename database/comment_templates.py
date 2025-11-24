# database/comment_templates.py

"""Comment template operations for reusable teacher comments"""

import sqlite3
import logging
from .connection import get_connection

logger = logging.getLogger(__name__)


def add_comment_template(comment_text, comment_type, user_id):
    """
    Add a new comment template (admin only)
    
    Args:
        comment_text: The comment text
        comment_type: Type of comment ('class_teacher' or 'head_teacher')
        user_id: ID of user creating the template
    
    Returns:
        bool: True if added successfully, False if template already exists
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO comment_templates (comment_text, comment_type, created_by)
            VALUES (?, ?, ?)
        """, (comment_text.strip(), comment_type, user_id))
        conn.commit()
        logger.info(f"Comment template added by user {user_id}")
        return True
    except sqlite3.IntegrityError:
        logger.warning("Comment template already exists")
        return False
    finally:
        conn.close()


def get_all_comment_templates(comment_type=None):
    """
    Get all comment templates, optionally filtered by type
    
    Args:
        comment_type: Optional filter ('class_teacher' or 'head_teacher')
    
    Returns:
        list: List of comment template records
    """
    conn = get_connection()
    cursor = conn.cursor()
    if comment_type:
        cursor.execute("""
            SELECT id, comment_text, comment_type, created_at
            FROM comment_templates
            WHERE comment_type = ?
            ORDER BY comment_text
        """, (comment_type,))
    else:
        cursor.execute("""
            SELECT id, comment_text, comment_type, created_at
            FROM comment_templates
            ORDER BY comment_type, comment_text
        """)
    templates = cursor.fetchall()
    conn.close()
    return templates


def delete_comment_template(template_id):
    """
    Delete a comment template
    
    Args:
        template_id: ID of template to delete
    
    Returns:
        bool: True if successful, False otherwise
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM comment_templates WHERE id = ?", (template_id,))
        conn.commit()
        logger.info(f"Comment template {template_id} deleted")
        return True
    except Exception as e:
        logger.error(f"Error deleting comment template: {e}")
        return False
    finally:
        conn.close()


def update_comment_template(template_id, new_text):
    """
    Update an existing comment template
    
    Args:
        template_id: ID of template to update
        new_text: New comment text
    
    Returns:
        bool: True if updated successfully, False if text already exists
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE comment_templates
            SET comment_text = ?
            WHERE id = ?
        """, (new_text.strip(), template_id))
        conn.commit()
        logger.info(f"Comment template {template_id} updated")
        return True
    except sqlite3.IntegrityError:
        logger.warning("Updated comment template text already exists")
        return False
    finally:
        conn.close()