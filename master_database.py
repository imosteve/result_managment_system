# master_database.py  — FINAL VERSION
"""
Master database for multi-tenant school management.

Tables:
  schools            — one row per registered school
  school_audit_log   — immutable log of all platform-level actions
  platform_admins    — platform-level superadmin accounts
                       (live in master.db, NOT in any school DB)

Platform superadmin login flow:
  - Email domain is checked against platform_admins first
  - If found, authenticate against master.db directly
  - No school session is set — they see the Platform Admin panel only
  - A default platform superadmin is seeded on first startup

status column (schools):  'active' | 'inactive'
  • Only active schools can be logged into.
  • Deactivating does NOT delete the database file.
  • Reactivating restores access immediately.
"""

import sqlite3
import os
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

MASTER_DB_PATH = os.path.join("data", "master.db")
SCHOOLS_DB_DIR = os.path.join("data", "schools")

# Default platform superadmin credentials — CHANGE ON FIRST LOGIN
_DEFAULT_PLATFORM_ADMIN_EMAIL    = os.getenv("PLATFORM_ADMIN_EMAIL",    "admin@rms.com")
_DEFAULT_PLATFORM_ADMIN_PASSWORD = os.getenv("PLATFORM_ADMIN_PASSWORD", "admin")


# ─────────────────────────────────────────────
# Connection
# ─────────────────────────────────────────────

def get_master_connection() -> sqlite3.Connection:
    """Get a connection to the master database (never a school DB)"""
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(MASTER_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ─────────────────────────────────────────────
# Master DB initialisation
# ─────────────────────────────────────────────

def create_master_tables():
    """
    Create master database tables and seed the default platform superadmin.

    Safe to call on every app startup — all DDL uses CREATE IF NOT EXISTS.
    The platform superadmin is only inserted when the table is empty,
    so repeated startups are idempotent.
    """
    conn = get_master_connection()
    cursor = conn.cursor()

    # ── Schools ───────────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schools (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            school_name   TEXT    NOT NULL,
            school_code   TEXT    UNIQUE NOT NULL,
            email_domain  TEXT    UNIQUE NOT NULL,
            database_name TEXT    NOT NULL,
            contact_email TEXT,
            address       TEXT,
            phone         TEXT,
            logo_path     TEXT,
            status        TEXT    NOT NULL DEFAULT 'active'
                              CHECK(status IN ('active', 'inactive')),
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Audit log ─────────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS school_audit_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            school_code  TEXT NOT NULL,
            action       TEXT NOT NULL,
            performed_by TEXT,
            details      TEXT,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Platform admins ───────────────────────────────────────────────────
    # These are NOT school users — they live only in master.db and can
    # register / manage schools via the Platform Admin panel.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS platform_admins (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            email      TEXT    UNIQUE NOT NULL,
            username   TEXT    UNIQUE NOT NULL,
            password   TEXT    NOT NULL,
            role       TEXT    NOT NULL DEFAULT 'platform_superadmin'
                           CHECK(role IN ('platform_superadmin')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()

    # ── Seed default platform superadmin (first startup only) ────────────
    _seed_default_platform_admin(conn)

    conn.close()
    logger.info("Master database tables initialised")


def _seed_default_platform_admin(conn: sqlite3.Connection):
    """
    Insert the default platform superadmin if the table is empty.

    Called once at first startup. Subsequent startups skip the insert
    because the table will already have a row.

    Default credentials come from environment variables so they can be
    overridden before deployment:
      PLATFORM_ADMIN_EMAIL    (default: admin@platform.com)
      PLATFORM_ADMIN_PASSWORD (default: platform_admin)

    The operator MUST change these after first login.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM platform_admins")
    count = cursor.fetchone()[0]

    if count == 0:
        cursor.execute("""
            INSERT INTO platform_admins (email, username, password, role)
            VALUES (?, ?, ?, 'platform_superadmin')
        """, (
            _DEFAULT_PLATFORM_ADMIN_EMAIL.lower().strip(),
            "platform_admin",
            _DEFAULT_PLATFORM_ADMIN_PASSWORD,
        ))
        conn.commit()
        logger.warning(
            f"Default platform superadmin seeded: "
            f"email='{_DEFAULT_PLATFORM_ADMIN_EMAIL}' — "
            "CHANGE THIS PASSWORD IMMEDIATELY."
        )
    else:
        logger.debug("Platform admin already exists — skipping seed")


# ─────────────────────────────────────────────
# Platform admin lookup  (used in login.py)
# ─────────────────────────────────────────────

def get_platform_admin_by_email(email: str) -> Optional[Dict[str, Any]]:
    """
    Look up a platform admin by email address.

    Called by login.py BEFORE school resolution so that platform admins
    can log in without needing a registered school email domain.

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


def update_platform_admin_password(email: str, new_password: str) -> bool:
    """Update a platform admin's password"""
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
        return affected > 0
    except Exception as e:
        logger.error(f"Error updating platform admin password: {e}")
        return False


# ─────────────────────────────────────────────
# School lookup
# ─────────────────────────────────────────────

def get_school_by_domain(email_domain: str) -> Optional[Dict[str, Any]]:
    """
    Look up an ACTIVE school by email domain.
    Primary lookup called during login — returns None if inactive.
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
        logger.error(f"Error looking up school by domain '{email_domain}': {e}")
        return None


def get_school_by_code(school_code: str,
                        active_only: bool = False) -> Optional[Dict[str, Any]]:
    """
    Look up a school by its unique code.

    Args:
        school_code: e.g. 'greenfield'
        active_only: If True returns None for inactive schools.
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
        logger.error(f"Error looking up school by code '{school_code}': {e}")
        return None


def get_all_schools() -> List[Dict[str, Any]]:
    """Return all schools (active and inactive) for the platform admin panel"""
    try:
        conn = get_master_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM schools ORDER BY school_name")
        results = cursor.fetchall()
        conn.close()
        return [dict(r) for r in results]
    except Exception as e:
        logger.error(f"Error fetching all schools: {e}")
        return []


def get_school_db_path(school_code: str) -> str:
    """Return the filesystem path to a school's SQLite database"""
    return os.path.join(SCHOOLS_DB_DIR, f"{school_code}.db")


# ─────────────────────────────────────────────
# Email → school resolution  (used in login.py)
# ─────────────────────────────────────────────

def resolve_school_from_email(email: str) -> Optional[Dict[str, Any]]:
    """
    Extract domain from an email and return the matching ACTIVE school.

    NOTE: login.py calls get_platform_admin_by_email() FIRST.
    This function is only called when the email is NOT a platform admin.

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
# School registration
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

    The database file is created ONCE here. Status / deactivation
    changes never touch the file — only the master DB record.

    Raises:
        ValueError:      school_code or email_domain already in master DB
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

    # 1. Write master DB record first (fail fast on duplicate code/domain)
    conn = get_master_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
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

    # 2. Create the school's database (exactly once)
    _initialize_school_database(db_path)

    # 3. Seed default users into the new database
    _create_school_default_users(db_path, school_code, email_domain)

    # 4. Audit log
    _log_school_action(
        school_code, "REGISTERED", performed_by,
        f"'{school_name}' registered — domain: '{email_domain}', db: '{db_path}'"
    )

    logger.info(f"School '{school_name}' registered: {db_path}")
    return {"school_code": school_code, "db_path": db_path, "db_name": db_name}


# ─────────────────────────────────────────────
# Status management
# ─────────────────────────────────────────────

def update_school_status(
    school_code:  str,
    new_status:   str,
    performed_by: str = "system",
) -> bool:
    """
    Activate or deactivate a school.

    Does NOT touch the school's database file — only updates the
    master DB record. Inactive schools are rejected at login.
    """
    if new_status not in ("active", "inactive"):
        logger.error(f"Invalid status value: '{new_status}'")
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
            logger.warning(f"No school found with code '{school_code}'")
            return False

        _log_school_action(
            school_code,
            f"STATUS_CHANGED_TO_{new_status.upper()}",
            performed_by,
            f"Status set to '{new_status}' by '{performed_by}'"
        )
        logger.info(f"School '{school_code}' → status: '{new_status}'")
        return True

    except Exception as e:
        logger.error(f"Error updating status for '{school_code}': {e}")
        return False


# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────

def _initialize_school_database(db_path: str):
    """
    Create all application tables in the new school database.
    Delegates to database/schema.py — single source of truth for schema.
    """
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    from database.schema import create_tables
    create_tables(db_path=db_path)
    logger.info(f"School database initialised: {db_path}")


def _create_school_default_users(db_path: str, school_code: str, email_domain: str):
    """
    Seed superadmin and admin accounts into a fresh school database.
    Matches the two-table schema (users + admin_users).

    Default credentials (must be changed immediately after first login):
      superadmin / superadmin
      admin      / admin
    """
    from database.connection import get_connection

    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        for username, password, email, role in [
            ("superadmin", "superadmin", f"superadmin@{email_domain}", "superadmin"),
            ("admin", "admin", f"admin@{email_domain}", "admin"),
        ]:
            cursor.execute(
                "INSERT OR IGNORE INTO users (username, password, email) VALUES (?, ?, ?)",
                (username, password, email)
            )
            user_id = cursor.lastrowid
            if user_id:
                cursor.execute(
                    "INSERT OR IGNORE INTO admin_users (user_id, role) VALUES (?, ?)",
                    (user_id, role)
                )
        conn.commit()
        logger.info(f"Default users seeded for school '{school_code}'")
    except Exception as e:
        conn.rollback()
        logger.warning(f"Could not seed default users for '{school_code}': {e}")
    finally:
        conn.close()


def _log_school_action(
    school_code:  str,
    action:       str,
    performed_by: str,
    details:      str = "",
):
    """Append an immutable entry to school_audit_log"""
    try:
        conn = get_master_connection()
        conn.execute("""
            INSERT INTO school_audit_log
                (school_code, action, performed_by, details)
            VALUES (?, ?, ?, ?)
        """, (school_code, action, performed_by, details))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Audit log write failed: {e}")