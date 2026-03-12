# database_school/schema.py

import logging
from .connection import get_connection

logger = logging.getLogger(__name__)


def create_tables(db_path=None):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")

    # ── LAYER 0 — CONTROL TABLES ──────────────────────────────────────────────

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session    TEXT    NOT NULL UNIQUE,
            is_active  INTEGER NOT NULL DEFAULT 0
                           CHECK(is_active IN (0, 1)),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS academic_settings (
            id              INTEGER PRIMARY KEY CHECK(id = 1),
            current_session TEXT    NOT NULL DEFAULT '',
            current_term    TEXT    NOT NULL DEFAULT 'First'
                                CHECK(current_term IN ('First', 'Second', 'Third')),
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by      TEXT
        )
    """)

    cursor.execute("""
        INSERT OR IGNORE INTO academic_settings (id, current_session, current_term)
        VALUES (1, '', 'First')
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT    NOT NULL UNIQUE,
            email      TEXT    NOT NULL UNIQUE,
            password   TEXT    NOT NULL,
            role       TEXT    NOT NULL DEFAULT 'teacher'
                           CHECK(role IN ('superadmin', 'admin', 'teacher')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── LAYER 1 — PERMANENT DEFINITIONS ──────────────────────────────────────

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS classes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            class_name  TEXT    NOT NULL UNIQUE,
            description TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
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
        CREATE TABLE IF NOT EXISTS students (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name     TEXT    NOT NULL UNIQUE,
            gender           TEXT    CHECK(gender IN ('M', 'F')),
            email            TEXT,
            date_of_birth    TEXT,
            admission_number TEXT    UNIQUE,
            school_fees_paid TEXT    NOT NULL DEFAULT 'NO'
                                 CHECK(school_fees_paid IN ('YES', 'NO')),
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── LAYER 2 — SESSION ENROLLMENT ─────────────────────────────────────────

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS class_sessions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            class_name TEXT    NOT NULL
                           REFERENCES classes(class_name)
                           ON DELETE CASCADE ON UPDATE CASCADE,
            session    TEXT    NOT NULL
                           REFERENCES sessions(session)
                           ON DELETE CASCADE ON UPDATE CASCADE,
            is_active  INTEGER NOT NULL DEFAULT 1
                           CHECK(is_active IN (0, 1)),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(class_name, session)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teacher_assignments (
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
                                 CHECK(assignment_type IN ('class_teacher', 'subject_teacher')),
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, class_session_id, subject_name, assignment_type)
        )
    """)

    # ── LAYER 3 — STUDENT ENROLLMENT (PER-TERM) ───────────────────────────────
    # One row = one student enrolled in one class for one TERM of one session.
    # A student present all 3 terms has 3 rows (one per term).
    # A new student joining in Term 2 has rows for Second and Third only.
    # CASCADE DELETE: removing a class_session removes all its enrollments,
    # which in turn removes all their scores/comments/etc.

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS class_session_students (
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

    # ── LAYER 4 — TERM DATA ───────────────────────────────────────────────────

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scores (
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
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS psychomotor_ratings (
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
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comments (
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
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_subject_selections (
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
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS next_term_info (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            term             TEXT    NOT NULL
                                 CHECK(term IN ('First', 'Second', 'Third')),
            session          TEXT    NOT NULL,
            next_term_begins DATE,
            fees_json        TEXT    NOT NULL DEFAULT '{}',
            updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by       INTEGER
                                 REFERENCES users(id)
                                 ON DELETE SET NULL,
            UNIQUE(term, session)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comment_templates (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            comment_text  TEXT    NOT NULL,
            comment_type  TEXT    NOT NULL
                              CHECK(comment_type IN ('class_teacher', 'head_teacher')),
            average_lower REAL,
            average_upper REAL,
            created_by    INTEGER NOT NULL
                              REFERENCES users(id)
                              ON DELETE CASCADE,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(comment_text, comment_type),
            CHECK (
                (comment_type = 'class_teacher'
                    AND average_lower IS NULL AND average_upper IS NULL)
                OR
                (comment_type = 'head_teacher'
                    AND average_lower IS NOT NULL AND average_upper IS NOT NULL)
            )
        )
    """)

    conn.commit()
    conn.close()
    _create_indexes(db_path)
    logger.info(f"Tables created/verified for: {db_path or 'active session DB'}")


def _create_indexes(db_path=None):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_cs_class      ON class_sessions(class_name)",
            "CREATE INDEX IF NOT EXISTS idx_cs_session    ON class_sessions(session)",
            "CREATE INDEX IF NOT EXISTS idx_css_cs_id     ON class_session_students(class_session_id)",
            "CREATE INDEX IF NOT EXISTS idx_css_student   ON class_session_students(student_name)",
            "CREATE INDEX IF NOT EXISTS idx_css_cls_ses   ON class_session_students(class_name, session)",
            "CREATE INDEX IF NOT EXISTS idx_css_term      ON class_session_students(term)",
            # New: fast lookup for (class, session, term) — the most common query
            "CREATE INDEX IF NOT EXISTS idx_css_cls_ses_term ON class_session_students(class_name, session, term)",
            "CREATE INDEX IF NOT EXISTS idx_ta_user       ON teacher_assignments(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_ta_cs_id      ON teacher_assignments(class_session_id)",
            "CREATE INDEX IF NOT EXISTS idx_sc_enroll     ON scores(enrollment_id)",
            "CREATE INDEX IF NOT EXISTS idx_sc_cls_ses_term ON scores(class_name, session, term)",
            "CREATE INDEX IF NOT EXISTS idx_sc_student    ON scores(student_name, session)",
            "CREATE INDEX IF NOT EXISTS idx_sc_total      ON scores(total_score DESC)",
            "CREATE INDEX IF NOT EXISTS idx_sub_class     ON subjects(class_name)",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)",
            "CREATE INDEX IF NOT EXISTS idx_ct_type_range ON comment_templates(comment_type, average_lower, average_upper)",
        ]
        for sql in indexes:
            cursor.execute(sql)
        conn.commit()
        logger.info("Performance indexes created/verified")
        return True
    except Exception as e:
        logger.error(f"Error creating indexes: {e}")
        return False
    finally:
        conn.close()