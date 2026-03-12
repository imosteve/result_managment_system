# migration_scripts/migrate_per_term_enrollment.py
#
# Migrates class_session_students from session-level to per-term enrollment.
#
# WHAT CHANGES:
#   class_session_students gains a `term` column.
#   UNIQUE changes from (class_session_id, student_name)
#                    to (class_session_id, student_name, term)
#
# EXISTING DATA:
#   Every existing enrollment row is expanded into 3 rows (First, Second, Third).
#
# DOWNSTREAM (scores, comments, psychomotor_ratings, student_subject_selections):
#   Each row already has a `term` column. We use it to pick the correct
#   new enrollment_id.  We do this by temporarily dropping UNIQUE constraints
#   (rename-recreate pattern) so the UPDATE never hits a conflict.

import sqlite3
import shutil
import logging
import sys
import os

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = r"C:\Users\imosteve\Documents\Result system\python system\student_results_app\data\suis.db"
TERMS   = ("First", "Second", "Third")


def already_migrated(conn) -> bool:
    cols = [r[1] for r in conn.execute("PRAGMA table_info(class_session_students)").fetchall()]
    return "term" in cols


def rebuild_table(conn, table: str, new_ddl: str, columns: list):
    """
    Rename → recreate with new DDL → copy data → drop old.
    Avoids all UNIQUE constraint conflicts during the copy because
    we're inserting into a fresh table.
    """
    tmp = f"__{table}_mig"
    col_list = ", ".join(f'"{c}"' for c in columns)
    conn.execute(f'ALTER TABLE "{table}" RENAME TO "{tmp}"')
    conn.execute(new_ddl)
    conn.execute(f'INSERT INTO "{table}" ({col_list}) SELECT {col_list} FROM "{tmp}"')
    conn.execute(f'DROP TABLE "{tmp}"')
    logger.info(f"  {table}: rebuilt with new DDL")


def migrate(db_path: str) -> None:
    backup = db_path + ".pre_term_migration.bak"
    shutil.copy2(db_path, backup)
    logger.info(f"Backup created: {backup}")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = OFF")

    if already_migrated(conn):
        logger.info("Already migrated — term column exists. Nothing to do.")
        conn.close()
        return

    logger.info("Starting per-term enrollment migration...")

    try:
        conn.execute("BEGIN")

        # ── 1. Read all existing enrollments ─────────────────────────────────
        rows = conn.execute("""
            SELECT id, class_session_id, student_name, class_name, session, enrollment_date
            FROM   class_session_students
        """).fetchall()
        logger.info(f"Found {len(rows)} enrollment(s) → expanding to {len(rows) * 3}")

        # ── 2. Rename old enrollment table ───────────────────────────────────
        conn.execute("ALTER TABLE class_session_students RENAME TO _css_old")

        # ── 3. Create new enrollment table with term ──────────────────────────
        conn.execute("""
            CREATE TABLE class_session_students (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                class_session_id INTEGER NOT NULL
                                     REFERENCES class_sessions(id)
                                     ON DELETE CASCADE ON UPDATE CASCADE,
                student_name     TEXT    NOT NULL
                                     REFERENCES students(student_name)
                                     ON DELETE CASCADE ON UPDATE CASCADE,
                class_name       TEXT    NOT NULL,
                session          TEXT    NOT NULL,
                term             TEXT    NOT NULL
                                     CHECK(term IN ('First', 'Second', 'Third')),
                enrollment_date  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(class_session_id, student_name, term)
            )
        """)

        # ── 4. Expand each old row into 3 term rows ───────────────────────────
        # old_id → {term: new_id}
        old_to_new = {}

        for (old_id, cs_id, student_name, class_name, session, enroll_date) in rows:
            old_to_new[old_id] = {}
            for term in TERMS:
                conn.execute("""
                    INSERT INTO class_session_students
                        (class_session_id, student_name, class_name, session, term, enrollment_date)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (cs_id, student_name, class_name, session, term, enroll_date))
                new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                old_to_new[old_id][term] = new_id

        logger.info("Enrollment rows expanded.")

        # ── 5. Remap downstream tables ────────────────────────────────────────
        # Strategy: for each downstream table, load all rows into memory,
        # rebuild the table fresh (no UNIQUE conflicts), then reinsert with
        # corrected enrollment_ids.

        downstream_ddl = {
            "scores": (
                ["enrollment_id", "student_name", "class_name", "session",
                 "term", "subject_name", "ca_score", "exam_score",
                 "grade", "position", "created_at", "updated_at", "updated_by"],
                """CREATE TABLE scores (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    enrollment_id INTEGER NOT NULL
                                      REFERENCES class_session_students(id)
                                      ON DELETE CASCADE ON UPDATE CASCADE,
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
                )"""
            ),
            "comments": (
                ["enrollment_id", "student_name", "class_name", "session", "term",
                 "class_teacher_comment", "head_teacher_comment",
                 "head_teacher_comment_custom", "created_at", "updated_at"],
                """CREATE TABLE comments (
                    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
                    enrollment_id               INTEGER NOT NULL
                                                    REFERENCES class_session_students(id)
                                                    ON DELETE CASCADE ON UPDATE CASCADE,
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
                )"""
            ),
            "psychomotor_ratings": (
                ["enrollment_id", "student_name", "class_name", "session", "term",
                 "punctuality", "neatness", "honesty", "cooperation",
                 "leadership", "perseverance", "politeness", "obedience",
                 "attentiveness", "attitude_to_work", "created_at", "updated_at"],
                """CREATE TABLE psychomotor_ratings (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    enrollment_id    INTEGER NOT NULL
                                         REFERENCES class_session_students(id)
                                         ON DELETE CASCADE ON UPDATE CASCADE,
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
                )"""
            ),
            "student_subject_selections": (
                ["enrollment_id", "student_name", "class_name", "session",
                 "term", "subject_name", "created_at"],
                """CREATE TABLE student_subject_selections (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    enrollment_id INTEGER NOT NULL
                                      REFERENCES class_session_students(id)
                                      ON DELETE CASCADE ON UPDATE CASCADE,
                    student_name  TEXT    NOT NULL,
                    class_name    TEXT    NOT NULL,
                    session       TEXT    NOT NULL,
                    term          TEXT    NOT NULL
                                      CHECK(term IN ('First', 'Second', 'Third')),
                    subject_name  TEXT    NOT NULL,
                    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(enrollment_id, subject_name, term)
                )"""
            ),
        }

        for table, (columns, new_ddl) in downstream_ddl.items():
            exists = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if not exists:
                logger.info(f"  {table}: does not exist, skipping")
                continue

            # Load all existing rows
            col_list = ", ".join(f'"{c}"' for c in columns)
            existing = conn.execute(
                f'SELECT {col_list} FROM "{table}"'
            ).fetchall()

            # Build corrected rows — swap enrollment_id using old_to_new map
            corrected = []
            skipped = 0
            for row in existing:
                row = list(row)
                old_enrollment_id = row[0]   # enrollment_id is always first
                term_val = row[4]            # term is always index 4 in all these tables

                if old_enrollment_id in old_to_new and term_val in old_to_new[old_enrollment_id]:
                    row[0] = old_to_new[old_enrollment_id][term_val]
                    corrected.append(row)
                else:
                    skipped += 1
                    logger.warning(
                        f"  {table}: could not remap enrollment_id={old_enrollment_id} "
                        f"term={term_val} — row skipped"
                    )

            # Deduplicate: keep last row per UNIQUE key to avoid constraint errors
            # (handles edge case where old data had duplicates)
            seen = {}
            for row in corrected:
                enrollment_id = row[0]
                term_val      = row[4]
                subject_name  = row[5] if len(row) > 5 and table in ("scores", "student_subject_selections") else None
                key = (enrollment_id, subject_name, term_val) if subject_name is not None else (enrollment_id, term_val)
                seen[key] = row   # last one wins
            deduped = list(seen.values())

            if len(deduped) < len(corrected):
                logger.warning(
                    f"  {table}: deduplicated {len(corrected) - len(deduped)} duplicate row(s)"
                )

            # Rename old table → recreate fresh → insert corrected rows
            tmp = f"__{table}_mig"
            conn.execute(f'ALTER TABLE "{table}" RENAME TO "{tmp}"')
            conn.execute(new_ddl)

            placeholders = ", ".join("?" for _ in columns)
            conn.executemany(
                f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders})',
                deduped
            )
            conn.execute(f'DROP TABLE "{tmp}"')
            logger.info(
                f"  {table}: {len(deduped)} row(s) migrated "
                f"({skipped} skipped, {len(corrected) - len(deduped)} deduped)"
            )

        # ── 6. Drop old enrollment table ──────────────────────────────────────
        conn.execute("DROP TABLE _css_old")

        # ── 7. Recreate indexes ───────────────────────────────────────────────
        for idx_sql in [
            "CREATE INDEX IF NOT EXISTS idx_css_cs_id       ON class_session_students(class_session_id)",
            "CREATE INDEX IF NOT EXISTS idx_css_student     ON class_session_students(student_name)",
            "CREATE INDEX IF NOT EXISTS idx_css_cls_ses     ON class_session_students(class_name, session)",
            "CREATE INDEX IF NOT EXISTS idx_css_term        ON class_session_students(term)",
            "CREATE INDEX IF NOT EXISTS idx_css_cls_ses_term ON class_session_students(class_name, session, term)",
            "CREATE INDEX IF NOT EXISTS idx_sc_enroll       ON scores(enrollment_id)",
        ]:
            conn.execute(idx_sql)

        conn.execute("PRAGMA foreign_keys = ON")
        conn.commit()
        logger.info("Migration complete ✅")
        logger.info("Run PRAGMA foreign_key_check to verify integrity.")

    except Exception as e:
        conn.rollback()
        logger.error(f"Migration failed, rolled back: {e}")
        logger.error(f"Original DB preserved at: {backup}")
        conn.close()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print(f"ERROR: DB not found: {DB_PATH}")
        sys.exit(1)
    migrate(DB_PATH)
    print("\nDone. Restart your Streamlit app.")