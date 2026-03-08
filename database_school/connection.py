# database/connection.py  — MULTI-TENANT VERSION
"""
Database connection management.

THE ONLY FILE that needed changing for multi-tenancy.
Every other database module (classes.py, users.py, schema.py, etc.)
already calls get_connection() — they all work unchanged.

Resolution priority for which DB to connect to:
  1. Explicit db_path argument  (used during school initialisation)
  2. st.session_state['school_db_path']  (set at login for the active school)
  3. DB_PATH env var / default fallback  (single-tenant / legacy mode)
"""

import sqlite3
import os
import logging
from contextlib import contextmanager
from typing import Optional
import streamlit as st
from config import DB_CONFIG

logger = logging.getLogger(__name__)

# ── Fallback / legacy path (used before any school session is resolved) ───────
DB_PATH    = os.getenv('DATABASE_PATH', st.session_state.get("school_db_path"))
BACKUP_PATH = os.getenv('BACKUP_PATH',  os.path.join("data", "backups"))


# ─────────────────────────────────────────────
# Path resolution
# ─────────────────────────────────────────────

def get_db_path(db_path: Optional[str] = None) -> str:
    """
    Resolve which SQLite file to open, in priority order:

      1. Explicit db_path argument
         → used when initialising a brand-new school database
           (called from master_database._initialize_school_database)

      2. st.session_state['school_db_path']
         → set by SessionManager.create_session() / restore_from_cookies()
           after the user logs in and their school is identified

      3. DB_PATH (env var or default 'data/school.db')
         → backwards-compatible single-tenant fallback
    """
    if db_path:
        return db_path

    # Try Streamlit session state (may not be available outside a Streamlit run)
    try:
        session_path = st.session_state.get("school_db_path")
        if session_path:
            return session_path
    except Exception:
        pass  # Running outside Streamlit context (CLI, tests, migrations)

    return DB_PATH


# ─────────────────────────────────────────────
# Core connection helpers
# ─────────────────────────────────────────────

def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Get a database connection for the resolved school database.

    Args:
        db_path: Optional explicit path. When None, resolves automatically
                 via get_db_path() — reading from session state if available.

    Returns:
        sqlite3.Connection with Row factory and foreign keys enabled.
    """
    path = get_db_path(db_path)
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_db_connection(db_path: Optional[str] = None):
    """
    Context manager for database connections with automatic commit/rollback.

    Args:
        db_path: Optional explicit path (same resolution rules as get_connection).

    Usage:
        with get_db_connection() as conn:          # uses active school from session
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")

        with get_db_connection(db_path=some_path) as conn:   # explicit path
            ...

    Yields:
        sqlite3.Connection
    """
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
