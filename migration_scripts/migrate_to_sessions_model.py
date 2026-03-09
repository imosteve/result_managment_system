# migration_scripts/migrate_to_sessions_model.py
"""
Migration: old flat schema → new session-aware schema.

WHAT THIS DOES (in order)
══════════════════════════
Step 1.  Backup the database.
Step 2.  Rename old conflicting tables FIRST (before creating new ones):
             classes  → classes_OLD
             students → students_OLD
         This is done before new table creation so there's no naming
         collision — both old and new can coexist temporarily.
Step 3.  Create all new tables (sessions, academic_settings, classes,
         subjects, students, class_sessions, teacher_assignments,
         class_session_students, scores [new], etc.)
Step 4.  Migrate sessions — collect distinct session strings from OLD data.
Step 5.  Migrate class definitions — distinct class names from OLD data.
Step 6.  Migrate subjects — copy from old subjects table, strip term/session.
Step 7.  Migrate student master registry — from students_OLD + old scores.
Step 8.  Create class_sessions — one per (class_name, session) pair.
Step 9.  Enroll students — populate class_session_students.
Step 10. Migrate scores:
            - old column test_score → new column ca_score
            - old column exam_score stays exam_score
            - old column total_score is now GENERATED — skip it
            - grade, position copied as-is
Step 11. Migrate comments — add enrollment_id, keep term-keyed data.
Step 12. Migrate psychomotor_ratings — add enrollment_id.
Step 13. Migrate student_subject_selections — add enrollment_id.
Step 14. Set academic_settings to the most recent session / First term.
Step 15. Integrity check.

COLUMN MAPPING (old → new)
══════════════════════════
  Old scores:  student_name, subject_name, class_name, term, session,
               test_score, exam_score, total_score (computed), grade, position
  New scores:  enrollment_id, student_name, class_name, session,
               term, subject_name,
               ca_score (← was test_score), exam_score, total_score (GENERATED),
               grade, position

  Old classes: id, name, term, session   → permanent classes(class_name)
  Old students: id, name, gender, email, school_fees_paid, class_name, term, session
                → students(student_name, gender, email, school_fees_paid)
                + class_session_students(enrollment)

SAFETY
══════
• A timestamped .bak backup is created before any changes.
• Old tables renamed to *_OLD — NEVER deleted. Keep for 30 days.
• Script is restartable — all INSERTs use OR IGNORE.
• Run on a copy of the database first to verify before using on live data.

USAGE
═════
    python migration_scripts/migrate_to_sessions_model.py
    python migration_scripts/migrate_to_sessions_model.py --db data/schools/suis.db
"""

import sqlite3
import sys
import os
import shutil
import argparse
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

# ─────────────────────────────────────────────────────────────────
# DDL for new tables (self-contained — no imports needed)
# ─────────────────────────────────────────────────────────────────

NEW_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session    TEXT    NOT NULL UNIQUE,
    is_active  INTEGER NOT NULL DEFAULT 0 CHECK(is_active IN (0,1)),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS academic_settings (
    id              INTEGER PRIMARY KEY CHECK(id = 1),
    current_session TEXT    NOT NULL DEFAULT '',
    current_term    TEXT    NOT NULL DEFAULT 'First'
                        CHECK(current_term IN ('First','Second','Third')),
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by      TEXT
);
INSERT OR IGNORE INTO academic_settings (id, current_session, current_term)
VALUES (1, '', 'First');

CREATE TABLE IF NOT EXISTS classes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    class_name  TEXT    NOT NULL UNIQUE,
    description TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS subjects (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    class_name     TEXT    NOT NULL
                       REFERENCES classes(class_name)
                       ON DELETE CASCADE ON UPDATE CASCADE,
    subject_name   TEXT    NOT NULL,
    max_ca_score   REAL    NOT NULL DEFAULT 40,
    max_exam_score REAL    NOT NULL DEFAULT 60,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(class_name, subject_name)
);

CREATE TABLE IF NOT EXISTS students (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    student_name     TEXT    NOT NULL UNIQUE,
    gender           TEXT    CHECK(gender IN ('M','F')),
    email            TEXT    UNIQUE,
    date_of_birth    TEXT,
    admission_number TEXT    UNIQUE,
    school_fees_paid TEXT    NOT NULL DEFAULT 'NO'
                         CHECK(school_fees_paid IN ('YES','NO')),
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS class_sessions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    class_name TEXT    NOT NULL
                   REFERENCES classes(class_name)
                   ON DELETE CASCADE ON UPDATE CASCADE,
    session    TEXT    NOT NULL
                   REFERENCES sessions(session)
                   ON DELETE CASCADE ON UPDATE CASCADE,
    is_active  INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(class_name, session)
);

CREATE TABLE IF NOT EXISTS teacher_assignments (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          INTEGER NOT NULL
                         REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE,
    class_session_id INTEGER NOT NULL
                         REFERENCES class_sessions(id) ON DELETE CASCADE ON UPDATE CASCADE,
    class_name       TEXT    NOT NULL,
    session          TEXT    NOT NULL,
    subject_name     TEXT,
    assignment_type  TEXT    NOT NULL
                         CHECK(assignment_type IN ('class_teacher','subject_teacher')),
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, class_session_id, subject_name, assignment_type)
);

CREATE TABLE IF NOT EXISTS class_session_students (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    class_session_id INTEGER NOT NULL
                         REFERENCES class_sessions(id) ON DELETE CASCADE ON UPDATE CASCADE,
    student_name     TEXT    NOT NULL
                         REFERENCES students(student_name) ON DELETE CASCADE ON UPDATE CASCADE,
    class_name       TEXT    NOT NULL,
    session          TEXT    NOT NULL,
    enrollment_date  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(class_session_id, student_name)
);

CREATE TABLE IF NOT EXISTS scores_new (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    enrollment_id INTEGER NOT NULL
                      REFERENCES class_session_students(id) ON DELETE CASCADE ON UPDATE CASCADE,
    student_name  TEXT    NOT NULL,
    class_name    TEXT    NOT NULL,
    session       TEXT    NOT NULL,
    term          TEXT    NOT NULL CHECK(term IN ('First','Second','Third')),
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
);

CREATE TABLE IF NOT EXISTS comments_new (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    enrollment_id               INTEGER NOT NULL
                                    REFERENCES class_session_students(id) ON DELETE CASCADE ON UPDATE CASCADE,
    student_name                TEXT    NOT NULL,
    class_name                  TEXT    NOT NULL,
    session                     TEXT    NOT NULL,
    term                        TEXT    NOT NULL CHECK(term IN ('First','Second','Third')),
    class_teacher_comment       TEXT,
    head_teacher_comment        TEXT,
    head_teacher_comment_custom INTEGER NOT NULL DEFAULT 0
                                    CHECK(head_teacher_comment_custom IN (0,1)),
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(enrollment_id, term)
);

CREATE TABLE IF NOT EXISTS psychomotor_ratings_new (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    enrollment_id    INTEGER NOT NULL
                         REFERENCES class_session_students(id) ON DELETE CASCADE ON UPDATE CASCADE,
    student_name     TEXT    NOT NULL,
    class_name       TEXT    NOT NULL,
    session          TEXT    NOT NULL,
    term             TEXT    NOT NULL CHECK(term IN ('First','Second','Third')),
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
);

CREATE TABLE IF NOT EXISTS student_subject_selections_new (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    enrollment_id INTEGER NOT NULL
                      REFERENCES class_session_students(id) ON DELETE CASCADE ON UPDATE CASCADE,
    student_name  TEXT    NOT NULL,
    class_name    TEXT    NOT NULL,
    session       TEXT    NOT NULL,
    term          TEXT    NOT NULL CHECK(term IN ('First','Second','Third')),
    subject_name  TEXT    NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(enrollment_id, subject_name, term)
);
"""


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def table_exists(cur, name):
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None


def column_exists(cur, table, col):
    cur.execute(f"PRAGMA table_info({table})")
    return any(r[1] == col for r in cur.fetchall())


def get_columns(cur, table):
    cur.execute(f"PRAGMA table_info({table})")
    return [r[1] for r in cur.fetchall()]


def resolve_enrollment_id(cur, student_name, class_name, session):
    cur.execute("""
        SELECT css.id
        FROM   class_session_students css
        JOIN   class_sessions cs ON cs.id = css.class_session_id
        WHERE  css.student_name = ? AND cs.class_name = ? AND cs.session = ?
    """, (student_name, class_name, session))
    row = cur.fetchone()
    return row[0] if row else None


# ─────────────────────────────────────────────────────────────────
# Steps
# ─────────────────────────────────────────────────────────────────

def step_backup(db_path):
    backup_path = f"{db_path}.pre_sessions_{TIMESTAMP}.bak"
    shutil.copy2(db_path, backup_path)
    logger.info(f"✅ Backup: {backup_path}")
    return backup_path


def step_rename_old_tables(cur):
    """
    Rename OLD conflicting tables BEFORE creating new ones.
    This prevents naming collisions.
    """
    logger.info("Renaming old conflicting tables...")
    renames = []

    # classes: old schema has (name TEXT, term TEXT, session TEXT)
    # new schema has (class_name TEXT UNIQUE, description TEXT)
    if table_exists(cur, "classes") and column_exists(cur, "classes", "term"):
        if not table_exists(cur, "classes_OLD"):
            cur.execute("ALTER TABLE classes RENAME TO classes_OLD")
            renames.append("classes → classes_OLD")

    # students: old schema has (name TEXT, class_name TEXT, term TEXT, session TEXT)
    # new schema has (student_name TEXT UNIQUE)
    if table_exists(cur, "students") and column_exists(cur, "students", "class_name"):
        if not table_exists(cur, "students_OLD"):
            cur.execute("ALTER TABLE students RENAME TO students_OLD")
            renames.append("students → students_OLD")

    # subjects: old schema has UNIQUE(name, class_name, term, session)
    # new schema has UNIQUE(class_name, subject_name) — no term/session
    if table_exists(cur, "subjects") and column_exists(cur, "subjects", "term"):
        if not table_exists(cur, "subjects_OLD"):
            cur.execute("ALTER TABLE subjects RENAME TO subjects_OLD")
            renames.append("subjects → subjects_OLD")

    for r in renames:
        logger.info(f"  {r}")
    if not renames:
        logger.info("  (no tables needed renaming)")


def step_create_new_tables(conn):
    logger.info("Creating new tables...")
    conn.executescript(NEW_TABLES_SQL)
    conn.commit()
    logger.info("✅ New tables created")


def step_migrate_sessions(cur):
    logger.info("Migrating sessions...")
    sessions = set()
    for table in ["scores", "comments", "psychomotor_ratings",
                  "students_OLD", "classes_OLD"]:
        if table_exists(cur, table) and column_exists(cur, table, "session"):
            cur.execute(
                f"SELECT DISTINCT session FROM {table} "
                "WHERE session IS NOT NULL AND session != ''"
            )
            sessions.update(r[0] for r in cur.fetchall())

    n = 0
    for s in sorted(sessions):
        cur.execute("INSERT OR IGNORE INTO sessions (session) VALUES (?)", (s,))
        if cur.rowcount:
            n += 1
    logger.info(f"✅ Sessions: {n} inserted → {sorted(sessions)}")
    return sessions


def step_migrate_class_definitions(cur):
    logger.info("Migrating class definitions...")
    class_names = set()

    # From old classes table
    if table_exists(cur, "classes_OLD"):
        cur.execute("SELECT DISTINCT name FROM classes_OLD WHERE name IS NOT NULL")
        class_names.update(r[0] for r in cur.fetchall())

    # From other tables in case classes_OLD didn't exist
    for table in ["scores", "comments", "students_OLD"]:
        if table_exists(cur, table) and column_exists(cur, table, "class_name"):
            cur.execute(
                f"SELECT DISTINCT class_name FROM {table} "
                "WHERE class_name IS NOT NULL AND class_name != ''"
            )
            class_names.update(r[0] for r in cur.fetchall())

    n = 0
    for cn in sorted(class_names):
        cur.execute(
            "INSERT OR IGNORE INTO classes (class_name) VALUES (?)", (cn,)
        )
        if cur.rowcount:
            n += 1
    logger.info(f"✅ Classes: {n} inserted ({len(class_names)} total)")
    return class_names


def step_migrate_subjects(cur):
    """
    OLD subjects: (name, class_name, term, session)
    NEW subjects: (class_name, subject_name) — no term or session.
    We de-duplicate by taking distinct (class_name, name) pairs.
    Max scores default to 40/60 (old schema didn't have these columns).
    """
    logger.info("Migrating subjects...")
    if not table_exists(cur, "subjects_OLD"):
        logger.info("  subjects_OLD not found — skipping")
        return

    cur.execute("SELECT DISTINCT class_name, name FROM subjects_OLD")
    pairs = cur.fetchall()
    n = 0
    for class_name, subject_name in pairs:
        cur.execute(
            "INSERT OR IGNORE INTO subjects (class_name, subject_name) VALUES (?,?)",
            (class_name, subject_name)
        )
        if cur.rowcount:
            n += 1
    logger.info(f"✅ Subjects: {n} inserted ({len(pairs)} total)")


def step_migrate_student_registry(cur):
    """
    OLD students: name, gender, email, school_fees_paid, class_name, term, session
    NEW students: student_name, gender, email, school_fees_paid
    """
    logger.info("Migrating student master registry...")
    rows = []

    if table_exists(cur, "students_OLD"):
        old_cols = get_columns(cur, "students_OLD")
        name_col   = "name" if "name" in old_cols else "student_name"
        gender_col = "gender" if "gender" in old_cols else None
        email_col  = "email"  if "email"  in old_cols else None
        fees_col   = "school_fees_paid" if "school_fees_paid" in old_cols else None

        selects = [f"{name_col} AS student_name"]
        if gender_col: selects.append(f"{gender_col} AS gender")
        if email_col:  selects.append(f"{email_col} AS email")
        if fees_col:   selects.append(f"{fees_col} AS school_fees_paid")

        cur.execute(
            f"SELECT DISTINCT {', '.join(selects)} FROM students_OLD "
            f"WHERE {name_col} IS NOT NULL AND {name_col} != ''"
        )
        rows = cur.fetchall()
        col_names = [d[0] for d in cur.description]

    # Also collect any student_names from scores not already in students_OLD
    if table_exists(cur, "scores") and column_exists(cur, "scores", "student_name"):
        cur.execute(
            "SELECT DISTINCT student_name FROM scores "
            "WHERE student_name IS NOT NULL AND student_name != ''"
        )
        extra = {r[0] for r in cur.fetchall()}
        existing = {r[0] for r in rows} if rows else set()
        for name in extra - existing:
            rows.append((name,))

    n = 0
    for row in rows:
        if isinstance(row, tuple) and len(row) == 1:
            cur.execute(
                "INSERT OR IGNORE INTO students (student_name) VALUES (?)", row
            )
        else:
            row_dict = dict(zip(col_names, row))
            cur.execute("""
                INSERT OR IGNORE INTO students
                    (student_name, gender, email, school_fees_paid)
                VALUES (?, ?, ?, ?)
            """, (
                row_dict.get("student_name"),
                row_dict.get("gender"),
                row_dict.get("email"),
                row_dict.get("school_fees_paid", "NO")
            ))
        if cur.rowcount:
            n += 1
    logger.info(f"✅ Students: {n} inserted")


def step_create_class_sessions(cur):
    """Create class_sessions for every (class_name, session) pair in old data."""
    logger.info("Creating class_sessions...")
    pairs = set()
    for table in ["scores", "comments", "psychomotor_ratings", "students_OLD"]:
        if (table_exists(cur, table)
                and column_exists(cur, table, "class_name")
                and column_exists(cur, table, "session")):
            cur.execute(
                f"SELECT DISTINCT class_name, session FROM {table} "
                "WHERE class_name != '' AND session != ''"
            )
            pairs.update(cur.fetchall())

    n = 0
    for class_name, session in sorted(pairs):
        cur.execute(
            "INSERT OR IGNORE INTO class_sessions (class_name, session) VALUES (?,?)",
            (class_name, session)
        )
        if cur.rowcount:
            n += 1
    logger.info(f"✅ class_sessions: {n} created ({len(pairs)} total)")
    return pairs


def step_enroll_students(cur):
    """
    Populate class_session_students from OLD students table + old scores.
    Collects (student_name, class_name, session) triples.
    """
    logger.info("Enrolling students...")
    triples = set()

    if table_exists(cur, "students_OLD"):
        old_cols = get_columns(cur, "students_OLD")
        name_col = "name" if "name" in old_cols else "student_name"
        if column_exists(cur, "students_OLD", "class_name") and \
           column_exists(cur, "students_OLD", "session"):
            cur.execute(
                f"SELECT DISTINCT {name_col}, class_name, session "
                "FROM students_OLD "
                f"WHERE {name_col} IS NOT NULL AND class_name != '' AND session != ''"
            )
            triples.update(cur.fetchall())

    for table in ["scores", "comments"]:
        if (table_exists(cur, table)
                and column_exists(cur, table, "student_name")
                and column_exists(cur, table, "class_name")
                and column_exists(cur, table, "session")):
            cur.execute(
                f"SELECT DISTINCT student_name, class_name, session FROM {table} "
                "WHERE student_name != '' AND class_name != '' AND session != ''"
            )
            triples.update(cur.fetchall())

    n = 0
    skipped = 0
    for student_name, class_name, session in sorted(triples):
        cur.execute("""
            SELECT id FROM class_sessions WHERE class_name = ? AND session = ?
        """, (class_name, session))
        row = cur.fetchone()
        if not row:
            skipped += 1
            continue
        cs_id = row[0]
        cur.execute("""
            INSERT OR IGNORE INTO class_session_students
                (class_session_id, student_name, class_name, session)
            VALUES (?, ?, ?, ?)
        """, (cs_id, student_name, class_name, session))
        if cur.rowcount:
            n += 1

    logger.info(f"✅ Enrollments: {n} created, {skipped} skipped (missing class_session)")


def step_migrate_scores(cur):
    """
    Migrate old scores to scores_new.

    KEY COLUMN MAPPING:
      old test_score  → new ca_score
      old exam_score  → new exam_score (unchanged)
      old total_score → NOT inserted (GENERATED column, computed by DB)
      old grade, position → copied as-is
    """
    logger.info("Migrating scores...")
    if not table_exists(cur, "scores"):
        logger.info("  No scores table found — skipping")
        return

    old_cols = get_columns(cur, "scores")
    # Determine old score column name (test_score or ca_score)
    if "test_score" in old_cols:
        ca_col = "test_score"
    elif "ca_score" in old_cols:
        ca_col = "ca_score"
    else:
        logger.warning("  Cannot identify CA score column in old scores — skipping")
        return

    grade_sel    = "grade"    if "grade"    in old_cols else "NULL"
    position_sel = "position" if "position" in old_cols else "NULL"

    cur.execute(f"""
        SELECT student_name, subject_name, class_name, term, session,
               {ca_col}, exam_score, {grade_sel}, {position_sel}
        FROM   scores
        WHERE  student_name != '' AND class_name != '' AND session != ''
    """)
    rows = cur.fetchall()

    n = skipped = 0
    for (student_name, subject_name, class_name, term, session,
         ca_score, exam_score, grade, position) in rows:

        enrollment_id = resolve_enrollment_id(cur, student_name, class_name, session)
        if not enrollment_id:
            skipped += 1
            continue

        cur.execute("""
            INSERT OR IGNORE INTO scores_new
                (enrollment_id, student_name, class_name, session,
                 term, subject_name, ca_score, exam_score, grade, position)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (enrollment_id, student_name, class_name, session,
              term, subject_name, ca_score or 0, exam_score or 0,
              grade, position))
        if cur.rowcount:
            n += 1
        else:
            skipped += 1

    logger.info(f"✅ Scores: {n} migrated, {skipped} skipped")


def step_migrate_comments(cur):
    logger.info("Migrating comments...")
    if not table_exists(cur, "comments"):
        logger.info("  No comments table — skipping")
        return

    cur.execute("""
        SELECT student_name, class_name, term, session,
               class_teacher_comment, head_teacher_comment,
               head_teacher_comment_custom
        FROM   comments
        WHERE  student_name != '' AND class_name != '' AND session != ''
    """)
    rows = cur.fetchall()
    n = skipped = 0
    for (student_name, class_name, term, session,
         ct_comment, ht_comment, ht_custom) in rows:
        enrollment_id = resolve_enrollment_id(cur, student_name, class_name, session)
        if not enrollment_id:
            skipped += 1
            continue
        cur.execute("""
            INSERT OR IGNORE INTO comments_new
                (enrollment_id, student_name, class_name, session, term,
                 class_teacher_comment, head_teacher_comment,
                 head_teacher_comment_custom)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (enrollment_id, student_name, class_name, session, term,
              ct_comment, ht_comment, ht_custom or 0))
        if cur.rowcount:
            n += 1
        else:
            skipped += 1
    logger.info(f"✅ Comments: {n} migrated, {skipped} skipped")


def step_migrate_psychomotor(cur):
    logger.info("Migrating psychomotor ratings...")
    if not table_exists(cur, "psychomotor_ratings"):
        logger.info("  No psychomotor_ratings table — skipping")
        return

    cur.execute("""
        SELECT student_name, class_name, term, session,
               punctuality, neatness, honesty, cooperation, leadership,
               perseverance, politeness, obedience, attentiveness, attitude_to_work
        FROM   psychomotor_ratings
        WHERE  student_name != '' AND class_name != '' AND session != ''
    """)
    rows = cur.fetchall()
    n = skipped = 0
    for row in rows:
        (student_name, class_name, term, session,
         punctuality, neatness, honesty, cooperation, leadership,
         perseverance, politeness, obedience, attentiveness, attitude_to_work) = row
        enrollment_id = resolve_enrollment_id(cur, student_name, class_name, session)
        if not enrollment_id:
            skipped += 1
            continue
        cur.execute("""
            INSERT OR IGNORE INTO psychomotor_ratings_new
                (enrollment_id, student_name, class_name, session, term,
                 punctuality, neatness, honesty, cooperation, leadership,
                 perseverance, politeness, obedience, attentiveness, attitude_to_work)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (enrollment_id, student_name, class_name, session, term,
              punctuality, neatness, honesty, cooperation, leadership,
              perseverance, politeness, obedience, attentiveness, attitude_to_work))
        if cur.rowcount:
            n += 1
        else:
            skipped += 1
    logger.info(f"✅ Psychomotor: {n} migrated, {skipped} skipped")


def step_migrate_subject_selections(cur):
    logger.info("Migrating student subject selections...")
    if not table_exists(cur, "student_subject_selections"):
        logger.info("  No student_subject_selections table — skipping")
        return

    cur.execute("""
        SELECT student_name, subject_name, class_name, term, session
        FROM   student_subject_selections
        WHERE  student_name != '' AND class_name != '' AND session != ''
    """)
    rows = cur.fetchall()
    n = skipped = 0
    for (student_name, subject_name, class_name, term, session) in rows:
        enrollment_id = resolve_enrollment_id(cur, student_name, class_name, session)
        if not enrollment_id:
            skipped += 1
            continue
        cur.execute("""
            INSERT OR IGNORE INTO student_subject_selections_new
                (enrollment_id, student_name, class_name, session, term, subject_name)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (enrollment_id, student_name, class_name, session, term, subject_name))
        if cur.rowcount:
            n += 1
        else:
            skipped += 1
    logger.info(f"✅ Subject selections: {n} migrated, {skipped} skipped")


def step_swap_new_tables(cur):
    """
    Rename the *_new tables to their final names.
    Also rename old data tables to *_OLD for safety (if not already done).
    """
    logger.info("Swapping new tables into place...")

    swaps = [
        ("scores",                    "scores_OLD",                    "scores_new"),
        ("comments",                  "comments_OLD",                  "comments_new"),
        ("psychomotor_ratings",       "psychomotor_ratings_OLD",       "psychomotor_ratings_new"),
        ("student_subject_selections","student_subject_selections_OLD","student_subject_selections_new"),
    ]
    for old_name, backup_name, new_name in swaps:
        if table_exists(cur, old_name) and not table_exists(cur, backup_name):
            cur.execute(f"ALTER TABLE {old_name} RENAME TO {backup_name}")
            logger.info(f"  {old_name} → {backup_name}")
        if table_exists(cur, new_name):
            cur.execute(f"ALTER TABLE {new_name} RENAME TO {old_name}")
            logger.info(f"  {new_name} → {old_name}")


def step_set_academic_settings(cur, sessions_found):
    if not sessions_found:
        logger.warning("No sessions found — academic_settings left blank")
        return
    latest = sorted(sessions_found)[-1]
    cur.execute("""
        UPDATE academic_settings
        SET current_session = ?, current_term = 'First', updated_by = 'migration'
        WHERE id = 1
    """, (latest,))
    logger.info(
        f"✅ academic_settings → session={latest}, term=First  "
        "(review in Admin → Academic Settings)"
    )


def step_integrity_check(conn):
    cur = conn.cursor()
    cur.execute("PRAGMA integrity_check")
    result = cur.fetchone()[0]
    if result == "ok":
        logger.info("✅ Integrity check passed")
    else:
        logger.error(f"❌ Integrity check FAILED: {result}")
    return result == "ok"


# ─────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────

def run_migration(db_path: str):
    if not os.path.exists(db_path):
        logger.error(f"Database not found: {db_path}")
        sys.exit(1)

    logger.info(f"Starting migration: {db_path}")
    logger.info("=" * 60)

    backup_path = step_backup(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("PRAGMA journal_mode = WAL")
    cur = conn.cursor()

    try:
        # ORDER MATTERS — rename old tables FIRST, then create new ones
        step_rename_old_tables(cur)
        conn.commit()

        step_create_new_tables(conn)

        sessions = step_migrate_sessions(cur)
        conn.commit()

        step_migrate_class_definitions(cur)
        conn.commit()

        step_migrate_subjects(cur)
        conn.commit()

        step_migrate_student_registry(cur)
        conn.commit()

        step_create_class_sessions(cur)
        conn.commit()

        step_enroll_students(cur)
        conn.commit()

        step_migrate_scores(cur)
        conn.commit()

        step_migrate_comments(cur)
        conn.commit()

        step_migrate_psychomotor(cur)
        conn.commit()

        step_migrate_subject_selections(cur)
        conn.commit()

        step_swap_new_tables(cur)
        conn.commit()

        step_set_academic_settings(cur, sessions)
        conn.commit()

        conn.execute("PRAGMA foreign_keys = ON")
        ok = step_integrity_check(conn)

        logger.info("=" * 60)
        if ok:
            logger.info("✅ MIGRATION COMPLETE")
        else:
            logger.warning("⚠️  Migration completed with integrity issues — review above")

        logger.info(f"   Backup at: {backup_path}")
        logger.info("   NEXT STEPS:")
        logger.info("   1. Admin Panel → Academic Settings → verify session + term")
        logger.info("   2. Test score entry and broadsheet for one class")
        logger.info("   3. After 30 days, run: DROP TABLE classes_OLD, students_OLD, etc.")

    except Exception as e:
        logger.error(f"❌ Migration FAILED: {e}")
        logger.error(f"   Restore from backup: {backup_path}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate school DB to session-aware schema")
    parser.add_argument(
        "--db",
        default=os.path.join("data", "schools", "suis.db"),
        help="Path to the school SQLite database"
    )
    args = parser.parse_args()
    run_migration(args.db)
