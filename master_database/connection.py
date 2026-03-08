# master_database/connection.py
"""
Master database connection factory.
All modules import get_master_connection() from here — never hardcode the path.
"""

import os
import sqlite3
import logging

logger = logging.getLogger(__name__)

MASTER_DB_PATH = os.path.join("data", "master.db")
SCHOOLS_DB_DIR = os.path.join("data", "schools")


def get_master_connection() -> sqlite3.Connection:
    """
    Return a connection to master.db with Row factory and FK enforcement.
    Creates the data/ directory if it does not exist.
    """
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(MASTER_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn
