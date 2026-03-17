#!/usr/bin/env python3
"""
migrate_add_score_system_table.py
──────────────────────────────────
Adds the class_term_score_systems table to suis.db.

Safe to run multiple times — uses CREATE TABLE IF NOT EXISTS.
No existing data is altered. All classes will show is_set=False
until an admin sets the system in Manage Classes → 📐 Score System.

Run from anywhere:
    python migrate_add_score_system_table.py
"""

import sqlite3
import os
from datetime import datetime

# ── Hardcoded DB path ─────────────────────────────────────────────────────────
DB_PATH = r"C:\Users\imosteve\Documents\Result system\python system\student_results_app\data\suis.db"

# ── DDL ───────────────────────────────────────────────────────────────────────
CREATE_SQL = """
CREATE TABLE IF NOT EXISTS class_term_score_systems (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    class_name     TEXT    NOT NULL
                       REFERENCES classes(class_name)
                       ON DELETE CASCADE ON UPDATE CASCADE,
    term           TEXT    NOT NULL
                       CHECK(term IN ('First', 'Second', 'Third')),
    max_ca_score   REAL    NOT NULL DEFAULT 30
                       CHECK(max_ca_score IN (30, 40)),
    max_exam_score REAL    NOT NULL DEFAULT 70
                       CHECK(max_exam_score IN (70, 60)),
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(class_name, term)
)
"""


def run():
    print("=" * 60)
    print("  Migration: class_term_score_systems")
    print(f"  DB:        {DB_PATH}")
    print(f"  Run at:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # ── Check file exists ─────────────────────────────────────────────────
    if not os.path.exists(DB_PATH):
        print(f"\n❌  Database not found: {DB_PATH}")
        print("    Check the path and try again.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    # ── Check if already migrated ─────────────────────────────────────────
    cursor.execute("""
        SELECT COUNT(*) FROM sqlite_master
        WHERE  type = 'table' AND name = 'class_term_score_systems'
    """)
    if cursor.fetchone()[0] > 0:
        print("\n⏭️   Table already exists — nothing to do.")
        conn.close()
        return

    # ── Run migration ─────────────────────────────────────────────────────
    try:
        conn.execute(CREATE_SQL)
        conn.commit()
        print("\n✅  class_term_score_systems created successfully.")
        print("\n    Next step: go to Manage Classes → 📐 Score System")
        print("    and set the CA/Exam weighting for each class and term.")
    except sqlite3.Error as e:
        conn.rollback()
        print(f"\n❌  Migration failed: {e}")
    finally:
        conn.close()

    print("=" * 60)


if __name__ == "__main__":
    run()