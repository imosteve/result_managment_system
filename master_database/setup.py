# master_database/setup.py
"""
Master database table creation and first-run seeding.
Called once at app startup from app_manager.py or main.py.
All DDL uses CREATE IF NOT EXISTS — safe to call on every startup.
"""

import logging
from .connection import get_master_connection
from .platform_admins import _seed_default_platform_admin

logger = logging.getLogger(__name__)


def create_master_tables() -> None:
    """
    Create all master database tables and seed the default platform superadmin.

    Tables created:
      schools           — one row per registered school
      school_audit_log  — immutable platform action log
      platform_admins   — platform-level admin accounts

    Safe to call on every app startup — idempotent.
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

    # ── Seed default platform superadmin on first run ─────────────────────
    _seed_default_platform_admin(conn)

    conn.close()
    logger.info("Master database tables initialised")
