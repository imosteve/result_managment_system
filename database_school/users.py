# database/users.py  — MULTI-TENANT VERSION
# database/users.py  — POST-MIGRATION VERSION
"""
User management and teacher assignment operations.
"""

import sqlite3
import logging
from .connection import get_connection

logger = logging.getLogger(__name__)

VALID_ROLES = ("superadmin", "admin", "teacher")


# ─────────────────────────────────────────────
# User CRUD
# ─────────────────────────────────────────────

def create_user(username: str, password: str, email: str, role: str = "teacher") -> bool:
    """
    Create a new user.

    Args:
        username : Unique username
        password : Plain-text password (swap for bcrypt in production)
        email    : Unique email address (used for multi-tenant login)
        role     : 'superadmin' | 'admin' | 'teacher'  (default: 'teacher')

    Returns:
        True if created, False if username/email already exists or invalid role.
    """
    if len(password) < 4:
        logger.error(f"Password for '{username}' is too short (min 4 chars)")
        return False

    if role not in VALID_ROLES:
        logger.error(f"Invalid role '{role}' for user '{username}'")
        return False

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO users (username, password, email, role)
            VALUES (?, ?, ?, ?)
        """, (username, password, email.lower().strip() if email else None, role))

        conn.commit()
        logger.info(f"User '{username}' created (role='{role}')")
        return True

    except sqlite3.IntegrityError:
        logger.warning(f"User '{username}' or email '{email}' already exists")
        return False
    finally:
        conn.close()


def get_user_by_username(username: str):
    """
    Retrieve a user row by username.

    Returns:
        Row with columns: id, username, password, role, email
        None if not found.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, password, role, email
        FROM users
        WHERE username = ?
    """, (username,))
    user = cursor.fetchone()
    conn.close()
    return user


def get_user_by_email(email: str):
    """
    Retrieve a user row by email address.
    Used by login.py for email-based authentication.

    Returns:
        Row with columns: id, username, password, role, email
        None if not found.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, password, role, email
        FROM users
        WHERE LOWER(email) = LOWER(?)
    """, (email.strip(),))
    user = cursor.fetchone()
    conn.close()
    return user


def get_user_role(user_id: int) -> str | None:
    """
    Return the role for a user.

    Returns:
        'superadmin' | 'admin' | 'teacher' — or None if user not found.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT role FROM users WHERE id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


def delete_user(user_id: int) -> None:
    """Delete a user (CASCADE removes assignments)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def get_all_users() -> list:
    """
    Get all users ordered by username.

    Returns:
        List of rows, each with columns: id, username, password, role, email
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, password, role, email
        FROM users
        ORDER BY username
    """)
    users = cursor.fetchall()
    conn.close()
    return users


def update_user(
    user_id: int,
    new_username: str,
    new_password: str | None = None,
    new_email: str | None = None,
) -> bool:
    """
    Update a user's username, optionally password and email.

    Returns:
        True if updated, False on unique-constraint conflict.
    """
    if new_password and len(new_password) < 4:
        logger.error(f"New password for user {user_id} is too short (min 4 chars)")
        return False

    conn = get_connection()
    cursor = conn.cursor()
    try:
        if new_password:
            cursor.execute("""
                UPDATE users
                SET username = ?, password = ?, email = ?
                WHERE id = ?
            """, (new_username, new_password,
                  new_email.lower().strip() if new_email else None,
                  user_id))
        else:
            cursor.execute("""
                UPDATE users
                SET username = ?, email = ?
                WHERE id = ?
            """, (new_username,
                  new_email.lower().strip() if new_email else None,
                  user_id))

        conn.commit()
        logger.info(f"User {user_id} updated")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Update failed for user {user_id} — username/email conflict")
        return False
    finally:
        conn.close()


# ==================== TEACHER ASSIGNMENT OPERATIONS ====================

def get_user_assignments(user_id):
    """
    Get all assignments for a user (both class and subject teacher assignments).

    Returns:
        list of dicts: {id, class_name, session, subject_name, assignment_type}
    """
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, class_name, session, subject_name, assignment_type
            FROM teacher_assignments
            WHERE user_id = ?
            ORDER BY session DESC, class_name, subject_name
        """, (user_id,))
        rows = cursor.fetchall()
        conn.close()
        logger.info(f"Retrieved {len(rows)} assignments for user {user_id}")
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Error getting assignments for user {user_id}: {str(e)}")
        return []


def assign_teacher(user_id, class_name, session, subject_name=None, assignment_type='class_teacher'):
    """
    Assign a user as class teacher or subject teacher.
    term is no longer a column on teacher_assignments — assignments cover all terms in a session.

    Args:
        user_id:         User ID to assign
        class_name:      Class name
        session:         Session (e.g. "2024/2025")
        subject_name:    Subject name (required for subject_teacher)
        assignment_type: 'class_teacher' or 'subject_teacher'

    Returns:
        bool: True if assigned successfully, False otherwise
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if assignment_type == 'subject_teacher' and not subject_name:
            logger.error("Subject teacher assignment requires a subject name")
            return False

        if assignment_type == 'class_teacher':
            subject_name = None

        # Duplicate check
        if assignment_type == 'class_teacher':
            cursor.execute("""
                SELECT id FROM teacher_assignments
                WHERE user_id = ? AND class_name = ? AND session = ?
                  AND assignment_type = 'class_teacher'
            """, (user_id, class_name, session))
        else:
            cursor.execute("""
                SELECT id FROM teacher_assignments
                WHERE user_id = ? AND class_name = ? AND session = ?
                  AND subject_name = ? AND assignment_type = 'subject_teacher'
            """, (user_id, class_name, session, subject_name))

        if cursor.fetchone():
            logger.warning(f"Assignment already exists for user {user_id}")
            return False

        cursor.execute("""
            INSERT INTO teacher_assignments
                (user_id, class_name, session, subject_name, assignment_type)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, class_name, session, subject_name, assignment_type))
        conn.commit()
        logger.info(f"Assigned user {user_id} as {assignment_type} for {class_name}-{session}")
        return True
    except sqlite3.IntegrityError as e:
        logger.warning(f"Assignment already exists for user {user_id}: {str(e)}")
        return False
    finally:
        conn.close()


def batch_assign_subject_teacher(user_id, class_name, session, subject_names):
    """
    Batch assign a user as subject teacher for multiple subjects.

    Returns:
        tuple: (success_count, failed_subjects)
    """
    success_count = 0
    failed_subjects = []

    for subject_name in subject_names:
        if assign_teacher(user_id, class_name, session, subject_name, 'subject_teacher'):
            success_count += 1
        else:
            failed_subjects.append(subject_name)

    logger.info(f"Batch assignment: {success_count}/{len(subject_names)} subjects assigned successfully")
    return success_count, failed_subjects


def delete_assignment(assignment_id):
    """
    Delete a teacher assignment
    
    Args:
        assignment_id: Assignment ID to delete
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM teacher_assignments WHERE id = ?", (assignment_id,))
    conn.commit()
    conn.close()


def update_assignment(assignment_id, new_class_name, new_subject_name=None):
    """
    Update a teacher assignment's class and subject.
    term is no longer stored on assignments.

    Returns:
        bool: True if updated successfully, False otherwise
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE teacher_assignments
            SET class_name = ?, subject_name = ?
            WHERE id = ?
        """, (new_class_name, new_subject_name, assignment_id))
        conn.commit()
        logger.info(f"Assignment {assignment_id} updated successfully")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Failed to update assignment {assignment_id} — may already exist")
        return False
    finally:
        conn.close()