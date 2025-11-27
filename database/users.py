# database/users.py

"""User management and teacher assignment operations"""

import sqlite3
import logging
from .connection import get_connection

logger = logging.getLogger(__name__)


def create_user(username, password, role=None):
    """
    Create a new user with username and password
    
    Args:
        username: Username for the new user
        password: Password (should be pre-hashed)
        role: Optional role ('admin' or 'superadmin')
    
    Returns:
        bool: True if user created successfully, False otherwise
    """
    if len(password) < 4:
        logger.error(f"Password for user '{username}' is too short (length: {len(password)})")
        return False
    
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Create user
        cursor.execute("""
            INSERT INTO users (username, password)
            VALUES (?, ?)
        """, (username, password))
        
        user_id = cursor.lastrowid
        
        # If role is provided and is admin/superadmin, add to admin_users table
        if role in ['admin', 'superadmin']:
            cursor.execute("""
                INSERT INTO admin_users (user_id, role)
                VALUES (?, ?)
            """, (user_id, role))
        
        conn.commit()
        logger.info(f"User '{username}' created successfully")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Failed to create user '{username}' - may already exist")
        return False
    finally:
        conn.close()


def get_user_by_username(username):
    """
    Retrieve user by username with role information
    
    Args:
        username: Username to search for
    
    Returns:
        sqlite3.Row or None: User record with role information
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.username, u.password, au.role
        FROM users u
        LEFT JOIN admin_users au ON u.id = au.user_id
        WHERE u.username = ?
    """, (username,))
    user = cursor.fetchone()
    conn.close()
    return user


def get_user_role(user_id):
    """
    Get user's admin role if they have one
    
    Args:
        user_id: User ID
    
    Returns:
        str or None: Role ('admin' or 'superadmin') or None if not admin
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT role FROM admin_users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


def delete_user(user_id):
    """
    Delete a user and their assignments (CASCADE)
    
    Args:
        user_id: User ID to delete
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def get_all_users():
    """
    Get all users with their roles
    
    Returns:
        list: List of user records with role information
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.username, u.password, au.role
        FROM users u
        LEFT JOIN admin_users au ON u.id = au.user_id
        ORDER BY u.username
    """)
    users = cursor.fetchall()
    conn.close()
    return users


def update_user(user_id, new_username, new_password=None):
    """
    Update user's username and optionally password
    
    Args:
        user_id: User ID to update
        new_username: New username
        new_password: Optional new password (pre-hashed)
    
    Returns:
        bool: True if updated successfully, False otherwise
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if new_password:
            if len(new_password) < 4:
                logger.error(f"Password for user '{new_username}' is too short")
                return False
            cursor.execute("""
                UPDATE users 
                SET username = ?, password = ?
                WHERE id = ?
            """, (new_username, new_password, user_id))
        else:
            cursor.execute("""
                UPDATE users 
                SET username = ?
                WHERE id = ?
            """, (new_username, user_id))
        
        conn.commit()
        logger.info(f"User {user_id} updated successfully")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Failed to update user - username may already exist")
        return False
    finally:
        conn.close()


# ==================== TEACHER ASSIGNMENT OPERATIONS ====================

def get_user_assignments(user_id):
    """
    Get all assignments for a user (both class and subject teacher assignments)
    
    Args:
        user_id: User ID
    
    Returns:
        list: List of assignment records
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, class_name, term, session, subject_name, assignment_type
            FROM teacher_assignments
            WHERE user_id = ?
            ORDER BY session DESC, term, class_name, subject_name
        """, (user_id,))
        assignments = cursor.fetchall()
        conn.close()
        
        logger.info(f"Retrieved {len(assignments)} assignments for user {user_id}")
        return assignments
    except Exception as e:
        logger.error(f"Error getting assignments for user {user_id}: {str(e)}")
        return []


def assign_teacher(user_id, class_name, term, session, subject_name=None, assignment_type='class_teacher'):
    """
    Assign a user as class teacher or subject teacher with proper duplicate checking
    
    Args:
        user_id: User ID to assign
        class_name: Class name
        term: Term
        session: Session
        subject_name: Subject name (required for subject_teacher)
        assignment_type: 'class_teacher' or 'subject_teacher'
    
    Returns:
        bool: True if assigned successfully, False otherwise
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Validate assignment_type
        if assignment_type == 'subject_teacher' and not subject_name:
            logger.error("Subject teacher assignment requires a subject name")
            return False
        
        if assignment_type == 'class_teacher':
            subject_name = None  # Class teachers don't have subject_name
        
        # Check if this user already has this exact assignment
        if assignment_type == 'class_teacher':
            cursor.execute("""
                SELECT id FROM teacher_assignments
                WHERE user_id = ? AND class_name = ? AND term = ? AND session = ? 
                AND assignment_type = 'class_teacher'
            """, (user_id, class_name, term, session))
        else:
            cursor.execute("""
                SELECT id FROM teacher_assignments
                WHERE user_id = ? AND class_name = ? AND term = ? AND session = ? 
                AND subject_name = ? AND assignment_type = 'subject_teacher'
            """, (user_id, class_name, term, session, subject_name))
        
        if cursor.fetchone():
            logger.warning(f"This assignment already exists for user {user_id}")
            return False
        
        # Insert the assignment
        cursor.execute("""
            INSERT INTO teacher_assignments (user_id, class_name, term, session, subject_name, assignment_type)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, class_name, term, session, subject_name, assignment_type))
        conn.commit()
        logger.info(f"Successfully assigned user {user_id} as {assignment_type} for {class_name}-{term}-{session}")
        return True
    except sqlite3.IntegrityError as e:
        logger.warning(f"Assignment already exists for user {user_id}: {str(e)}")
        return False
    finally:
        conn.close()


def batch_assign_subject_teacher(user_id, class_name, term, session, subject_names):
    """
    Batch assign a user as subject teacher for multiple subjects at once
    
    Args:
        user_id: User ID to assign
        class_name: Class name
        term: Term
        session: Session
        subject_names: List of subject names
    
    Returns:
        tuple: (success_count, failed_subjects)
    """
    success_count = 0
    failed_subjects = []
    
    for subject_name in subject_names:
        if assign_teacher(user_id, class_name, term, session, subject_name, 'subject_teacher'):
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


def update_assignment(assignment_id, new_class_name, new_term, new_session, new_subject_name=None):
    """
    Update a teacher assignment
    
    Args:
        assignment_id: Assignment ID to update
        new_class_name: New class name
        new_term: New term
        new_session: New session
        new_subject_name: New subject name (optional)
    
    Returns:
        bool: True if updated successfully, False otherwise
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE teacher_assignments
            SET class_name = ?, term = ?, session = ?, subject_name = ?
            WHERE id = ?
        """, (new_class_name, new_term, new_session, new_subject_name, assignment_id))
        conn.commit()
        logger.info(f"Assignment {assignment_id} updated successfully")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Failed to update assignment - may already exist")
        return False
    finally:
        conn.close()