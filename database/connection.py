# database/__init__.py

"""Database connection management"""

import sqlite3
import os
import logging
from contextlib import contextmanager

# Configuration
DB_PATH = os.getenv('DATABASE_PATH', os.path.join("data", "school.db"))
BACKUP_PATH = os.getenv('BACKUP_PATH', os.path.join("backups"))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_connection():
    """
    Get database connection with foreign keys enabled
    
    Returns:
        sqlite3.Connection: Database connection with Row factory
    """
    os.makedirs("data", exist_ok=True)
    os.makedirs("data/backups", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_db_connection():
    """
    Context manager for database connections with automatic commit/rollback
    
    Usage:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
    
    Yields:
        sqlite3.Connection: Database connection
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()