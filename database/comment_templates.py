# database/comment_templates.py

"""Comment template operations for reusable teacher comments"""

import sqlite3
import logging
from .connection import get_connection

logger = logging.getLogger(__name__)


def add_comment_template(comment_text, comment_type, user_id, average_lower=None, average_upper=None):
    """
    Add a new comment template
    
    Args:
        comment_text: The comment text
        comment_type: Type of comment ('class_teacher' or 'head_teacher')
        user_id: ID of user creating the template
        average_lower: Lower bound of average range (required for head_teacher)
        average_upper: Upper bound of average range (required for head_teacher)
    
    Returns:
        bool: True if added successfully, False if template already exists
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO comment_templates (comment_text, comment_type, average_lower, average_upper, created_by, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (comment_text.strip(), comment_type, average_lower, average_upper, user_id))
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
        if comment_type == 'head_teacher':
            cursor.execute("""
                SELECT id, comment_text, comment_type, average_lower, average_upper, created_at
                FROM comment_templates
                WHERE comment_type = ?
                ORDER BY average_lower
            """, (comment_type,))
        else:
            cursor.execute("""
                SELECT id, comment_text, comment_type, average_lower, average_upper, created_at
                FROM comment_templates
                WHERE comment_type = ?
                ORDER BY comment_text
            """, (comment_type,))
    else:
        cursor.execute("""
            SELECT id, comment_text, comment_type, average_lower, average_upper, created_at
            FROM comment_templates
            ORDER BY comment_type, average_lower, comment_text
        """)
    templates = cursor.fetchall()
    conn.close()
    return templates


def get_head_teacher_comment_by_average(average):
    """
    Get the appropriate head teacher comment based on student average
    
    Args:
        average: Student's average score
    
    Returns:
        str or None: Comment text if a matching range is found, None otherwise
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT comment_text
        FROM comment_templates
        WHERE comment_type = 'head_teacher'
            AND average_lower <= ?
            AND average_upper >= ?
        ORDER BY average_lower
        LIMIT 1
    """, (average, average))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


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


def update_comment_template(template_id, new_text, average_lower=None, average_upper=None):
    """
    Update an existing comment template
    
    Args:
        template_id: ID of template to update
        new_text: New comment text
        average_lower: New lower bound (optional, for head_teacher)
        average_upper: New upper bound (optional, for head_teacher)
    
    Returns:
        bool: True if updated successfully, False if error occurs
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE comment_templates
            SET comment_text = ?, average_lower = ?, average_upper = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_text.strip(), average_lower, average_upper, template_id))
        conn.commit()
        logger.info(f"Comment template {template_id} updated")
        return True
    except sqlite3.IntegrityError:
        logger.warning("Updated comment template text already exists")
        return False
    finally:
        conn.close()


def check_range_overlap(average_lower, average_upper, exclude_id=None):
    """
    Check if a new average range overlaps with existing ranges
    
    Args:
        average_lower: Lower bound to check
        average_upper: Upper bound to check
        exclude_id: Template ID to exclude from check (for updates)
    
    Returns:
        bool: True if overlap exists, False otherwise
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    if exclude_id:
        cursor.execute("""
            SELECT COUNT(*) FROM comment_templates
            WHERE comment_type = 'head_teacher'
                AND id != ?
                AND ((average_lower <= ? AND average_upper >= ?)
                     OR (average_lower <= ? AND average_upper >= ?)
                     OR (average_lower >= ? AND average_upper <= ?))
        """, (exclude_id, average_lower, average_lower, average_upper, average_upper, average_lower, average_upper))
    else:
        cursor.execute("""
            SELECT COUNT(*) FROM comment_templates
            WHERE comment_type = 'head_teacher'
                AND ((average_lower <= ? AND average_upper >= ?)
                     OR (average_lower <= ? AND average_upper >= ?)
                     OR (average_lower >= ? AND average_upper <= ?))
        """, (average_lower, average_lower, average_upper, average_upper, average_lower, average_upper))
    
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0