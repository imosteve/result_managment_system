# master_database/schools.py
"""
CRUD and status operations for the schools table in master.db.
"""

import os
import sqlite3
import logging
from typing import Optional, Dict, Any, List
from .connection import get_master_connection, SCHOOLS_DB_DIR
from .audit import log_school_action

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Path helper
# ─────────────────────────────────────────────

def get_school_db_path(school_code: str) -> str:
    """Return the filesystem path to a school's SQLite database."""
    return os.path.join(SCHOOLS_DB_DIR, f"{school_code.lower().strip()}.db")


# ─────────────────────────────────────────────
# READ
# ─────────────────────────────────────────────

def get_all_schools() -> List[Dict[str, Any]]:
    """Return all schools (active and inactive) ordered by name."""
    try:
        conn = get_master_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM schools ORDER BY school_name")
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"get_all_schools error: {e}")
        return []


def get_school_by_code(
    school_code: str,
    active_only: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Look up a school by its unique code.

    Args:
        school_code: e.g. 'suis'
        active_only: If True, returns None for inactive schools.
                     Pass True when resolving a cookie-restored session.
    """
    try:
        conn = get_master_connection()
        cursor = conn.cursor()
        if active_only:
            cursor.execute(
                "SELECT * FROM schools WHERE school_code = ? AND status = 'active'",
                (school_code.lower().strip(),)
            )
        else:
            cursor.execute(
                "SELECT * FROM schools WHERE school_code = ?",
                (school_code.lower().strip(),)
            )
        result = cursor.fetchone()
        conn.close()
        return dict(result) if result else None
    except Exception as e:
        logger.error(f"get_school_by_code '{school_code}' error: {e}")
        return None


def get_school_by_domain(email_domain: str) -> Optional[Dict[str, Any]]:
    """
    Look up an ACTIVE school by email domain.
    Primary login lookup — returns None if inactive.
    """
    try:
        conn = get_master_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM schools WHERE email_domain = ? AND status = 'active'",
            (email_domain.lower().strip(),)
        )
        result = cursor.fetchone()
        conn.close()
        return dict(result) if result else None
    except Exception as e:
        logger.error(f"get_school_by_domain '{email_domain}' error: {e}")
        return None


def resolve_school_from_email(email: str) -> Optional[Dict[str, Any]]:
    """
    Extract domain from an email and return the matching ACTIVE school.
    Called in login.py after confirming the user is not a platform admin.

    Returns:
        School dict or None (not found / inactive)
    """
    if not email or "@" not in email:
        return None
    domain = email.split("@")[1].lower().strip()
    school = get_school_by_domain(domain)
    if school is None:
        logger.warning(f"No active school for domain: '{domain}'")
    else:
        logger.info(f"Domain '{domain}' → school '{school['school_code']}'")
    return school


# ─────────────────────────────────────────────
# CREATE
# ─────────────────────────────────────────────

def register_school(
    school_name:   str,
    school_code:   str,
    email_domain:  str,
    contact_email: str = "",
    address:       str = "",
    phone:         str = "",
    performed_by:  str = "system",
) -> Dict[str, Any]:
    """
    Register a new school and create its isolated SQLite database.

    Steps:
      1. Validate inputs
      2. Write master DB record (fail fast on duplicate code/domain)
      3. Create the school's database file
      4. Seed default superadmin and admin users
      5. Write audit log entry

    Args:
        school_name:   Human-readable name, e.g. 'Greenfield Academy'
        school_code:   Short unique ID, e.g. 'greenfield' (lowercased, no spaces)
        email_domain:  Staff login domain, e.g. 'greenfield.edu'
        contact_email: Optional contact email stored in master DB
        address:       Optional address
        phone:         Optional phone
        performed_by:  Actor for audit log

    Returns:
        Dict with school_code, db_path, db_name

    Raises:
        ValueError:      school_code or email_domain already registered
        FileExistsError: database file already exists on disk
    """
    school_code  = school_code.lower().strip().replace(" ", "_")
    email_domain = email_domain.lower().strip()
    db_name      = f"{school_code}.db"
    db_path      = get_school_db_path(school_code)

    if os.path.exists(db_path):
        raise FileExistsError(
            f"A database already exists at '{db_path}'. "
            "This school code may have been registered before."
        )

    # 1. Write master DB record
    conn = get_master_connection()
    try:
        conn.execute("""
            INSERT INTO schools
                (school_name, school_code, email_domain, database_name,
                 contact_email, address, phone, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
        """, (school_name, school_code, email_domain, db_name,
              contact_email, address, phone))
        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.close()
        raise ValueError(f"school_code or email_domain already exists: {e}")
    finally:
        conn.close()

    # 2. Create school DB
    _initialize_school_database(db_path)

    # 3. Seed default users
    _create_school_default_users(db_path, school_code, email_domain)

    # 4. Audit
    log_school_action(
        school_code, "REGISTERED", performed_by,
        f"'{school_name}' registered — domain: '{email_domain}', db: '{db_path}'"
    )

    logger.info(f"School '{school_name}' registered: {db_path}")
    return {"school_code": school_code, "db_path": db_path, "db_name": db_name}


# ─────────────────────────────────────────────
# UPDATE
# ─────────────────────────────────────────────

def update_school_status(
    school_code:  str,
    new_status:   str,
    performed_by: str = "system",
) -> bool:
    """
    Activate or deactivate a school.

    Does NOT touch the school's database file — only updates the master
    DB record. Inactive schools are rejected at login.

    Args:
        school_code: School to update
        new_status:  'active' or 'inactive'
        performed_by: Actor for audit log

    Returns:
        True if updated, False on error or not found
    """
    if new_status not in ("active", "inactive"):
        logger.error(f"update_school_status: invalid status '{new_status}'")
        return False

    try:
        conn = get_master_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE schools
            SET    status     = ?,
                   updated_at = CURRENT_TIMESTAMP
            WHERE  school_code = ?
        """, (new_status, school_code.lower().strip()))
        affected = cursor.rowcount
        conn.commit()
        conn.close()

        if affected == 0:
            logger.warning(f"update_school_status: '{school_code}' not found")
            return False

        log_school_action(
            school_code,
            f"STATUS_CHANGED_TO_{new_status.upper()}",
            performed_by,
            f"Status set to '{new_status}' by '{performed_by}'"
        )
        logger.info(f"School '{school_code}' → status: '{new_status}'")
        return True

    except Exception as e:
        logger.error(f"update_school_status error: {e}")
        return False


def update_school_info(
    school_code:   str,
    school_name:   Optional[str] = None,
    contact_email: Optional[str] = None,
    address:       Optional[str] = None,
    phone:         Optional[str] = None,
    logo_path:     Optional[str] = None,
    performed_by:  str = "system",
) -> bool:
    """
    Update editable school metadata. Only non-None fields are changed.

    Note: school_code and email_domain are intentionally not editable here
    because they are structural identifiers tied to the DB filename and
    login routing. Contact support to change those.

    Args:
        school_code:   School to update (lookup key — not changeable)
        school_name:   New display name
        contact_email: New contact email
        address:       New address
        phone:         New phone number
        logo_path:     New logo file path
        performed_by:  Actor for audit log

    Returns:
        True if updated, False if not found or no fields provided
    """
    fields = {
        "school_name":   school_name,
        "contact_email": contact_email,
        "address":       address,
        "phone":         phone,
        "logo_path":     logo_path,
    }
    updates = {k: v for k, v in fields.items() if v is not None}

    if not updates:
        logger.warning("update_school_info: no fields to update")
        return False

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values     = list(updates.values()) + [school_code.lower().strip()]

    try:
        conn = get_master_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE schools SET {set_clause}, updated_at = CURRENT_TIMESTAMP "
            f"WHERE school_code = ?",
            values
        )
        affected = cursor.rowcount
        conn.commit()
        conn.close()

        if affected == 0:
            logger.warning(f"update_school_info: '{school_code}' not found")
            return False

        log_school_action(
            school_code, "INFO_UPDATED", performed_by,
            f"Fields updated: {list(updates.keys())}"
        )
        logger.info(f"School '{school_code}' info updated: {list(updates.keys())}")
        return True

    except Exception as e:
        logger.error(f"update_school_info error: {e}")
        return False


# ─────────────────────────────────────────────
# DELETE
# ─────────────────────────────────────────────

def delete_school(
    school_code:   str,
    delete_db_file: bool = False,
    performed_by:  str = "system",
) -> bool:
    """
    Delete a school from master.db.

    Args:
        school_code:    School to delete
        delete_db_file: If True, also deletes the school's .db file from disk.
                        Defaults to False — data is preserved unless explicitly
                        requested. This is irreversible.
        performed_by:   Actor for audit log

    Returns:
        True if deleted, False if not found or error
    """
    try:
        school = get_school_by_code(school_code)
        if school is None:
            logger.warning(f"delete_school: '{school_code}' not found")
            return False

        db_path = get_school_db_path(school_code)

        conn = get_master_connection()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM schools WHERE school_code = ?",
            (school_code.lower().strip(),)
        )
        conn.commit()
        conn.close()

        if delete_db_file and os.path.exists(db_path):
            os.remove(db_path)
            logger.warning(f"School database file deleted: {db_path}")

        log_school_action(
            school_code, "DELETED", performed_by,
            f"School '{school['school_name']}' deleted. "
            f"DB file {'deleted' if delete_db_file else 'preserved'}: {db_path}"
        )
        logger.info(f"School '{school_code}' deleted from master DB")
        return True

    except Exception as e:
        logger.error(f"delete_school error: {e}")
        return False


# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────

def _initialize_school_database(db_path: str) -> None:
    """Create all application tables in the new school database."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    from database.schema import create_tables
    create_tables(db_path=db_path)
    logger.info(f"School database initialised: {db_path}")


def _create_school_default_users(
    db_path: str,
    school_code: str,
    email_domain: str,
) -> None:
    """
    Seed superadmin and admin accounts into a fresh school database.

    Default credentials (must be changed after first login):
      superadmin@<domain> / superadmin
      admin@<domain>      / admin
    """
    from database.connection import get_connection

    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        for username, password, role in [
            ("superadmin", "superadmin", "superadmin"),
            ("admin",      "admin",      "admin"),
        ]:
            email = f"{username}@{email_domain}"
            cursor.execute("""
                INSERT OR IGNORE INTO users (username, password, email, role)
                VALUES (?, ?, ?, ?)
            """, (username, password, email, role))

        conn.commit()
        logger.info(f"Default users seeded for school '{school_code}'")
    except Exception as e:
        conn.rollback()
        logger.warning(f"Could not seed default users for '{school_code}': {e}")
    finally:
        conn.close()
