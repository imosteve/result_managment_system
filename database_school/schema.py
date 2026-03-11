# database_school/schema.py

import logging
from .connection import get_connection

logger = logging.getLogger(__name__)


def create_tables(db_path=None):
    """
    Create all school database tables.
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")

    # ══════════════════════════════════════════════════════════════
    # LAYER 0 — CONTROL TABLES
    # ══════════════════════════════════════════════════════════════

    # Sessions Table 
    # One row per academic year. Admin creates this before the year begins.
    # session TEXT is the natural key used everywhere else.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session    TEXT    NOT NULL UNIQUE,
            is_active  INTEGER NOT NULL DEFAULT 0
                           CHECK(is_active IN (0, 1)),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Academic settings Table 
    # Single-row table (id = 1 enforced by CHECK).
    # Admins update current_session / current_term to switch context.
    # All teacher views read this — teachers never select term/session.
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

    # Seed the single row if not present
    cursor.execute("""
        INSERT OR IGNORE INTO academic_settings (id, current_session, current_term)
        VALUES (1, '', 'First')
    """)

    # Users Table 
    # Defined early — other tables reference users(id).
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

    # ══════════════════════════════════════════════════════════════
    # LAYER 1 — PERMANENT DEFINITIONS
    # ══════════════════════════════════════════════════════════════

    # Classes Table 
    # Created once. "Primary 4" exists here independently of any
    # session or term. class_name is the natural join key.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS classes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            class_name  TEXT    NOT NULL UNIQUE,
            description TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Subjects Table 
    # Subjects belong to a class, not to a term or session.
    # "Mathematics" for "Primary 4" is defined once and applies to
    # all sessions and all three terms.
    # max_ca_score + max_exam_score allow per-subject score weighting.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
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
    """)

    # Students (master registry) Table 
    # One row per student, ever. student_name is the natural join key.
    # Students are not re-registered each year — only enrolled into
    # a class-session (see class_session_students below).
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

    # ══════════════════════════════════════════════════════════════
    # LAYER 2 — SESSION ENROLLMENT
    # ══════════════════════════════════════════════════════════════

    # Class-sessions Table 
    # One row = one class open for one academic year.
    # All three terms share this row.
    # Admin "opens" a class for a session before the year begins.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS class_sessions (
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
    """)

    # Teacher assignments Table 
    # Links a user (teacher) to a class-session.
    # assignment_type = 'class_teacher'   → responsible for the whole class
    # assignment_type = 'subject_teacher' → teaches a specific subject only
    # subject_name is NULL for class_teacher assignments.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teacher_assignments (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL
                                REFERENCES users(id)
                                ON DELETE CASCADE
                                ON UPDATE CASCADE,
            class_session_id INTEGER NOT NULL
                                REFERENCES class_sessions(id)
                                ON DELETE CASCADE
                                ON UPDATE CASCADE,
            -- denormalised for convenient queries (avoids joins in hot paths)
            class_name      TEXT    NOT NULL,
            session         TEXT    NOT NULL,
            subject_name    TEXT,   -- NULL for class_teacher assignments
            assignment_type TEXT    NOT NULL
                                CHECK(assignment_type IN ('class_teacher', 'subject_teacher')),
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, class_session_id, subject_name, assignment_type)
        )
    """)

    # ══════════════════════════════════════════════════════════════
    # LAYER 3 — STUDENT ENROLLMENT
    # ══════════════════════════════════════════════════════════════

    # Class-session students Table 
    # One row = one student enrolled in one class for one academic year.
    # This replaces the old per-term student registration.
    # Enrolling once here makes the student valid for all three terms.
    # CASCADE DELETE: removing a class_session removes all its students,
    #   which in turn removes all their scores/comments/etc.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS class_session_students (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            class_session_id INTEGER NOT NULL
                                 REFERENCES class_sessions(id)
                                 ON DELETE CASCADE
                                 ON UPDATE CASCADE,
            student_name     TEXT    NOT NULL
                                 REFERENCES students(student_name)
                                 ON DELETE CASCADE
                                 ON UPDATE CASCADE,
            -- denormalised for query convenience
            class_name       TEXT    NOT NULL,
            session          TEXT    NOT NULL,
            enrollment_date  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(class_session_id, student_name)
        )
    """)

    # ══════════════════════════════════════════════════════════════
    # LAYER 4 — TERM DATA  (new rows per term, old rows untouched)
    # ══════════════════════════════════════════════════════════════

    # Scores Table 
    # One row per (enrollment_id, subject_name, term).
    # Switching to Term 2: new rows are inserted, Term 1 rows untouched.
    # enrollment_id CASCADE: deleting an enrollment deletes all its scores.
    # subject_name is a soft reference to subjects(subject_name, class_name)
    # — see module docstring for why it's not a hard FK.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            enrollment_id INTEGER NOT NULL
                              REFERENCES class_session_students(id)
                              ON DELETE CASCADE
                              ON UPDATE CASCADE,
            -- denormalised for backward-compat with existing query code
            student_name  TEXT    NOT NULL,
            class_name    TEXT    NOT NULL,
            session       TEXT    NOT NULL,
            -- context
            term          TEXT    NOT NULL
                              CHECK(term IN ('First', 'Second', 'Third')),
            subject_name  TEXT    NOT NULL,
            -- score components  (old schema: test_score + exam_score)
            ca_score      REAL    NOT NULL DEFAULT 0,
            exam_score    REAL    NOT NULL DEFAULT 0,
            total_score   REAL    GENERATED ALWAYS AS (ca_score + exam_score) STORED,
            grade         TEXT,
            position      INTEGER,
            -- audit
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by    TEXT,
            UNIQUE(enrollment_id, subject_name, term)
        )
    """)

    # Psychomotor / Ratings Table 
    # Per (enrollment_id, term). Same fields as old psychomotor_ratings.
    # Old field names preserved to avoid breaking report generators.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS psychomotor_ratings (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            enrollment_id    INTEGER NOT NULL
                                 REFERENCES class_session_students(id)
                                 ON DELETE CASCADE
                                 ON UPDATE CASCADE,
            -- denormalised
            student_name     TEXT    NOT NULL,
            class_name       TEXT    NOT NULL,
            session          TEXT    NOT NULL,
            term             TEXT    NOT NULL
                                 CHECK(term IN ('First', 'Second', 'Third')),
            -- affective domain
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

    # Comments Table 
    # Per (enrollment_id, term). New term = new row; old rows untouched.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id                          INTEGER PRIMARY KEY AUTOINCREMENT,
            enrollment_id               INTEGER NOT NULL
                                            REFERENCES class_session_students(id)
                                            ON DELETE CASCADE
                                            ON UPDATE CASCADE,
            -- denormalised
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

    # Student subject selections Table 
    # For elective subjects (e.g. SSS2/SSS3). Per (enrollment_id, term).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_subject_selections (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            enrollment_id INTEGER NOT NULL
                              REFERENCES class_session_students(id)
                              ON DELETE CASCADE
                              ON UPDATE CASCADE,
            -- denormalised
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

    # Next term info Table 
    # School-wide. One row per (term, session).
    # updated_by is SET NULL if the user is deleted (soft reference).
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

    # Comment templates Table 
    # Global pool of reusable comment text.
    # created_by CASCADE: deleting a user removes their templates.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comment_templates (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            comment_text TEXT    NOT NULL,
            comment_type TEXT    NOT NULL
                             CHECK(comment_type IN ('class_teacher', 'head_teacher')),
            average_lower REAL,
            average_upper REAL,
            created_by   INTEGER NOT NULL
                             REFERENCES users(id)
                             ON DELETE CASCADE,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(comment_text, comment_type),
            CHECK (
                (comment_type = 'class_teacher'
                    AND average_lower IS NULL
                    AND average_upper IS NULL)
                OR
                (comment_type = 'head_teacher'
                    AND average_lower IS NOT NULL
                    AND average_upper IS NOT NULL)
            )
        )
    """)

    conn.commit()
    conn.close()

    _create_indexes(db_path)
    logger.info(f"Tables created/verified for: {db_path or 'active session DB'}")


def _create_indexes(db_path=None):
    """Create performance indexes."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        indexes = [
            # class_sessions
            "CREATE INDEX IF NOT EXISTS idx_cs_class    ON class_sessions(class_name)",
            "CREATE INDEX IF NOT EXISTS idx_cs_session  ON class_sessions(session)",
            # class_session_students
            "CREATE INDEX IF NOT EXISTS idx_css_cs_id   ON class_session_students(class_session_id)",
            "CREATE INDEX IF NOT EXISTS idx_css_student ON class_session_students(student_name)",
            "CREATE INDEX IF NOT EXISTS idx_css_cls_ses ON class_session_students(class_name, session)",
            # teacher_assignments
            "CREATE INDEX IF NOT EXISTS idx_ta_user     ON teacher_assignments(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_ta_cs_id    ON teacher_assignments(class_session_id)",
            # scores
            "CREATE INDEX IF NOT EXISTS idx_sc_enroll   ON scores(enrollment_id)",
            "CREATE INDEX IF NOT EXISTS idx_sc_cls_ses_term ON scores(class_name, session, term)",
            "CREATE INDEX IF NOT EXISTS idx_sc_student  ON scores(student_name, session)",
            "CREATE INDEX IF NOT EXISTS idx_sc_total    ON scores(total_score DESC)",
            # subjects
            "CREATE INDEX IF NOT EXISTS idx_sub_class   ON subjects(class_name)",
            # users
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)",
            # comment_templates
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