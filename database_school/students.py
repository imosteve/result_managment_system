# database_school/students.py
"""
Student management — master registry and per-term enrollment.

CONCEPTS
════════
• students table  = master registry. One row per student, ever.
  student_name is the natural key used across all related tables.

• class_session_students = per-TERM enrollment.
  One row per (student, class_session, term).
  A student present for all 3 terms of a session has 3 rows.
  A student who joins in Term 2 has rows for Second and Third only.
  Adding/removing a student in Term 2 does NOT affect Term 1 or Term 3.

• enrollment_id = class_session_students.id
  The FK used by scores, comments, psychomotor_ratings, subject_selections.
  Each enrollment_id is specific to one term — downstream data is
  automatically term-scoped through this FK.

• IMPORT / PROMOTION: import_students_from_class() bulk-enrolls students
  from a previous class into a new one for all 3 terms by default.
"""

import sqlite3
import logging
from .connection import get_connection

logger = logging.getLogger(__name__)

VALID_TERMS = ("First", "Second", "Third")


# ═════════════════════════════════════════════════════════════════
# Master student registry
# ═════════════════════════════════════════════════════════════════

def create_student(student_name: str, gender: str = None,
                   email: str = None, date_of_birth: str = None,
                   admission_number: str = None,
                   school_fees_paid: str = "NO") -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO students
                (student_name, gender, email, date_of_birth,
                 admission_number, school_fees_paid)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (student_name.strip(), gender, email,
              date_of_birth, admission_number, school_fees_paid))
        conn.commit()
        logger.info(f"Student '{student_name}' added to master registry")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Student '{student_name}' already exists")
        return False
    except Exception as e:
        logger.error(f"Error creating student: {e}")
        return False
    finally:
        conn.close()


def get_all_students() -> list:
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, student_name, gender, email, date_of_birth,
               admission_number, school_fees_paid, created_at
        FROM   students
        ORDER  BY student_name
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def student_exists(student_name: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM students WHERE student_name = ?", (student_name,))
    result = cursor.fetchone() is not None
    conn.close()
    return result


def update_student(student_name: str, new_name: str = None,
                   gender: str = None, email: str = None,
                   date_of_birth: str = None,
                   admission_number: str = None,
                   school_fees_paid: str = None) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        updates = {}
        if new_name and new_name.strip() != student_name:
            updates["student_name"] = new_name.strip()
        if gender is not None:
            updates["gender"] = gender
        if email is not None:
            updates["email"] = email
        if date_of_birth is not None:
            updates["date_of_birth"] = date_of_birth
        if admission_number is not None:
            updates["admission_number"] = admission_number
        if school_fees_paid is not None:
            updates["school_fees_paid"] = school_fees_paid
        if not updates:
            return True
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [student_name]
        cursor.execute(
            f"UPDATE students SET {set_clause} WHERE student_name = ?", values
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Update failed for '{student_name}' — conflict on unique field")
        return False
    except Exception as e:
        logger.error(f"Error updating student: {e}")
        return False
    finally:
        conn.close()


def delete_student(student_name: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM students WHERE student_name = ?", (student_name,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error deleting student: {e}")
        return False
    finally:
        conn.close()


# ═════════════════════════════════════════════════════════════════
# Per-term enrollment (class_session_students)
# ═════════════════════════════════════════════════════════════════

def enroll_student(student_name: str, class_name: str,
                   session: str, term: str) -> tuple:
    """
    Enroll a student in a class for a specific term of a session.
    Auto-creates the student in the master registry if not already there.
    Idempotent — safe to call if already enrolled (INSERT OR IGNORE).

    Args:
        student_name: student's full name
        class_name:   must have an open class_sessions row for this session
        session:      e.g. "2024/2025"
        term:         "First", "Second", or "Third"

    Returns:
        (True, enrollment_id) on success
        (False, reason_string) on failure
    """
    if term not in VALID_TERMS:
        return False, f"Invalid term '{term}'. Must be one of {VALID_TERMS}."

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR IGNORE INTO students (student_name) VALUES (?)",
            (student_name.strip(),)
        )

        cursor.execute("""
            SELECT id FROM class_sessions
            WHERE class_name = ? AND session = ?
        """, (class_name, session))
        row = cursor.fetchone()
        if not row:
            return (
                False,
                f"'{class_name}' is not open for session '{session}'. "
                "Ask an admin to open it first."
            )
        class_session_id = row[0]

        cursor.execute("""
            INSERT OR IGNORE INTO class_session_students
                (class_session_id, student_name, class_name, session, term)
            VALUES (?, ?, ?, ?, ?)
        """, (class_session_id, student_name.strip(), class_name, session, term))
        conn.commit()

        cursor.execute("""
            SELECT id FROM class_session_students
            WHERE class_session_id = ? AND student_name = ? AND term = ?
        """, (class_session_id, student_name.strip(), term))
        enrollment_id = cursor.fetchone()[0]
        logger.info(f"Enrolled '{student_name}' in '{class_name}' / '{session}' / {term}")
        return True, enrollment_id
    except Exception as e:
        logger.error(f"Error enrolling student: {e}")
        return False, str(e)
    finally:
        conn.close()


def enroll_student_all_terms(student_name: str, class_name: str,
                              session: str) -> tuple:
    """
    Enroll a student in all 3 terms of a session at once.
    Convenience wrapper for the common case.

    Returns:
        (True, {term: enrollment_id, ...}) on success
        (False, reason_string) on first failure
    """
    ids = {}
    for term in VALID_TERMS:
        ok, result = enroll_student(student_name, class_name, session, term)
        if not ok:
            return False, result
        ids[term] = result
    return True, ids


def bulk_enroll_students(student_names: list, class_name: str,
                          session: str, terms: tuple = VALID_TERMS) -> dict:
    """
    Enroll multiple students at once for the specified terms.

    Args:
        student_names: list of student name strings
        class_name, session: context
        terms: tuple of term strings to enroll for (default: all 3)

    Returns:
        dict: {enrolled: [names], errors: [{name, reason}]}
    """
    results = {"enrolled": [], "errors": []}
    for name in student_names:
        name = name.strip()
        if not name:
            continue
        failed = False
        for term in terms:
            ok, detail = enroll_student(name, class_name, session, term)
            if not ok and "already" not in str(detail).lower():
                results["errors"].append({"name": name, "reason": detail})
                failed = True
                break
        if not failed:
            results["enrolled"].append(name)
    return results


def unenroll_student(student_name: str, class_name: str,
                     session: str, term: str) -> bool:
    """
    Remove a student's enrollment from a specific term of a class-session.
    CASCADE deletes all their scores, comments, psychomotor ratings, and
    subject selections for that term only.
    Other terms in the same session are NOT affected.

    Args:
        student_name, class_name, session: context
        term: "First", "Second", or "Third" — only this term is removed

    Returns True if a row was deleted.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            DELETE FROM class_session_students
            WHERE student_name = ? AND term = ?
              AND class_session_id = (
                  SELECT id FROM class_sessions
                  WHERE class_name = ? AND session = ?
              )
        """, (student_name, term, class_name, session))
        conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info(
                f"Unenrolled '{student_name}' from "
                f"'{class_name}' / '{session}' / {term}"
            )
        return deleted
    except Exception as e:
        logger.error(f"Error unenrolling student: {e}")
        return False
    finally:
        conn.close()


def unenroll_student_all_terms(student_name: str, class_name: str,
                                session: str) -> int:
    """
    Remove a student from ALL terms of a class-session.
    Use when fully removing a student from a session (not just one term).
    Returns count of term rows deleted (0-3).
    """
    count = 0
    for term in VALID_TERMS:
        if unenroll_student(student_name, class_name, session, term):
            count += 1
    return count


def get_enrolled_students(class_name: str, session: str, term: str) -> list:
    """
    Return all students enrolled in a class for a specific term.

    Args:
        class_name, session: identify the class-session
        term: "First", "Second", or "Third"

    Returns list of dicts:
        {enrollment_id, student_name, class_name, session, term,
         gender, email, admission_number, school_fees_paid, enrollment_date}
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            css.id              AS enrollment_id,
            css.student_name,
            css.class_name,
            css.session,
            css.term,
            s.gender,
            s.email,
            s.admission_number,
            s.school_fees_paid,
            css.enrollment_date
        FROM  class_session_students css
        JOIN  students s        ON s.student_name = css.student_name
        JOIN  class_sessions cs ON cs.id = css.class_session_id
        WHERE cs.class_name = ? AND cs.session = ? AND css.term = ?
        ORDER BY css.student_name
    """, (class_name, session, term))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_enrollment_id(student_name: str, class_name: str,
                      session: str, term: str) -> int | None:
    """
    Return class_session_students.id for a student in a class/session/term.
    Used as the FK when writing scores, comments, psychomotor, etc.
    Returns None if student is not enrolled for that term.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT css.id
        FROM   class_session_students css
        JOIN   class_sessions cs ON cs.id = css.class_session_id
        WHERE  css.student_name = ?
          AND  cs.class_name   = ?
          AND  cs.session      = ?
          AND  css.term        = ?
    """, (student_name, class_name, session, term))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def get_student_enrolled_terms(student_name: str, class_name: str,
                                session: str) -> list:
    """
    Return the list of terms a student is enrolled in for a class/session.
    e.g. ["First", "Second"] if they joined in Term 1 but left before Term 3.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT css.term
        FROM   class_session_students css
        JOIN   class_sessions cs ON cs.id = css.class_session_id
        WHERE  css.student_name = ?
          AND  cs.class_name   = ?
          AND  cs.session      = ?
        ORDER  BY css.term
    """, (student_name, class_name, session))
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_students_not_enrolled_in(class_name: str, session: str,
                                  term: str) -> list:
    """
    Return master registry students NOT enrolled in this class/session/term.
    Useful for the 'add students' picker UI.
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.student_name, s.gender, s.admission_number
        FROM   students s
        WHERE  s.student_name NOT IN (
            SELECT css.student_name
            FROM   class_session_students css
            JOIN   class_sessions cs ON cs.id = css.class_session_id
            WHERE  cs.class_name = ? AND cs.session = ? AND css.term = ?
        )
        ORDER BY s.student_name
    """, (class_name, session, term))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ═════════════════════════════════════════════════════════════════
# Student import / promotion
# ═════════════════════════════════════════════════════════════════

def import_students_from_class(source_class: str, source_session: str,
                                target_class: str, target_session: str,
                                terms: tuple = VALID_TERMS) -> dict:
    """
    Copy student enrollments from one class-session to another.
    Enrolls each student in all specified terms of the target session.

    Typical use: promotion. E.g. copy all "Primary 4 / 2024-2025"
    students into "Primary 5 / 2025-2026".

    Target class_session must already exist (admin opens it first).
    Existing enrollments in the target are skipped (INSERT OR IGNORE).

    Args:
        source_class, source_session: where to copy from
        target_class, target_session: where to copy to
        terms: which terms to enroll in (default: all 3)

    Returns:
        dict: {imported: int, skipped: int, error: str or None}
    """
    # Get distinct students from ANY term in the source
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT css.student_name
        FROM   class_session_students css
        JOIN   class_sessions cs ON cs.id = css.class_session_id
        WHERE  cs.class_name = ? AND cs.session = ?
        ORDER  BY css.student_name
    """, (source_class, source_session))
    source_students = [r["student_name"] for r in cursor.fetchall()]
    conn.close()

    if not source_students:
        return {
            "imported": 0, "skipped": 0,
            "error": f"No students found in '{source_class}' / '{source_session}'."
        }

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id FROM class_sessions
            WHERE class_name = ? AND session = ?
        """, (target_class, target_session))
        row = cursor.fetchone()
        if not row:
            return {
                "imported": 0, "skipped": 0,
                "error": (
                    f"'{target_class}' is not open for session '{target_session}'. "
                    "Open it first."
                )
            }
        target_cs_id = row[0]

        imported = skipped = 0
        for name in source_students:
            cursor.execute(
                "INSERT OR IGNORE INTO students (student_name) VALUES (?)", (name,)
            )
            student_imported = False
            for term in terms:
                cursor.execute("""
                    INSERT OR IGNORE INTO class_session_students
                        (class_session_id, student_name, class_name, session, term)
                    VALUES (?, ?, ?, ?, ?)
                """, (target_cs_id, name, target_class, target_session, term))
                if cursor.rowcount:
                    student_imported = True
            if student_imported:
                imported += 1
            else:
                skipped += 1

        conn.commit()
        logger.info(
            f"Imported {imported} students from "
            f"'{source_class}/{source_session}' → "
            f"'{target_class}/{target_session}' for terms {terms}"
        )
        return {"imported": imported, "skipped": skipped, "error": None}
    except Exception as e:
        logger.error(f"Error importing students: {e}")
        return {"imported": 0, "skipped": 0, "error": str(e)}
    finally:
        conn.close()