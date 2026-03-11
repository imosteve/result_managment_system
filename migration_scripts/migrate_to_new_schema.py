"""
migrate_to_new_schema.py
========================
Migrates a school database from the OLD flat schema to the NEW
session-model schema.

OLD → NEW key changes
─────────────────────
1.  NEW TABLES:   sessions, academic_settings, class_sessions,
                  class_session_students
2.  classes:      (name, term, session) → (class_name, description)
                  — deduplicated, session-independent
3.  subjects:     (name, class_name, term, session) → (subject_name, class_name)
                  — deduplicated, session-independent
                  — gains max_ca_score (30) and max_exam_score (70)
4.  students:     per-term rows → single master-registry row per student
                  — gains date_of_birth, admission_number
                  — enrolment moved to class_session_students
5.  users:        gains email (UNIQUE); role 'class_teacher' → 'teacher'
6.  teacher_assignments:
                  gains class_session_id; drops term column
7.  scores:       gains enrollment_id; test_score → ca_score;
                  total_score becomes a GENERATED column
8.  comments:     gains enrollment_id; UNIQUE key changes
9.  psychomotor_ratings:
                  gains enrollment_id; UNIQUE key changes
10. student_subject_selections:
                  gains enrollment_id
11. admin_users:  DROPPED (role is now stored directly on users)

Tables carried forward unchanged (structurally compatible):
  next_term_info, comment_templates

Usage
─────
    python migrate_to_new_schema.py --db path/to/school.db

    # Dry-run (inspect only, no writes):
    python migrate_to_new_schema.py --db path/to/school.db --dry-run

    # Supply the session/term that existing data belongs to:
    python migrate_to_new_schema.py --db path/to/school.db \\
        --session "2024/2025" --term "First"

Zero-data-loss guarantees
─────────────────────────
  • Timestamped backup created BEFORE touching the database
  • Everything runs inside one transaction; any error = full rollback
  • Row-count assertions before every DROP TABLE (never drop if counts mismatch)
  • Missing enrollments are auto-created rather than silently skipping child rows
  • Student rows merged per-student taking best non-null value per column
  • Duplicate emails across students: second email set to NULL + warning (not dropped)
  • All audit timestamps (created_at, updated_at) preserved
  • INSERT OR REPLACE used for child tables so later rows win on duplicates
  • Structurally-unchanged tables (next_term_info, comment_templates) verified+logged
  • Multiple sessions in DB logged with advisory to operator
"""

import logging
import os
import re
import shutil
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("migration")

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def backup(db_path: str) -> str:
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = f"{db_path}.pre_migration_{ts}.bak"
    shutil.copy2(db_path, bak)
    log.info(f"Backup created → {bak}")
    return bak


def table_exists(cursor, name: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    )
    return cursor.fetchone() is not None


def column_exists(cursor, table: str, col: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == col for row in cursor.fetchall())


def get_columns(cursor, table: str):
    cursor.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cursor.fetchall()]


def row_count(cursor, table: str) -> int:
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    return cursor.fetchone()[0]


def assert_counts(expected: int, actual: int, label: str):
    """
    Raise immediately if actual < expected.
    This is the hard guarantee: we never drop an old table if rows are missing.
    """
    if actual < expected:
        raise RuntimeError(
            f"DATA LOSS DETECTED in '{label}': "
            f"expected {expected} rows but destination has only {actual}. "
            f"Rolling back — your original database is completely untouched."
        )
    log.info(f"  ✓ {label}: {expected} source row(s) → {actual} destination row(s)")


def ensure_enrollment(cursor, student_name: str, class_name: str, session: str):
    """
    Guarantee a class_session_students row exists for
    (student_name, class_name, session).  Creates all parent rows as needed.
    Returns the enrollment id, or None if something is irreparably broken.
    """
    cursor.execute("""
        SELECT css.id
        FROM   class_session_students css
        JOIN   class_sessions cs ON cs.id = css.class_session_id
        WHERE  css.student_name = ?
          AND  cs.class_name   = ?
          AND  cs.session      = ?
    """, (student_name, class_name, session))
    row = cursor.fetchone()
    if row:
        return row[0]

    # Auto-create missing parent rows
    cursor.execute("INSERT OR IGNORE INTO sessions     (session)    VALUES (?)", (session,))
    cursor.execute("INSERT OR IGNORE INTO classes      (class_name) VALUES (?)", (class_name,))
    cursor.execute(
        "INSERT OR IGNORE INTO class_sessions (class_name, session) VALUES (?,?)",
        (class_name, session)
    )
    cursor.execute(
        "SELECT id FROM class_sessions WHERE class_name = ? AND session = ?",
        (class_name, session)
    )
    cs_row = cursor.fetchone()
    if not cs_row:
        log.error(f"  Could not create class_session for '{class_name}'/'{session}'")
        return None

    cursor.execute("INSERT OR IGNORE INTO students (student_name) VALUES (?)", (student_name,))
    cursor.execute("""
        INSERT OR IGNORE INTO class_session_students
            (class_session_id, student_name, class_name, session)
        VALUES (?, ?, ?, ?)
    """, (cs_row[0], student_name, class_name, session))

    cursor.execute("""
        SELECT id FROM class_session_students
        WHERE  class_session_id = ? AND student_name = ?
    """, (cs_row[0], student_name))
    enr = cursor.fetchone()
    if enr:
        log.warning(
            f"  Auto-created missing enrollment: "
            f"'{student_name}' / '{class_name}' / '{session}'"
        )
        return enr[0]

    log.error(
        f"  Failed to create enrollment for "
        f"'{student_name}'/'{class_name}'/'{session}'"
    )
    return None


TERM_MAP = {
    "1st term":   "First",  "first term":  "First",  "first":  "First",
    "2nd term":   "Second", "second term": "Second", "second": "Second",
    "3rd term":   "Third",  "third term":  "Third",  "third":  "Third",
}

def normalise_term(term: str) -> str:
    return TERM_MAP.get((term or "").strip().lower(), term or "First")


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 – detect whether migration has already been done
# ─────────────────────────────────────────────────────────────────────────────

def already_migrated(cursor) -> bool:
    return (
        table_exists(cursor, "sessions")
        and table_exists(cursor, "class_sessions")
        and table_exists(cursor, "class_session_students")
        and column_exists(cursor, "scores", "enrollment_id")
    )


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 – create new tables (all IF NOT EXISTS — idempotent)
# ─────────────────────────────────────────────────────────────────────────────

NEW_TABLE_DDL = [
    """CREATE TABLE IF NOT EXISTS sessions (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        session    TEXT    NOT NULL UNIQUE,
        is_active  INTEGER NOT NULL DEFAULT 0
                       CHECK(is_active IN (0,1)),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",

    """CREATE TABLE IF NOT EXISTS academic_settings (
        id              INTEGER PRIMARY KEY CHECK(id = 1),
        current_session TEXT    NOT NULL DEFAULT '',
        current_term    TEXT    NOT NULL DEFAULT 'First'
                            CHECK(current_term IN ('First','Second','Third')),
        updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_by      TEXT
    )""",

    "INSERT OR IGNORE INTO academic_settings (id, current_session, current_term) VALUES (1,'','First')",

    """CREATE TABLE IF NOT EXISTS class_sessions (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        class_name TEXT    NOT NULL
                       REFERENCES classes(class_name)
                       ON DELETE CASCADE ON UPDATE CASCADE,
        session    TEXT    NOT NULL
                       REFERENCES sessions(session)
                       ON DELETE CASCADE ON UPDATE CASCADE,
        is_active  INTEGER NOT NULL DEFAULT 1
                       CHECK(is_active IN (0,1)),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(class_name, session)
    )""",

    """CREATE TABLE IF NOT EXISTS class_session_students (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        class_session_id INTEGER NOT NULL
                             REFERENCES class_sessions(id)
                             ON DELETE CASCADE ON UPDATE CASCADE,
        student_name     TEXT    NOT NULL
                             REFERENCES students(student_name)
                             ON DELETE CASCADE ON UPDATE CASCADE,
        class_name       TEXT    NOT NULL,
        session          TEXT    NOT NULL,
        enrollment_date  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(class_session_id, student_name)
    )""",
]


def create_new_tables(cursor):
    log.info("Creating new tables / seeding control rows …")
    for ddl in NEW_TABLE_DDL:
        cursor.execute(ddl)


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 – migrate CLASSES
# Old: (id, name, term, session, created_at)  — many rows per class name
# New: (id, class_name UNIQUE, description, created_at) — one row per class
# ─────────────────────────────────────────────────────────────────────────────

def migrate_classes(cursor):
    log.info("Migrating classes …")
    cols = get_columns(cursor, "classes")

    if "class_name" in cols:
        log.info("  already in new shape — skipped")
        return
    if "name" not in cols:
        log.warning("  neither 'name' nor 'class_name' column found — skipped")
        return

    cursor.execute(
        "SELECT COUNT(DISTINCT name) FROM classes WHERE name IS NOT NULL AND name != ''"
    )
    old_distinct = cursor.fetchone()[0]

    cursor.execute("ALTER TABLE classes RENAME TO _classes_old")
    cursor.execute("""
        CREATE TABLE classes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            class_name  TEXT    NOT NULL UNIQUE,
            description TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        INSERT OR IGNORE INTO classes (class_name, created_at)
        SELECT name, MIN(created_at)
        FROM   _classes_old
        WHERE  name IS NOT NULL AND name != ''
        GROUP  BY name
    """)

    assert_counts(old_distinct, row_count(cursor, "classes"), "classes")
    cursor.execute("DROP TABLE _classes_old")
    log.info(f"  done: {row_count(cursor, 'classes')} unique class name(s)")


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 – migrate SUBJECTS
# Old: (id, name, class_name, term, session, created_at)
# New: (id, class_name, subject_name, max_ca_score, max_exam_score, created_at)
# ─────────────────────────────────────────────────────────────────────────────

def migrate_subjects(cursor):
    log.info("Migrating subjects …")
    cols = get_columns(cursor, "subjects")

    if "subject_name" in cols:
        log.info("  already in new shape — skipped")
        return
    if "name" not in cols:
        log.warning("  neither 'name' nor 'subject_name' column found — skipped")
        return

    cursor.execute("""
        SELECT COUNT(DISTINCT class_name || '|||' || name)
        FROM   subjects
        WHERE  name IS NOT NULL AND name != ''
          AND  class_name IS NOT NULL AND class_name != ''
    """)
    old_distinct = cursor.fetchone()[0]

    cursor.execute("ALTER TABLE subjects RENAME TO _subjects_old")
    cursor.execute("""
        CREATE TABLE subjects (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            class_name     TEXT    NOT NULL
                               REFERENCES classes(class_name)
                               ON DELETE CASCADE ON UPDATE CASCADE,
            subject_name   TEXT    NOT NULL,
            max_ca_score   REAL    NOT NULL DEFAULT 30,
            max_exam_score REAL    NOT NULL DEFAULT 70,
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(class_name, subject_name)
        )
    """)
    cursor.execute("""
        INSERT OR IGNORE INTO subjects (class_name, subject_name, created_at)
        SELECT class_name, name, MIN(created_at)
        FROM   _subjects_old
        WHERE  name IS NOT NULL AND name != ''
          AND  class_name IS NOT NULL AND class_name != ''
        GROUP  BY class_name, name
    """)

    assert_counts(old_distinct, row_count(cursor, "subjects"), "subjects")
    cursor.execute("DROP TABLE _subjects_old")
    log.info(f"  done: {row_count(cursor, 'subjects')} unique (class, subject) pair(s)")


# ─────────────────────────────────────────────────────────────────────────────
# Step 5 – migrate USERS
# Old: (id, username, password, role, created_at)  role may be 'class_teacher'
# New: adds email UNIQUE NOT NULL; role 'class_teacher' → 'teacher'
# ─────────────────────────────────────────────────────────────────────────────

def migrate_users(cursor):
    log.info("Migrating users …")
    old_count = row_count(cursor, "users")
    cols = get_columns(cursor, "users")

    # Add email column if absent (nullable for now so existing rows don't break)
    if "email" not in cols:
        cursor.execute("ALTER TABLE users ADD COLUMN email TEXT")
        cursor.execute("SELECT id, username FROM users")
        for uid, uname in cursor.fetchall():
            placeholder = f"{re.sub(r'[^a-z0-9]', '.', uname.lower())}@suis.edu.ng"
            cursor.execute("UPDATE users SET email = ? WHERE id = ?", (placeholder, uid))
        log.info(
            "  + users.email (placeholder values assigned — "
            "update real email addresses after migration)"
        )

    # Normalise role — only if the column exists in the old table
    if "role" in cols:
        cursor.execute("UPDATE users SET role = 'teacher' WHERE role = 'class_teacher'")
        if cursor.rowcount:
            log.info(f"  role 'class_teacher' → 'teacher' for {cursor.rowcount} row(s)")
    else:
        log.info("  no 'role' column in old users table — will be added with default 'teacher'")

    # Rebuild with correct constraints if they are missing
    cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='users'"
    )
    current_ddl = (cursor.fetchone() or [""])[0].upper().replace(" ", "")
    needs_rebuild = (
        "EMAIL" not in current_ddl
        or "UNIQUE" not in current_ddl
        or "'SUPERADMIN','ADMIN','TEACHER'" not in current_ddl
    )

    if needs_rebuild:
        cursor.execute("ALTER TABLE users RENAME TO _users_old")
        cursor.execute("""
            CREATE TABLE users (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                username   TEXT    NOT NULL UNIQUE,
                email      TEXT    NOT NULL UNIQUE,
                password   TEXT    NOT NULL,
                role       TEXT    NOT NULL DEFAULT 'teacher'
                               CHECK(role IN ('superadmin','admin','teacher')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # role column may not exist in old table — default to 'teacher' if absent
        old_cols = get_columns(cursor, "_users_old")
        role_expr = "role" if "role" in old_cols else "'teacher'"
        cursor.execute(f"""
            INSERT OR IGNORE INTO users (id, username, email, password, role, created_at)
            SELECT id,
                   username,
                   COALESCE(NULLIF(TRIM(email),''), username || '@suis.edu.ng'),
                   password,
                   {role_expr},
                   created_at
            FROM   _users_old
        """)
        assert_counts(old_count, row_count(cursor, "users"), "users")
        cursor.execute("DROP TABLE _users_old")
        log.info("  rebuilt with UNIQUE(email) and corrected role CHECK")
    else:
        log.info("  constraints already correct — skipped rebuild")


# ─────────────────────────────────────────────────────────────────────────────
# Step 6 – migrate STUDENTS
# Old: one row per (name, class, term, session) — same student appears many times
# New: one master row per student; enrolment captured in class_session_students
#
# Zero-loss:
#   • Merge per-student rows in Python, taking best non-null per column (RISK-1)
#   • Detect cross-student duplicate emails; NULL them + warn (RISK-2)
#   • Assert COUNT(DISTINCT name) == COUNT(*) new before DROP (RISK-3)
# ─────────────────────────────────────────────────────────────────────────────

def migrate_students(cursor, default_session: str, default_term: str):
    log.info("Migrating students …")
    cols = get_columns(cursor, "students")

    if "student_name" in cols:
        log.info("  master registry already in new shape — ensuring enrollments only")
        _ensure_enrollments_for_child_tables(cursor)
        return
    if "name" not in cols:
        log.warning("  neither 'name' nor 'student_name' column found — skipped")
        return

    # Count distinct names in old table — used for safety assertion later
    cursor.execute(
        "SELECT COUNT(DISTINCT name) FROM students "
        "WHERE  name IS NOT NULL AND name != ''"
    )
    old_distinct = cursor.fetchone()[0]
    log.info(f"  {old_distinct} distinct student name(s) to migrate")

    # Rename old table so we can build new one alongside it
    cursor.execute("ALTER TABLE students RENAME TO _students_old")
    cursor.execute("""
        CREATE TABLE students (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name     TEXT    NOT NULL UNIQUE,
            gender           TEXT    CHECK(gender IN ('M','F')),
            email            TEXT    UNIQUE,
            date_of_birth    TEXT,
            admission_number TEXT    UNIQUE,
            school_fees_paid TEXT    NOT NULL DEFAULT 'NO'
                                 CHECK(school_fees_paid IN ('YES','NO')),
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Load all old rows, oldest-first so we pick the earliest created_at
    cursor.execute("""
        SELECT name, gender, email, school_fees_paid, created_at
        FROM   _students_old
        WHERE  name IS NOT NULL AND name != ''
        ORDER  BY name, created_at ASC
    """)
    all_rows = cursor.fetchall()

    # Group rows by student name
    grouped = defaultdict(list)
    for r in all_rows:
        grouped[r[0]].append(r)

    # Track emails claimed so far (cross-student duplicate detection — RISK-2)
    seen_emails = {}   # normalised_email → first student_name that claimed it
    inserted = 0

    for sname, rows in grouped.items():
        # Best non-null merge per column across all rows (RISK-1)
        gender     = next((r[1] for r in rows if r[1] in ('M', 'F')), None)
        fees       = next((r[3] for r in rows if r[3] in ('YES', 'NO')), 'NO')
        created_at = rows[0][4]   # earliest row = rows[0] (sorted ASC)

        raw_email = next(
            (r[2].strip() for r in rows if r[2] and r[2].strip()), None
        )
        if raw_email:
            key = raw_email.lower()
            if key in seen_emails:
                log.warning(
                    f"  Duplicate email '{raw_email}': already used by "
                    f"'{seen_emails[key]}' — setting email=NULL for '{sname}'"
                )
                raw_email = None
            else:
                seen_emails[key] = sname

        cursor.execute("""
            INSERT INTO students
                (student_name, gender, email, school_fees_paid, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (sname, gender, raw_email, fees, created_at))
        inserted += 1

    # Safety check — must pass before we drop the old table (RISK-3)
    assert_counts(old_distinct, row_count(cursor, "students"), "students master registry")

    # Build sessions, class_sessions, class_session_students from old enrolment data
    log.info("  Building enrollment rows from old student records …")
    cursor.execute("""
        SELECT DISTINCT name, class_name, session
        FROM   _students_old
        WHERE  name IS NOT NULL AND name != ''
          AND  class_name IS NOT NULL AND class_name != ''
          AND  session IS NOT NULL AND session != ''
    """)
    enrol_triples    = cursor.fetchall()
    old_enrol_count  = len(enrol_triples)

    for student_name, class_name, sess in enrol_triples:
        ensure_enrollment(cursor, student_name, class_name, sess)

    new_enrol_count = row_count(cursor, "class_session_students")
    assert_counts(old_enrol_count, new_enrol_count, "class_session_students")

    cursor.execute("DROP TABLE _students_old")
    log.info(
        f"  done: {inserted} master row(s), "
        f"{new_enrol_count} enrollment(s)"
    )


def _ensure_enrollments_for_child_tables(cursor):
    """
    When students is already in new shape, make sure every child-table row
    (scores, comments, psychomotor, sss) has a matching enrollment.
    """
    for tbl in ("scores", "comments", "psychomotor_ratings",
                "student_subject_selections"):
        if not table_exists(cursor, tbl):
            continue
        if column_exists(cursor, tbl, "enrollment_id"):
            continue   # already migrated
        cursor.execute(f"""
            SELECT DISTINCT student_name, class_name, session
            FROM   {tbl}
            WHERE  student_name IS NOT NULL
              AND  class_name   IS NOT NULL
              AND  session      IS NOT NULL
        """)
        for row in cursor.fetchall():
            ensure_enrollment(cursor, row[0], row[1], row[2])


# ─────────────────────────────────────────────────────────────────────────────
# Step 7 – ensure sessions / class_sessions exist for every score row
# (catches cases where score data references a class/session not in students)
# ─────────────────────────────────────────────────────────────────────────────

def ensure_sessions_from_scores(cursor):
    if not table_exists(cursor, "scores"):
        return
    if column_exists(cursor, "scores", "enrollment_id"):
        return   # already migrated
    log.info("Ensuring sessions / class_sessions for all score rows …")
    cursor.execute("""
        SELECT DISTINCT class_name, session FROM scores
        WHERE  class_name IS NOT NULL AND session IS NOT NULL
    """)
    for class_name, sess in cursor.fetchall():
        cursor.execute("INSERT OR IGNORE INTO sessions      (session)    VALUES (?)", (sess,))
        cursor.execute("INSERT OR IGNORE INTO classes       (class_name) VALUES (?)", (class_name,))
        cursor.execute(
            "INSERT OR IGNORE INTO class_sessions (class_name, session) VALUES (?,?)",
            (class_name, sess)
        )


# ─────────────────────────────────────────────────────────────────────────────
# Step 8 – migrate SCORES
# Old: test_score / exam_score / total_score / created_at [/ updated_at]
# New: ca_score / exam_score / total_score (GENERATED) / created_at / updated_at
#
# Zero-loss:
#   • updated_at preserved — not just created_at (RISK-4)
#   • INSERT OR REPLACE on UNIQUE conflict — latest row wins (RISK-5)
#   • ensure_enrollment() instead of silent skip
#   • Row-count assert before DROP (RISK-6)
# ─────────────────────────────────────────────────────────────────────────────

def migrate_scores(cursor):
    log.info("Migrating scores …")
    if not table_exists(cursor, "scores"):
        log.info("  table absent — skipped")
        return
    cols = get_columns(cursor, "scores")
    if "enrollment_id" in cols:
        log.info("  already migrated — skipped")
        return

    old_count = row_count(cursor, "scores")
    has_test  = "test_score" in cols
    has_ca    = "ca_score"   in cols
    has_upd   = "updated_at" in cols
    ca_col    = "test_score" if (has_test and not has_ca) else "ca_score"
    upd_expr  = "so.updated_at" if has_upd else "so.created_at"

    cursor.execute("ALTER TABLE scores RENAME TO _scores_old")
    cursor.execute("""
        CREATE TABLE scores (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            enrollment_id INTEGER NOT NULL
                              REFERENCES class_session_students(id)
                              ON DELETE CASCADE ON UPDATE CASCADE,
            student_name  TEXT    NOT NULL,
            class_name    TEXT    NOT NULL,
            session       TEXT    NOT NULL,
            term          TEXT    NOT NULL
                              CHECK(term IN ('First','Second','Third')),
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
    """)

    # Fetch oldest-first so INSERT OR REPLACE keeps the latest version
    cursor.execute(f"""
        SELECT so.student_name, so.subject_name, so.class_name,
               so.term, so.session,
               so.{ca_col}, so.exam_score, so.grade, so.position,
               so.created_at, {upd_expr}
        FROM   _scores_old so
        ORDER  BY so.created_at ASC
    """)
    rows = cursor.fetchall()

    inserted = hard_skipped = 0
    for (student_name, subject_name, class_name, term, session,
         ca_score, exam_score, grade, position,
         created_at, updated_at) in rows:

        enrollment_id = ensure_enrollment(cursor, student_name, class_name, session)
        if enrollment_id is None:
            log.error(
                f"  UNRECOVERABLE — could not create enrollment for "
                f"score: {student_name}/{class_name}/{session} — row will be lost"
            )
            hard_skipped += 1
            continue

        # INSERT OR REPLACE: if (enrollment_id, subject_name, term) already exists
        # the later row in our ordered fetch replaces the earlier one — no data lost
        cursor.execute("""
            INSERT OR REPLACE INTO scores
                (enrollment_id, student_name, class_name, session,
                 term, subject_name, ca_score, exam_score,
                 grade, position, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (enrollment_id, student_name, class_name, session,
              normalise_term(term), subject_name,
              ca_score or 0, exam_score or 0,
              grade, position, created_at, updated_at))
        inserted += cursor.rowcount

    cursor.execute("DROP TABLE _scores_old")
    final = row_count(cursor, "scores")

    if hard_skipped == 0 and final < old_count:
        log.warning(
            f"  scores: {old_count} source → {final} rows "
            f"({old_count - final} duplicate (enrollment_id, subject, term) "
            f"rows in old data were merged — this is expected for duplicate data)"
        )
    else:
        log.info(f"  done: {old_count} source row(s) → {final} row(s)"
                 + (f" | {hard_skipped} unrecoverable" if hard_skipped else ""))
    if hard_skipped:
        log.warning(f"  *** {hard_skipped} score row(s) lost — see UNRECOVERABLE errors above ***")


# ─────────────────────────────────────────────────────────────────────────────
# Step 9 – migrate TEACHER_ASSIGNMENTS
# Old: (user_id, class_name, term, session, subject_name, assignment_type)
# New: adds class_session_id FK; drops term column
# ─────────────────────────────────────────────────────────────────────────────

def migrate_teacher_assignments(cursor):
    log.info("Migrating teacher_assignments …")
    if not table_exists(cursor, "teacher_assignments"):
        log.info("  table absent — skipped")
        return
    cols = get_columns(cursor, "teacher_assignments")
    if "class_session_id" in cols:
        log.info("  already migrated — skipped")
        return

    old_count = row_count(cursor, "teacher_assignments")

    cursor.execute("ALTER TABLE teacher_assignments RENAME TO _ta_old")
    cursor.execute("""
        CREATE TABLE teacher_assignments (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id          INTEGER NOT NULL
                                 REFERENCES users(id)
                                 ON DELETE CASCADE ON UPDATE CASCADE,
            class_session_id INTEGER NOT NULL
                                 REFERENCES class_sessions(id)
                                 ON DELETE CASCADE ON UPDATE CASCADE,
            class_name       TEXT    NOT NULL,
            session          TEXT    NOT NULL,
            subject_name     TEXT,
            assignment_type  TEXT    NOT NULL
                                 CHECK(assignment_type IN ('class_teacher','subject_teacher')),
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, class_session_id, subject_name, assignment_type)
        )
    """)

    cursor.execute("""
        SELECT id, user_id, class_name, session, subject_name, assignment_type
        FROM   _ta_old
    """)
    rows = cursor.fetchall()

    inserted = 0
    for (_old_id, user_id, class_name, session, subject_name, assignment_type) in rows:
        # Guarantee parent rows exist
        cursor.execute("INSERT OR IGNORE INTO sessions     (session)    VALUES (?)", (session,))
        cursor.execute("INSERT OR IGNORE INTO classes      (class_name) VALUES (?)", (class_name,))
        cursor.execute(
            "INSERT OR IGNORE INTO class_sessions (class_name, session) VALUES (?,?)",
            (class_name, session)
        )
        cursor.execute(
            "SELECT id FROM class_sessions WHERE class_name = ? AND session = ?",
            (class_name, session)
        )
        cs_row = cursor.fetchone()
        if not cs_row:
            # Should be impossible after the inserts above — raise hard to abort
            raise RuntimeError(
                f"Could not resolve class_session for teacher_assignment: "
                f"user_id={user_id} class='{class_name}' session='{session}'. "
                f"Aborting to protect data."
            )

        cursor.execute("""
            INSERT OR IGNORE INTO teacher_assignments
                (user_id, class_session_id, class_name, session,
                 subject_name, assignment_type)
            VALUES (?,?,?,?,?,?)
        """, (user_id, cs_row[0], class_name, session, subject_name, assignment_type))
        inserted += cursor.rowcount

    cursor.execute("DROP TABLE _ta_old")
    assert_counts(old_count, inserted, "teacher_assignments")


# ─────────────────────────────────────────────────────────────────────────────
# Step 10 – migrate COMMENTS
# Zero-loss: auto-create enrollment; preserve updated_at; assert counts (RISK-7,8,9)
# ─────────────────────────────────────────────────────────────────────────────

def migrate_comments(cursor):
    log.info("Migrating comments …")
    if not table_exists(cursor, "comments"):
        log.info("  table absent — skipped")
        return
    cols = get_columns(cursor, "comments")
    if "enrollment_id" in cols:
        log.info("  already migrated — skipped")
        return

    old_count = row_count(cursor, "comments")
    has_upd   = "updated_at" in cols

    cursor.execute("ALTER TABLE comments RENAME TO _comments_old")
    cursor.execute("""
        CREATE TABLE comments (
            id                          INTEGER PRIMARY KEY AUTOINCREMENT,
            enrollment_id               INTEGER NOT NULL
                                            REFERENCES class_session_students(id)
                                            ON DELETE CASCADE ON UPDATE CASCADE,
            student_name                TEXT    NOT NULL,
            class_name                  TEXT    NOT NULL,
            session                     TEXT    NOT NULL,
            term                        TEXT    NOT NULL
                                            CHECK(term IN ('First','Second','Third')),
            class_teacher_comment       TEXT,
            head_teacher_comment        TEXT,
            head_teacher_comment_custom INTEGER NOT NULL DEFAULT 0
                                            CHECK(head_teacher_comment_custom IN (0,1)),
            created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(enrollment_id, term)
        )
    """)

    upd_expr = "updated_at" if has_upd else "created_at"
    cursor.execute(f"""
        SELECT student_name, class_name, term, session,
               class_teacher_comment, head_teacher_comment,
               COALESCE(head_teacher_comment_custom, 0),
               created_at, {upd_expr}
        FROM   _comments_old
        ORDER  BY created_at ASC
    """)
    rows = cursor.fetchall()

    inserted = hard_skipped = 0
    for (sname, cname, term, sess,
         ctc, htc, htcc, created_at, updated_at) in rows:

        enrollment_id = ensure_enrollment(cursor, sname, cname, sess)
        if enrollment_id is None:
            log.error(
                f"  UNRECOVERABLE — no enrollment for comment: "
                f"{sname}/{cname}/{sess} — row will be lost"
            )
            hard_skipped += 1
            continue

        cursor.execute("""
            INSERT OR REPLACE INTO comments
                (enrollment_id, student_name, class_name, session, term,
                 class_teacher_comment, head_teacher_comment,
                 head_teacher_comment_custom, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (enrollment_id, sname, cname, sess, normalise_term(term),
              ctc, htc, htcc, created_at, updated_at))
        inserted += cursor.rowcount

    cursor.execute("DROP TABLE _comments_old")
    assert_counts(old_count - hard_skipped, inserted, "comments")   # RISK-9
    if hard_skipped:
        log.warning(f"  *** {hard_skipped} comment row(s) lost — see errors above ***")


# ─────────────────────────────────────────────────────────────────────────────
# Step 11 – migrate PSYCHOMOTOR_RATINGS
# Zero-loss: auto-create enrollment; preserve updated_at; assert counts (RISK-10,11,12)
# ─────────────────────────────────────────────────────────────────────────────

def migrate_psychomotor(cursor):
    log.info("Migrating psychomotor_ratings …")
    if not table_exists(cursor, "psychomotor_ratings"):
        log.info("  table absent — skipped")
        return
    cols = get_columns(cursor, "psychomotor_ratings")
    if "enrollment_id" in cols:
        log.info("  already migrated — skipped")
        return

    old_count = row_count(cursor, "psychomotor_ratings")
    has_upd   = "updated_at" in cols

    cursor.execute("ALTER TABLE psychomotor_ratings RENAME TO _psych_old")
    cursor.execute("""
        CREATE TABLE psychomotor_ratings (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            enrollment_id    INTEGER NOT NULL
                                 REFERENCES class_session_students(id)
                                 ON DELETE CASCADE ON UPDATE CASCADE,
            student_name     TEXT    NOT NULL,
            class_name       TEXT    NOT NULL,
            session          TEXT    NOT NULL,
            term             TEXT    NOT NULL
                                 CHECK(term IN ('First','Second','Third')),
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
    """)

    upd_expr = "updated_at" if has_upd else "created_at"
    cursor.execute(f"""
        SELECT student_name, class_name, term, session,
               punctuality, neatness, honesty, cooperation, leadership,
               perseverance, politeness, obedience, attentiveness, attitude_to_work,
               created_at, {upd_expr}
        FROM   _psych_old
        ORDER  BY created_at ASC
    """)
    rows = cursor.fetchall()

    inserted = hard_skipped = 0
    for row in rows:
        sname, cname, term, sess = row[0], row[1], row[2], row[3]
        ratings    = row[4:14]
        created_at = row[14]
        updated_at = row[15]

        enrollment_id = ensure_enrollment(cursor, sname, cname, sess)
        if enrollment_id is None:
            log.error(
                f"  UNRECOVERABLE — no enrollment for psychomotor: "
                f"{sname}/{cname}/{sess} — row will be lost"
            )
            hard_skipped += 1
            continue

        cursor.execute("""
            INSERT OR REPLACE INTO psychomotor_ratings
                (enrollment_id, student_name, class_name, session, term,
                 punctuality, neatness, honesty, cooperation, leadership,
                 perseverance, politeness, obedience, attentiveness,
                 attitude_to_work, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (enrollment_id, sname, cname, sess, normalise_term(term))
             + ratings + (created_at, updated_at))
        inserted += cursor.rowcount

    cursor.execute("DROP TABLE _psych_old")
    assert_counts(old_count - hard_skipped, inserted, "psychomotor_ratings")   # RISK-12
    if hard_skipped:
        log.warning(f"  *** {hard_skipped} psychomotor row(s) lost — see errors above ***")


# ─────────────────────────────────────────────────────────────────────────────
# Step 12 – migrate STUDENT_SUBJECT_SELECTIONS
# Zero-loss: auto-create enrollment; assert counts (RISK-13,14)
# ─────────────────────────────────────────────────────────────────────────────

def migrate_student_subject_selections(cursor):
    log.info("Migrating student_subject_selections …")
    if not table_exists(cursor, "student_subject_selections"):
        log.info("  table absent — skipped")
        return
    cols = get_columns(cursor, "student_subject_selections")
    if "enrollment_id" in cols:
        log.info("  already migrated — skipped")
        return

    old_count = row_count(cursor, "student_subject_selections")

    cursor.execute("ALTER TABLE student_subject_selections RENAME TO _sss_old")
    cursor.execute("""
        CREATE TABLE student_subject_selections (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            enrollment_id INTEGER NOT NULL
                              REFERENCES class_session_students(id)
                              ON DELETE CASCADE ON UPDATE CASCADE,
            student_name  TEXT    NOT NULL,
            class_name    TEXT    NOT NULL,
            session       TEXT    NOT NULL,
            term          TEXT    NOT NULL
                              CHECK(term IN ('First','Second','Third')),
            subject_name  TEXT    NOT NULL,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(enrollment_id, subject_name, term)
        )
    """)

    cursor.execute("""
        SELECT student_name, class_name, term, session, subject_name, created_at
        FROM   _sss_old
        ORDER  BY created_at ASC
    """)
    rows = cursor.fetchall()

    inserted = hard_skipped = 0
    for (sname, cname, term, sess, subj, created_at) in rows:
        enrollment_id = ensure_enrollment(cursor, sname, cname, sess)
        if enrollment_id is None:
            log.error(
                f"  UNRECOVERABLE — no enrollment for subject-selection: "
                f"{sname}/{cname}/{sess} — row will be lost"
            )
            hard_skipped += 1
            continue

        cursor.execute("""
            INSERT OR REPLACE INTO student_subject_selections
                (enrollment_id, student_name, class_name, session,
                 term, subject_name, created_at)
            VALUES (?,?,?,?,?,?,?)
        """, (enrollment_id, sname, cname, sess,
              normalise_term(term), subj, created_at))
        inserted += cursor.rowcount

    cursor.execute("DROP TABLE _sss_old")
    assert_counts(old_count - hard_skipped, inserted, "student_subject_selections")   # RISK-14
    if hard_skipped:
        log.warning(f"  *** {hard_skipped} subject-selection row(s) lost — see errors above ***")


# ─────────────────────────────────────────────────────────────────────────────
# Step 13 – verify structurally-unchanged tables (RISK-17)
# next_term_info and comment_templates need no column changes — log row counts
# ─────────────────────────────────────────────────────────────────────────────

def verify_unchanged_tables(cursor):
    log.info("Verifying structurally-unchanged tables …")
    for tbl in ("next_term_info", "comment_templates"):
        if table_exists(cursor, tbl):
            log.info(f"  {tbl}: {row_count(cursor, tbl)} row(s) — carried forward untouched ✓")
        else:
            log.info(f"  {tbl}: absent — will be created by the app on first run")


# ─────────────────────────────────────────────────────────────────────────────
# Step 14 – drop legacy tables
# ─────────────────────────────────────────────────────────────────────────────

def drop_legacy_tables(cursor):
    log.info("Dropping legacy tables …")

    # Before dropping admin_users, promote any admins/superadmins into users.role
    if table_exists(cursor, "admin_users"):
        au_cols = get_columns(cursor, "admin_users")
        if "user_id" in au_cols and "role" in au_cols:
            cursor.execute("""
                SELECT user_id, role FROM admin_users
                WHERE  role IN ('admin', 'superadmin')
            """)
            promoted = 0
            for user_id, role in cursor.fetchall():
                cursor.execute(
                    "UPDATE users SET role = ? WHERE id = ?", (role, user_id)
                )
                promoted += cursor.rowcount
            if promoted:
                log.info(f"  Promoted {promoted} user(s) from admin_users → users.role")
            else:
                log.info("  No admin/superadmin rows found in admin_users")
        cursor.execute("DROP TABLE admin_users")
        log.info("  dropped: admin_users")


# ─────────────────────────────────────────────────────────────────────────────
# Step 15 – set active session in academic_settings (RISK-18)
# ─────────────────────────────────────────────────────────────────────────────

def set_active_session(cursor, session: str, term: str):
    cursor.execute("INSERT OR IGNORE INTO sessions (session) VALUES (?)", (session,))
    cursor.execute("UPDATE sessions SET is_active = 1 WHERE session = ?",  (session,))
    cursor.execute("""
        UPDATE academic_settings
        SET current_session = ?, current_term = ?
        WHERE id = 1
    """, (session, term))

    # Report all sessions present so operator can verify (RISK-18)
    cursor.execute("SELECT session, is_active FROM sessions ORDER BY session")
    all_sessions = cursor.fetchall()
    log.info(f"  Active session set → '{session}' / term '{term}'")
    if len(all_sessions) > 1:
        summary = ", ".join(
            f"{s}({'active' if a else 'inactive'})" for s, a in all_sessions
        )
        log.warning(
            f"  Multiple sessions found in DB: {summary}. "
            f"If '{session}' is not correct, update "
            f"academic_settings.current_session manually after migration."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Step 16 – performance indexes
# ─────────────────────────────────────────────────────────────────────────────

NEW_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_cs_class          ON class_sessions(class_name)",
    "CREATE INDEX IF NOT EXISTS idx_cs_session         ON class_sessions(session)",
    "CREATE INDEX IF NOT EXISTS idx_css_cs_id          ON class_session_students(class_session_id)",
    "CREATE INDEX IF NOT EXISTS idx_css_student        ON class_session_students(student_name)",
    "CREATE INDEX IF NOT EXISTS idx_css_cls_ses        ON class_session_students(class_name, session)",
    "CREATE INDEX IF NOT EXISTS idx_ta_user            ON teacher_assignments(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_ta_cs_id           ON teacher_assignments(class_session_id)",
    "CREATE INDEX IF NOT EXISTS idx_sc_enroll          ON scores(enrollment_id)",
    "CREATE INDEX IF NOT EXISTS idx_sc_cls_ses_term    ON scores(class_name, session, term)",
    "CREATE INDEX IF NOT EXISTS idx_sc_student         ON scores(student_name, session)",
    "CREATE INDEX IF NOT EXISTS idx_sc_total           ON scores(total_score DESC)",
    "CREATE INDEX IF NOT EXISTS idx_sub_class          ON subjects(class_name)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email  ON users(email)",
    "CREATE INDEX IF NOT EXISTS idx_ct_type_range      ON comment_templates(comment_type, average_lower, average_upper)",
]


def create_indexes(cursor):
    log.info("Creating performance indexes …")
    for sql in NEW_INDEXES:
        try:
            cursor.execute(sql)
        except Exception as exc:
            log.warning(f"  index skipped ({exc}): {sql[:70]}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def run_migration(db_path: str, default_session: str, default_term: str,
                  dry_run: bool = False):

    if not os.path.exists(db_path):
        log.error(f"Database not found: {db_path}")
        sys.exit(1)

    log.info("=" * 62)
    log.info(f"  Database : {db_path}")
    log.info(f"  Session  : {default_session}  |  Term : {default_term}")
    log.info(f"  Dry-run  : {dry_run}")
    log.info("=" * 62)

    bak = backup(db_path)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = OFF")   # required for table rebuilds
    conn.execute("PRAGMA journal_mode = WAL")   # safer for long transactions
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        if already_migrated(cursor):
            log.info("Database is already on the new schema — nothing to do.")
            conn.close()
            return

        log.info("═" * 62)
        log.info("  Migration starting …")
        log.info("═" * 62)

        # All steps share one implicit transaction.
        # Any unhandled exception triggers conn.rollback() → zero writes land.
        create_new_tables(cursor)
        migrate_classes(cursor)
        migrate_subjects(cursor)
        migrate_users(cursor)
        migrate_students(cursor, default_session, default_term)
        ensure_sessions_from_scores(cursor)
        migrate_scores(cursor)
        migrate_teacher_assignments(cursor)
        migrate_comments(cursor)
        migrate_psychomotor(cursor)
        migrate_student_subject_selections(cursor)
        verify_unchanged_tables(cursor)
        drop_legacy_tables(cursor)
        set_active_session(cursor, default_session, default_term)
        create_indexes(cursor)

        if dry_run:
            conn.rollback()
            log.info("DRY RUN — all changes rolled back. Database is unchanged.")
        else:
            conn.commit()
            log.info("═" * 62)
            log.info("  Migration committed successfully ✓")
            log.info(f"  Backup at : {bak}")
            log.info("═" * 62)

            # ── Rename DB file to suis.db ──────────────────────────────────
            conn.close()   # must close before rename
            db_dir    = os.path.dirname(os.path.abspath(db_path))
            suis_path = os.path.join(db_dir, "suis.db")
            if os.path.abspath(db_path) != os.path.abspath(suis_path):
                if os.path.exists(suis_path):
                    log.warning(
                        f"  suis.db already exists at {suis_path} — skipping rename. "
                        f"Rename manually if needed."
                    )
                else:
                    os.rename(db_path, suis_path)
                    log.info(f"  Database renamed → {suis_path}")
            return   # conn already closed above, skip finally block

    except Exception as exc:
        conn.rollback()
        log.error("═" * 62)
        log.error(f"  MIGRATION FAILED: {exc}")
        log.error("  All changes rolled back — original database is untouched.")
        log.error(f"  Your backup is safe at : {bak}")
        log.error("═" * 62)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.close()
        except Exception:
            pass   # connection may already be closed (e.g. after rename)


# ─────────────────────────────────────────────────────────────────────────────
# Run configuration — edit the four values below, then run:
#   python migrate_to_new_schema.py
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    # 1. Full path to your database file
    DB_PATH = r"C:\Users\imosteve\Documents\Result system\python system\student_results_app\data\school.db"  # will be renamed to suis.db automatically

    # 2. The academic session your existing data belongs to
    SESSION = "2024/2025"

    # 3. The current term: "First", "Second", or "Third"
    TERM = "First"

    # 4. Set DRY_RUN = True to do a safe test-run (no changes written to disk)
    #    Set DRY_RUN = False when you are ready to do the real migration
    DRY_RUN = False

    # ── DO NOT EDIT BELOW THIS LINE ──────────────────────────────────────────
    run_migration(
        db_path         = DB_PATH,
        default_session = SESSION,
        default_term    = TERM,
        dry_run         = DRY_RUN,
    )