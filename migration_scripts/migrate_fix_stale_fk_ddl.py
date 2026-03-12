# migrations/migrate_fix_stale_fk_ddl.py
#
# ROOT CAUSE: SQLite stores CREATE TABLE DDL as text in sqlite_master.
# When migrate_old_database() ran, it renamed classes→_classes_old and
# students→_students_old. Even after renaming them back, OTHER tables
# (class_sessions, class_session_students) still have DDL in sqlite_master
# that says REFERENCES _classes_old / _students_old.
#
# SQLite FK enforcement reads those DDL strings at runtime — so it tries
# to find _classes_old and _students_old, fails, and raises:
#   "no such table: main._classes_old"
#
# FIX: Rebuild every affected table using the correct DDL via the
#      rename-recreate-copy-drop pattern with FK OFF.

import sqlite3
import shutil
import logging
import sys
import os

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = r"C:\Users\imosteve\Documents\Result system\python system\student_results_app\data\suis.db"


def get_stale_tables(conn):
    """Find tables whose DDL references _classes_old or _students_old."""
    rows = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table'"
    ).fetchall()
    stale = []
    for name, sql in rows:
        if sql and ("_classes_old" in sql or "_students_old" in sql):
            stale.append((name, sql))
    return stale


def fix(db_path: str) -> None:
    # ── Backup first ──────────────────────────────────────────────
    backup = db_path + ".bak2"
    shutil.copy2(db_path, backup)
    logger.info(f"Backup created: {backup}")

    conn = sqlite3.connect(db_path)

    # ── Diagnose ──────────────────────────────────────────────────
    stale = get_stale_tables(conn)
    if not stale:
        logger.info("No stale FK DDL found — DB is clean.")

        # Secondary check: run fk_check to see if SQLite still complains
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            conn.execute("SELECT COUNT(*) FROM class_sessions")
            conn.execute("SELECT COUNT(*) FROM class_session_students")
            logger.info("FK queries succeed — no action needed.")
        except Exception as e:
            logger.error(f"Query still fails even with no stale DDL: {e}")
            logger.error("The issue may be elsewhere. Check utils.py for migrate_old_database() calls.")
        conn.close()
        return

    logger.warning(f"Stale DDL found in {len(stale)} table(s): {[t[0] for t in stale]}")
    for name, sql in stale:
        logger.info(f"  {name}: ...{sql[sql.find('REFERENCES'):][:120]}...")

    # ── Correct DDL for each affected table ───────────────────────
    # We rebuild each table with correct REFERENCES to classes / students.
    # Add any tables that appear in the stale list.

    CORRECT_DDL = {
        "class_sessions": """
            CREATE TABLE class_sessions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                class_name TEXT    NOT NULL
                               REFERENCES classes(class_name)
                               ON DELETE CASCADE
                               ON UPDATE CASCADE,
                session    TEXT    NOT NULL
                               REFERENCES sessions(session)
                               ON DELETE CASCADE
                               ON UPDATE CASCADE,
                is_active  INTEGER NOT NULL DEFAULT 1
                               CHECK(is_active IN (0, 1)),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(class_name, session)
            )
        """,
        "class_session_students": """
            CREATE TABLE class_session_students (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                class_session_id INTEGER NOT NULL
                                     REFERENCES class_sessions(id)
                                     ON DELETE CASCADE
                                     ON UPDATE CASCADE,
                student_name     TEXT    NOT NULL
                                     REFERENCES students(student_name)
                                     ON DELETE CASCADE
                                     ON UPDATE CASCADE,
                class_name       TEXT    NOT NULL,
                session          TEXT    NOT NULL,
                enrollment_date  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(class_session_id, student_name)
            )
        """,
        "subjects": """
            CREATE TABLE subjects (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                class_name     TEXT    NOT NULL
                                   REFERENCES classes(class_name)
                                   ON DELETE CASCADE
                                   ON UPDATE CASCADE,
                subject_name   TEXT    NOT NULL,
                max_ca_score   REAL    NOT NULL DEFAULT 30,
                max_exam_score REAL    NOT NULL DEFAULT 70,
                created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(class_name, subject_name)
            )
        """,
        "scores": """
            CREATE TABLE scores (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                enrollment_id INTEGER NOT NULL
                                  REFERENCES class_session_students(id)
                                  ON DELETE CASCADE
                                  ON UPDATE CASCADE,
                student_name  TEXT    NOT NULL,
                class_name    TEXT    NOT NULL,
                session       TEXT    NOT NULL,
                term          TEXT    NOT NULL
                                  CHECK(term IN ('First', 'Second', 'Third')),
                subject_name  TEXT    NOT NULL,
                ca_score      REAL    NOT NULL DEFAULT 0,
                exam_score    REAL    NOT NULL DEFAULT 0,
                total_score   REAL    GENERATED ALWAYS AS (ca_score + exam_score) STORED,
                grade         TEXT,
                position      INTEGER,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_by    TEXT,
                UNIQUE(enrollment_id, subject_name, term)
            )
        """,
        "psychomotor_ratings": """
            CREATE TABLE psychomotor_ratings (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                enrollment_id    INTEGER NOT NULL
                                     REFERENCES class_session_students(id)
                                     ON DELETE CASCADE
                                     ON UPDATE CASCADE,
                student_name     TEXT    NOT NULL,
                class_name       TEXT    NOT NULL,
                session          TEXT    NOT NULL,
                term             TEXT    NOT NULL
                                     CHECK(term IN ('First', 'Second', 'Third')),
                punctuality      INTEGER CHECK(punctuality      BETWEEN 1 AND 5),
                neatness         INTEGER CHECK(neatness         BETWEEN 1 AND 5),
                honesty          INTEGER CHECK(honesty          BETWEEN 1 AND 5),
                cooperation      INTEGER CHECK(cooperation      BETWEEN 1 AND 5),
                leadership       INTEGER CHECK(leadership       BETWEEN 1 AND 5),
                perseverance     INTEGER CHECK(perseverance     BETWEEN 1 AND 5),
                politeness       INTEGER CHECK(politeness       BETWEEN 1 AND 5),
                obedience        INTEGER CHECK(obedience        BETWEEN 1 AND 5),
                attentiveness    INTEGER CHECK(attentiveness    BETWEEN 1 AND 5),
                attitude_to_work INTEGER CHECK(attitude_to_work BETWEEN 1 AND 5),
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(enrollment_id, term)
            )
        """,
        "comments": """
            CREATE TABLE comments (
                id                          INTEGER PRIMARY KEY AUTOINCREMENT,
                enrollment_id               INTEGER NOT NULL
                                                REFERENCES class_session_students(id)
                                                ON DELETE CASCADE
                                                ON UPDATE CASCADE,
                student_name                TEXT    NOT NULL,
                class_name                  TEXT    NOT NULL,
                session                     TEXT    NOT NULL,
                term                        TEXT    NOT NULL
                                                CHECK(term IN ('First', 'Second', 'Third')),
                class_teacher_comment       TEXT,
                head_teacher_comment        TEXT,
                head_teacher_comment_custom INTEGER NOT NULL DEFAULT 0
                                                CHECK(head_teacher_comment_custom IN (0, 1)),
                created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(enrollment_id, term)
            )
        """,
        "student_subject_selections": """
            CREATE TABLE student_subject_selections (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                enrollment_id INTEGER NOT NULL
                                  REFERENCES class_session_students(id)
                                  ON DELETE CASCADE
                                  ON UPDATE CASCADE,
                student_name  TEXT    NOT NULL,
                class_name    TEXT    NOT NULL,
                session       TEXT    NOT NULL,
                term          TEXT    NOT NULL
                                  CHECK(term IN ('First', 'Second', 'Third')),
                subject_name  TEXT    NOT NULL,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(enrollment_id, subject_name, term)
            )
        """,
    }

    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("BEGIN")

    try:
        for table_name, _ in stale:
            if table_name not in CORRECT_DDL:
                logger.warning(f"No correct DDL defined for '{table_name}' — skipping.")
                continue

            tmp = f"__{table_name}_tmp"
            logger.info(f"Rebuilding {table_name}...")

            # 1. Get current column names
            cols = [
                row[1] for row in
                conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            ]
            col_list = ", ".join(f'"{c}"' for c in cols)

            # 2. Rename current → tmp
            conn.execute(f'ALTER TABLE "{table_name}" RENAME TO "{tmp}"')

            # 3. Create with correct DDL
            conn.execute(CORRECT_DDL[table_name])

            # 4. Copy data
            conn.execute(f'INSERT INTO "{table_name}" ({col_list}) SELECT {col_list} FROM "{tmp}"')

            # 5. Drop tmp
            conn.execute(f'DROP TABLE "{tmp}"')

            logger.info(f"  ✅ {table_name} rebuilt with correct FK references")

        conn.execute("PRAGMA foreign_keys = ON")
        conn.commit()
        logger.info("\nAll stale FK DDL repaired successfully.")

    except Exception as e:
        conn.rollback()
        logger.error(f"Repair failed, rolled back: {e}")
        logger.error(f"Your backup is at: {backup}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print(f"Error: database not found at:\n  {DB_PATH}")
        sys.exit(1)

    fix(DB_PATH)
    print("\nDone. Restart your Streamlit app.")
