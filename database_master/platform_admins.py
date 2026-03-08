# master_database/platform_admins.py
"""
CRUD operations for platform_admins table in master.db.

Platform admins are NOT school users — they live only in master.db and
manage the hosting platform (register/activate/deactivate schools, etc.).
"""

import sqlite3
import logging
from typing import Optional, Dict, Any, List
from .connection import get_master_connection
from .audit import log_school_action

logger = logging.getLogger(__name__)

# Default platform superadmin seeded on first startup
import os
_DEFAULT_EMAIL    = os.getenv("PLATFORM_ADMIN_EMAIL",    "admin@rms.com")
_DEFAULT_PASSWORD = os.getenv("PLATFORM_ADMIN_PASSWORD", "admin")


# ─────────────────────────────────────────────
# Internal seed  (called by setup.py only)
# ─────────────────────────────────────────────

def _seed_default_platform_admin(conn: sqlite3.Connection) -> None:
    """
    Insert the default platform superadmin if the table is empty.
    Only called once at first startup from setup.create_master_tables().
    """
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM platform_admins")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO platform_admins (email, username, password, role)
            VALUES (?, ?, ?, 'platform_superadmin')
        """, (
            _DEFAULT_EMAIL.lower().strip(),
            "platform_admin",
            _DEFAULT_PASSWORD,
        ))
        conn.commit()
        logger.warning(
            f"Default platform superadmin seeded: email='{_DEFAULT_EMAIL}' "
            "— CHANGE THIS PASSWORD IMMEDIATELY."
        )
    else:
        logger.debug("Platform admin already exists — skipping seed")


# ─────────────────────────────────────────────
# READ
# ─────────────────────────────────────────────

def get_platform_admin_by_email(email: str) -> Optional[Dict[str, Any]]:
    """
    Look up a platform admin by email address.
    Called by login.py BEFORE school resolution.

    Returns:
        Dict with id, email, username, password, role — or None
    """
    try:
        conn = get_master_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM platform_admins WHERE LOWER(email) = LOWER(?)",
            (email.strip(),)
        )
        result = cursor.fetchone()
        conn.close()
        return dict(result) if result else None
    except Exception as e:
        logger.error(f"Error looking up platform admin '{email}': {e}")
        return None


def get_platform_admin_by_id(admin_id: int) -> Optional[Dict[str, Any]]:
    """
    Look up a platform admin by primary key.

    Returns:
        Dict with id, email, username, password, role — or None
    """
    try:
        conn = get_master_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM platform_admins WHERE id = ?",
            (admin_id,)
        )
        result = cursor.fetchone()
        conn.close()
        return dict(result) if result else None
    except Exception as e:
        logger.error(f"Error looking up platform admin id={admin_id}: {e}")
        return None


def get_all_platform_admins() -> List[Dict[str, Any]]:
    """
    Return all platform admins (passwords included — caller must not
    expose them in the UI).

    Returns:
        List of dicts ordered by username
    """
    try:
        conn = get_master_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, email, username, role, password, created_at, updated_at "
            "FROM platform_admins ORDER BY id ASC"
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Error fetching all platform admins: {e}")
        return []


# ─────────────────────────────────────────────
# CREATE
# ─────────────────────────────────────────────

def create_platform_admin(
    email:        str,
    username:     str,
    password:     str,
    performed_by: str = "system",
) -> bool:
    """
    Create a new platform admin account.

    Args:
        email:        Unique email address
        username:     Unique display name
        password:     Plain-text password (min 4 chars)
        performed_by: Actor username for audit log

    Returns:
        True if created, False if email/username already exists or invalid input
    """
    if not email or "@" not in email:
        logger.error("create_platform_admin: invalid email")
        return False
    if len(password) < 4:
        logger.error("create_platform_admin: password too short (min 4 chars)")
        return False

    try:
        conn = get_master_connection()
        conn.execute("""
            INSERT INTO platform_admins (email, username, password, role)
            VALUES (?, ?, ?, 'platform_superadmin')
        """, (email.lower().strip(), username.strip(), password))
        conn.commit()
        conn.close()

        log_school_action(
            "platform", "ADMIN_CREATED", performed_by,
            f"Platform admin '{username}' ({email}) created"
        )
        logger.info(f"Platform admin '{username}' created")
        return True

    except sqlite3.IntegrityError:
        logger.warning(
            f"create_platform_admin: email '{email}' or username '{username}' "
            "already exists"
        )
        return False
    except Exception as e:
        logger.error(f"create_platform_admin error: {e}")
        return False


# ─────────────────────────────────────────────
# UPDATE
# ─────────────────────────────────────────────

def update_platform_admin_password(
    email:        str,
    new_password: str,
    performed_by: str = "system",
) -> bool:
    """
    Update a platform admin's password.

    Args:
        email:        Email of the admin to update
        new_password: New plain-text password (min 4 chars)
        performed_by: Actor username for audit log

    Returns:
        True if updated, False if not found or invalid
    """
    if len(new_password) < 4:
        logger.error("update_platform_admin_password: password too short")
        return False

    try:
        conn = get_master_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE platform_admins
            SET    password   = ?,
                   updated_at = CURRENT_TIMESTAMP
            WHERE  LOWER(email) = LOWER(?)
        """, (new_password, email.strip()))
        affected = cursor.rowcount
        conn.commit()
        conn.close()

        if affected == 0:
            logger.warning(f"update_platform_admin_password: '{email}' not found")
            return False

        log_school_action(
            "platform", "ADMIN_PASSWORD_CHANGED", performed_by,
            f"Password updated for platform admin '{email}'"
        )
        logger.info(f"Password updated for platform admin '{email}'")
        return True

    except Exception as e:
        logger.error(f"update_platform_admin_password error: {e}")
        return False


def update_platform_admin_email(
    admin_id:     int,
    new_email:    str,
    performed_by: str = "system",
) -> bool:
    """
    Update a platform admin's email address.

    Args:
        admin_id:     Primary key of the admin to update
        new_email:    New unique email address
        performed_by: Actor username for audit log

    Returns:
        True if updated, False if conflict or not found
    """
    if not new_email or "@" not in new_email:
        logger.error("update_platform_admin_email: invalid email")
        return False

    try:
        conn = get_master_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE platform_admins
            SET    email      = ?,
                   updated_at = CURRENT_TIMESTAMP
            WHERE  id = ?
        """, (new_email.lower().strip(), admin_id))
        affected = cursor.rowcount
        conn.commit()
        conn.close()

        if affected == 0:
            logger.warning(f"update_platform_admin_email: id={admin_id} not found")
            return False

        log_school_action(
            "platform", "ADMIN_EMAIL_CHANGED", performed_by,
            f"Email updated for platform admin id={admin_id} → '{new_email}'"
        )
        logger.info(f"Email updated for platform admin id={admin_id}")
        return True

    except sqlite3.IntegrityError:
        logger.warning(
            f"update_platform_admin_email: email '{new_email}' already in use"
        )
        return False
    except Exception as e:
        logger.error(f"update_platform_admin_email error: {e}")
        return False


# ─────────────────────────────────────────────
# DELETE
# ─────────────────────────────────────────────

def delete_platform_admin(
    admin_id:     int,
    performed_by: str = "system",
) -> bool:
    """
    Delete a platform admin account.

    Safety guard: refuses to delete the last remaining admin to prevent
    complete lockout.

    Args:
        admin_id:     Primary key of the admin to delete
        performed_by: Actor username for audit log

    Returns:
        True if deleted, False if not found or last admin
    """
    try:
        conn = get_master_connection()
        cursor = conn.cursor()

        # Lockout guard
        cursor.execute("SELECT COUNT(*) FROM platform_admins")
        if cursor.fetchone()[0] <= 1:
            logger.warning(
                "delete_platform_admin: refused — cannot delete the last admin"
            )
            conn.close()
            return False

        # Grab username for audit before deleting
        cursor.execute(
            "SELECT email, username FROM platform_admins WHERE id = ?",
            (admin_id,)
        )
        row = cursor.fetchone()
        if row is None:
            logger.warning(f"delete_platform_admin: id={admin_id} not found")
            conn.close()
            return False

        email    = row["email"]
        username = row["username"]

        cursor.execute("DELETE FROM platform_admins WHERE id = ?", (admin_id,))
        conn.commit()
        conn.close()

        log_school_action(
            "platform", "ADMIN_DELETED", performed_by,
            f"Platform admin '{username}' ({email}) deleted"
        )
        logger.info(f"Platform admin '{username}' (id={admin_id}) deleted")
        return True

    except Exception as e:
        logger.error(f"delete_platform_admin error: {e}")
        return False
