# master_database/audit.py
"""
Audit log operations.

The school_audit_log table is append-only — rows are never updated or deleted.
All platform-level actions (school registration, status changes, admin changes,
db backups/restores) write a row here so there is a full immutable history.
"""

import logging
from typing import List, Dict, Any, Optional
from .connection import get_master_connection

logger = logging.getLogger(__name__)


def log_school_action(
    school_code:  str,
    action:       str,
    performed_by: str,
    details:      str = "",
) -> None:
    """
    Append an immutable entry to school_audit_log.

    Args:
        school_code:  School code this action relates to (use 'platform' for
                      actions not tied to a specific school, e.g. admin CRUD)
        action:       Short uppercase label, e.g. 'REGISTERED', 'DEACTIVATED',
                      'BACKUP_CREATED', 'ADMIN_CREATED'
        performed_by: Username or email of the actor
        details:      Optional free-text description
    """
    try:
        conn = get_master_connection()
        conn.execute("""
            INSERT INTO school_audit_log (school_code, action, performed_by, details)
            VALUES (?, ?, ?, ?)
        """, (school_code, action, performed_by, details))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Audit log write failed [{action}]: {e}")


def get_audit_log(
    limit: int = 200,
    offset: int = 0,
    action_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Return recent audit log entries across all schools.

    Args:
        limit:         Max rows to return (default 200)
        offset:        Pagination offset
        action_filter: Optional partial match on action column (case-insensitive)

    Returns:
        List of dicts with keys: id, school_code, action, performed_by,
        details, created_at
    """
    try:
        conn = get_master_connection()
        cursor = conn.cursor()

        if action_filter:
            cursor.execute("""
                SELECT id, school_code, action, performed_by, details, created_at
                FROM   school_audit_log
                WHERE  UPPER(action) LIKE UPPER(?)
                ORDER  BY created_at DESC
                LIMIT  ? OFFSET ?
            """, (f"%{action_filter}%", limit, offset))
        else:
            cursor.execute("""
                SELECT id, school_code, action, performed_by, details, created_at
                FROM   school_audit_log
                ORDER  BY created_at DESC
                LIMIT  ? OFFSET ?
            """, (limit, offset))

        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Error fetching audit log: {e}")
        return []


def get_audit_log_by_school(
    school_code: str,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Return audit log entries for a single school.

    Args:
        school_code: School code to filter by
        limit:       Max rows to return

    Returns:
        List of dicts ordered by most recent first
    """
    try:
        conn = get_master_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, school_code, action, performed_by, details, created_at
            FROM   school_audit_log
            WHERE  school_code = ?
            ORDER  BY created_at DESC
            LIMIT  ?
        """, (school_code.lower().strip(), limit))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Error fetching audit log for '{school_code}': {e}")
        return []
